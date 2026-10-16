"""Trove AutoBot - ponto de entrada.

A interface e um app Next.js (React + Tailwind + TypeScript) exportado para
`ui/out`, exibido numa janela nativa pelo pywebview. O nucleo (visao, input,
atalhos) continua em Python e conversa com a interface via `api.Api`.

Uso: python main.py
     --no-elevate  nao tenta reabrir como administrador
     --selftest    confere se a interface carregou e grava selftest.json
"""

import os
import sys

import deps

UI_INDEX = os.path.join("ui", "out", "index.html")
ICON = os.path.join("assets", "icon.ico")

SPLASH_TIMEOUT = 25          # segundos ate tirar a tela de abertura na marra
SELFTEST_DELAY = 8           # tempo que o selftest da para a interface subir

WINDOW_TITLE = "Trove AutoBot"
WINDOW_SIZE = (1040, 760)
WINDOW_MIN_SIZE = (920, 660)
WINDOW_BACKGROUND = "#171221"


def _bundled(relative):
    """Caminho de um recurso empacotado, no codigo ou dentro do exe."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative)


# --------------------------------------------------------- tela de abertura
def _close_splash(log=None):
    """Fecha a imagem de abertura do PyInstaller (so existe no exe)."""
    try:
        import pyi_splash
    except ImportError:
        return                                         # rodando pelo codigo
    try:
        pyi_splash.close()
    except Exception as exc:                           # noqa: BLE001
        if log:
            log(f"Tela de abertura: falha ao fechar ({exc!r}).")


def _start_splash_closer(log=None):
    """Fecha a tela de abertura quando a interface subir (ou no timeout).

    O fechamento roda nesta thread propria de proposito: chamado direto de
    dentro de uma chamada da ponte (thread do WebView2) o pyi_splash nao
    fecha. O timeout e a rede de seguranca para o caso de a interface falhar,
    senao a tela de abertura ficaria presa na frente do usuario.

    Devolve a funcao que a interface usa para sinalizar que subiu.
    """
    import threading

    subiu = threading.Event()

    def esperar_e_fechar():
        subiu.wait(SPLASH_TIMEOUT)
        _close_splash(log)

    threading.Thread(target=esperar_e_fechar, daemon=True).start()
    return subiu.set


# ----------------------------------------------------------- pre-requisitos
def _claim_single_instance():
    """Devolve o modulo do mutex, ou None se ja existe outra instancia aberta.

    Duas instancias brigam de verdade: as duas recebem os atalhos globais e as
    duas comandam o mouse.
    """
    import single_instance
    if single_instance.acquire():
        return single_instance
    _close_splash()
    single_instance.focus_existing()
    return None


def _dependencies_ready():
    """Sem os pacotes, abre a janela de instalacao antes de qualquer import
    pesado (o nucleo importa cv2, mss e pynput no topo)."""
    if not deps.missing():
        return True

    import setup_window
    instalou = setup_window.SetupWindow(deps.missing()).run()
    if not instalou or deps.missing():
        _close_splash()
        return False
    return True


def _handed_over_to_elevated(instance, input_sender):
    """True quando quem assume e uma nova instancia elevada e esta deve sair.

    O Trove costuma rodar como administrador; sem privilegio igual o Windows
    (UIPI) descarta nosso SendInput sem erro nenhum - o bot "roda" e nada
    acontece no jogo.
    """
    if input_sender.is_admin() or "--no-elevate" in sys.argv:
        return False

    instance.release()          # a instancia elevada precisa do mesmo mutex
    if input_sender.relaunch_as_admin():
        _close_splash()
        return True

    instance.acquire()          # a elevacao falhou: seguimos sem privilegio
    print("Aviso: não foi possível elevar. Se o Trove roda como "
          "administrador, o input será ignorado.")
    return False


def _locate_ui():
    """Caminho do index.html compilado, ou None com a instrucao de build."""
    index = _bundled(UI_INDEX)
    if os.path.exists(index):
        return index
    _close_splash()
    print(f"Interface não encontrada em {index}.\n"
          "Rode: cd ui && npm install && npm run build")
    return None


# -------------------------------------------------------------------- nucleo
class _Core:
    """Config, bot, atalhos e a ponte, com o ciclo de vida em um lugar so."""

    def __init__(self):
        import api as api_module
        import bot as bot_module
        import config
        import hotkeys
        import telemetry_server

        self._config = config
        self.cfg = config.load()
        self.engine = bot_module.Bot(self.cfg)
        self.manager = hotkeys.HotkeyManager()
        self.api = api_module.Api(self.cfg, self.engine, self.manager)
        self.engine.set_logger(self.api.log)

        # leitura de estado sai da ponte: ela nao aguenta 4 chamadas/s
        url, token, self._telemetry = telemetry_server.start({
            "poll": self.api.poll,
            "state": self.api.get_state,
        })
        self.api.bind_telemetry(url, token)

    def start(self):
        self.api.apply_hotkeys()
        self.engine.start()
        self.manager.start()
        self.api.log("Pronto. Calibre as skills e ligue o master (padrão F5).")

    def shutdown(self):
        self.engine.shutdown()
        self.manager.stop()
        self._telemetry.shutdown()
        self._telemetry.server_close()
        self._config.save(self.cfg)


def _open_window(core, index):
    """Cria a janela e liga os eventos ao nucleo."""
    import webview

    width, height = WINDOW_SIZE
    window = webview.create_window(
        WINDOW_TITLE, url=index, js_api=core.api,
        width=width, height=height, min_size=WINDOW_MIN_SIZE,
        background_color=WINDOW_BACKGROUND,
        hidden="--selftest" in sys.argv,
    )
    # a janela vai para dentro da Api como atributo privado de proposito:
    # publica, o pywebview desceria nela e travaria a ponte (ver api.Api)
    core.api.bind_window(window, _start_splash_closer(core.api.log))
    window.events.closed += core.shutdown
    return window


def _webview_options():
    """http_server serve `ui/out` em localhost para o Next achar /_next/..."""
    options = {"http_server": True}
    icon = _bundled(ICON)
    if os.path.exists(icon):
        options["icon"] = icon
    return options


# ------------------------------------------------------------------ selftest
def _selftest(window, index):
    """Confere se a interface carregou e grava selftest.json.

    Serve para diagnosticar o empacotamento, onde nao da para inspecionar a
    janela por fora (o exe roda elevado e o Windows bloqueia a captura).
    """
    import json
    import threading
    import time

    import config

    # BASE_DIR aponta para a pasta do exe (ou do codigo); a pasta do
    # sys.executable e somente leitura quando rodamos pelo Python instalado.
    destino = os.path.join(config.BASE_DIR, "selftest.json")

    def verificar_telemetria():
        # evaluate_js returns Promise objects before they resolve; keep a result
        # in the page and read it after the HTTP request actually completes.
        window.evaluate_js(
            "window.__botSelftest = null;"
            "window.pywebview.api.get_endpoint().then(async endpoint => {"
            "const response = await fetch(endpoint.url + '/state?t=' + endpoint.token);"
            "const state = await response.json();"
            "window.__botSelftest = response.ok && !!state.autoSlots && !!state.secondary;"
            "}).catch(() => { window.__botSelftest = false; });")
        for _attempt in range(30):
            result = window.evaluate_js("window.__botSelftest")
            if isinstance(result, bool):
                return result
            time.sleep(0.1)
        return False

    def medir():
        return {
            "index": index,
            "frozen": bool(getattr(sys, "frozen", False)),
            "bridge": window.evaluate_js("typeof window.pywebview"),
            "url": window.evaluate_js("location.href"),
            "body": window.evaluate_js("document.body.innerText.slice(0,400)"),
              "styled": window.evaluate_js(
                  "getComputedStyle(document.body).backgroundColor"),
              "telemetry_ok": verificar_telemetria(),
        }

    def gravar(relatorio):
        try:
            with open(destino, "w", encoding="utf-8") as arquivo:
                json.dump(relatorio, arquivo, indent=2, ensure_ascii=False,
                          default=str)
        except OSError as exc:
            print(f"selftest: não foi possível gravar {destino}: {exc}")

    def rodar():
        relatorio = {"index": index}
        try:
            time.sleep(SELFTEST_DELAY)
            relatorio = medir()
        except Exception as exc:                       # noqa: BLE001
            relatorio["error"] = repr(exc)
        finally:
            gravar(relatorio)
            os._exit(0)   # o servidor http do pywebview impede a saida normal

    threading.Thread(target=rodar, daemon=True).start()


def main():
    import crash_log
    crash_log.install()

    testing = "--selftest" in sys.argv
    instance = None if testing else _claim_single_instance()
    if not testing and instance is None:
        return
    if not _dependencies_ready():
        return

    import input_sender
    input_sender.set_dpi_aware()
    if not testing and _handed_over_to_elevated(instance, input_sender):
        return

    index = _locate_ui()
    if index is None:
        return

    core = _Core()
    # Diagnostics never start workers or register global game hotkeys.
    if not testing:
        core.start()
    crash_log.note(f"Bot iniciado (frozen={bool(getattr(sys, 'frozen', False))}).")
    window = _open_window(core, index)
    if "--selftest" in sys.argv:
        _selftest(window, index)

    import webview
    try:
        webview.start(**_webview_options())
    except Exception:                                  # noqa: BLE001
        import traceback
        crash_log.note("webview.start morreu:" + chr(10) + traceback.format_exc())
        raise
    crash_log.note("Bot encerrado normalmente.")


if __name__ == "__main__":
    main()
