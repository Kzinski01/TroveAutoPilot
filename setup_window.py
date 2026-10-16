"""Janela de resgate: aparece quando falta dependencia, antes da GUI principal.

So usa tkinter (stdlib), entao funciona mesmo com o ambiente vazio.
"""

import queue
import threading
import tkinter as tk

import deps

# mesmos tokens do tema da interface (ui/app/globals.css)
BG = "#09090b"
PANEL = "#141415"
ACCENT = "#0066ff"
TEXT = "#fafafa"
DANGER = "#ef4444"


class SetupWindow:
    def __init__(self, missing):
        self.restart = False
        # Tk so aceita chamadas da thread principal; o worker do pip enfileira.
        self._ui_queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title("Trove AutoBot - dependencias")
        self.root.configure(bg=BG)
        self.root.geometry("620x420")

        tk.Label(self.root, text="Faltam dependências", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18,
                                                     pady=(16, 2))
        tk.Label(self.root, text=", ".join(missing), bg=BG, fg=DANGER,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=18)
        tk.Label(self.root,
                 text="Clique abaixo para instalar. Precisa de internet.",
                 bg=BG, fg=TEXT, font=("Segoe UI", 9)).pack(anchor="w", padx=18,
                                                            pady=(6, 10))

        self.button = tk.Button(
            self.root, text="Instalar dependências", relief="flat", bg=ACCENT,
            fg="#ffffff", activebackground=TEXT, cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=18, pady=6,
            command=self._install)
        self.button.pack(anchor="w", padx=18)

        self.log_box = tk.Text(self.root, bg=PANEL, fg=TEXT, relief="flat",
                               font=("Consolas", 9), state="disabled", wrap="none")
        self.log_box.pack(fill="both", expand=True, padx=18, pady=14)

    def _post(self, callback):
        self._ui_queue.put(callback)

    def _pump(self):
        for _ in range(200):
            try:
                callback = self._ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except tk.TclError:
                return
        self.root.after(100, self._pump)

    def log(self, message):
        self._post(lambda: self._append(message))

    def _append(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _install(self):
        self.button.configure(state="disabled", text="Instalando…")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        code = deps.install(self.log)
        remaining = deps.missing()
        if code == 0 and not remaining:
            self.log("Tudo pronto. Iniciando o bot…")
            self.restart = True
            self._post(lambda: self.root.after(1200, self.root.destroy))
        else:
            if remaining:
                self.log("Ainda faltando: " + ", ".join(remaining))
            self._post(lambda: self.button.configure(
                state="normal", text="Tentar de novo"))

    def run(self):
        self.root.after(100, self._pump)
        self.root.mainloop()
        return self.restart
