"""Overlay em tela cheia para o usuario marcar uma area ou um ponto da tela.

Cria o proprio `Tk` a cada uso, porque a janela principal do bot e o webview
(sem tkinter).

**Todo o tkinter vive numa unica thread permanente, e so nela.** Um interpretador
Tcl pertence a thread que o criou e precisa ser destruido por ela. Antes o
overlay era montado na thread de quem chamou - que e uma thread nova do
pywebview, morta logo depois. Os objetos do Tk sobreviviam ate a coleta de lixo
e eram finalizados numa thread qualquer, o que corrompia a memoria: o processo
caia com STATUS_BREAKPOINT na alocacao seguinte, sempre em outro lugar.
"""

import gc
import queue
import threading
import time
import tkinter as tk

ACCENT = "#0066ff"
BG = "#09090b"
FG = "#fafafa"

# Depois de fechar o seletor, o Windows ainda leva um instante para repintar a
# area. Capturar antes disso deixaria o proprio overlay dentro do template.
REDRAW_DELAY = 0.25

_pedidos = queue.Queue()
_worker = None
_worker_lock = threading.Lock()


class _Pedido:
    """Um seletor a abrir e o lugar onde a resposta e devolvida."""

    __slots__ = ("funcao", "valor", "erro", "pronto")

    def __init__(self, funcao):
        self.funcao = funcao
        self.valor = None
        self.erro = None
        self.pronto = threading.Event()


def _servir_seletores():
    while True:
        pedido = _pedidos.get()
        try:
            pedido.valor = pedido.funcao()
        except Exception as exc:                       # noqa: BLE001
            pedido.erro = exc
        finally:
            # o que sobrou do Tk morre aqui, na thread que o criou, e nao mais
            # numa coleta de lixo em thread alheia
            gc.collect()
            pedido.pronto.set()


def _na_thread_do_tk(funcao):
    """Abre o seletor na thread do tkinter e espera o resultado.

    A fila tambem faz o papel do antigo cadeado: os pedidos sao atendidos um de
    cada vez, entao nunca existem dois overlays ao mesmo tempo.
    """
    global _worker
    if _worker is None:
        with _worker_lock:
            if _worker is None:
                _worker = threading.Thread(target=_servir_seletores,
                                           name="seletor", daemon=True)
                _worker.start()
    pedido = _Pedido(funcao)
    _pedidos.put(pedido)
    pedido.pronto.wait()
    if pedido.erro is not None:
        raise pedido.erro
    return pedido.valor


class _Overlay:
    def __init__(self, hint, mode):
        self.mode = mode                # "region" | "point"
        self.selection = None
        self._start = None
        self._rect = None

        self.root = tk.Tk()
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-alpha", 0.28)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="black", cursor="crosshair")

        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        width = self.root.winfo_screenwidth()
        self.canvas.create_text(width // 2, 60, fill=ACCENT,
                                font=("Segoe UI", 20, "bold"), text=hint)
        self.canvas.create_text(width // 2, 95, fill="white",
                                font=("Segoe UI", 12), text="ESC para cancelar")

        self.root.bind("<Escape>", lambda _event: self._finish())
        if mode == "region":
            self.canvas.bind("<ButtonPress-1>", self._on_press)
            self.canvas.bind("<B1-Motion>", self._on_drag)
            self.canvas.bind("<ButtonRelease-1>", self._on_release)
        else:
            self.canvas.bind("<ButtonPress-1>", self._on_click)

        self.root.focus_force()

    def _finish(self):
        self.root.quit()

    def _on_press(self, event):
        self._start = (event.x_root, event.y_root)
        self._rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=ACCENT, width=2)

    def _on_drag(self, event):
        if self._rect is not None:
            x0 = self._start[0] - self.root.winfo_rootx()
            y0 = self._start[1] - self.root.winfo_rooty()
            self.canvas.coords(self._rect, x0, y0, event.x, event.y)

    def _on_release(self, event):
        if self._start is not None:
            x0, y0 = self._start
            x1, y1 = event.x_root, event.y_root
            width, height = abs(x1 - x0), abs(y1 - y0)
            if width >= 4 and height >= 4:
                self.selection = (min(x0, x1), min(y0, y1), width, height)
        self._finish()

    def _on_click(self, event):
        self.selection = (event.x_root, event.y_root)
        self._finish()

    def run(self):
        try:
            self.root.mainloop()
            return self.selection
        finally:
            self.root.destroy()


def _abrir(hint, mode):
    selection = _Overlay(hint, mode).run()
    # o overlay acabou de sumir; espera o Windows repintar antes da captura
    time.sleep(REDRAW_DELAY)
    return selection


def _run(hint, mode):
    return _na_thread_do_tk(lambda: _abrir(hint, mode))


def select_region(hint="Arraste para selecionar a área"):
    return _run(hint, "region")


def select_point(hint="Clique no ponto desejado"):
    return _run(hint, "point")
