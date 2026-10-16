"""Gera o executavel (dist/TroveAutoBot.exe).

Compila a interface Next.js e empacota tudo com o PyInstaller.

Uso: python build.py            (build completo)
     python build.py --skip-ui  (reaproveita o ui/out ja compilado)
"""

import os
import shutil
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UI_DIR = os.path.join(BASE_DIR, "ui")
UI_OUT = os.path.join(UI_DIR, "out")
ASSETS = os.path.join(BASE_DIR, "assets")
NAME = "TroveAutoBot"


def pyinstaller_options(icon, splash):
    options = [
        "--noconfirm",
        "--clean",
        # onedir, nao onefile: o onefile extrai ~66 MB para o TEMP a cada
        # abertura, o que custava ~3,5s de tela preta antes da janela aparecer.
        "--onedir",
        "--windowed",             # GUI: sem janela de console
        "--uac-admin",            # pede elevacao no arranque (UIPI/SendInput)
        f"--name={NAME}",
        # a interface compilada vai junto e e servida pelo pywebview
        f"--add-data={UI_OUT}{os.pathsep}ui/out",
        f"--add-data={ASSETS}{os.pathsep}assets",
        f"--add-data={os.path.join(BASE_DIR, 'LICENSE')}{os.pathsep}licenses",
        f"--add-data={os.path.join(BASE_DIR, 'THIRD_PARTY_NOTICES.md')}{os.pathsep}licenses",
        # importados sob demanda, o PyInstaller nao os enxerga sozinho
        "--hidden-import=setup_window",
        "--hidden-import=single_instance",
        "--hidden-import=crash_log",
        "--hidden-import=telemetry_server",
        "--hidden-import=webview.platforms.edgechromium",
        "--exclude-module=pytest",
        "--exclude-module=matplotlib",
        "--exclude-module=tkinter.test",
    ]
    if icon:
        # --icon veste o exe; o --add-data leva o mesmo .ico para a janela
        options += [f"--icon={icon}"]
    if splash:
        # feedback imediato: aparece assim que o usuario clica
        options += [f"--splash={splash}"]
    return options


def run(command, cwd=None):
    print(">", " ".join(command))
    # Resolve npm.cmd explicitly; Python and PyInstaller never need a shell.
    executable = shutil.which(command[0]) or command[0]
    return subprocess.call([executable, *command[1:]], cwd=cwd)


def build_ui():
    if not os.path.isdir(os.path.join(UI_DIR, "node_modules")):
        print("Instalando dependencias da interface...")
        if run(["npm", "ci"], cwd=UI_DIR) != 0:
            return False
    print("Compilando a interface Next.js...")
    return run(["npm", "run", "build"], cwd=UI_DIR) == 0


def _pyinstaller_available():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller nao instalado. Rode: pip install pyinstaller")
        return False
    return True


def _ui_ready():
    """Compila a interface (a menos que --skip-ui) e confere a saida."""
    if "--skip-ui" not in sys.argv and not build_ui():
        print("Falha ao compilar a interface.")
        return False
    if not os.path.isdir(UI_OUT):
        print(f"Interface nao encontrada em {UI_OUT}. Rode sem --skip-ui.")
        return False
    return True


def _build_assets():
    """Gera icone e tela de abertura a partir de assets/logo.png."""
    import make_icon
    icon = make_icon.build()
    if not icon:
        print("Seguindo sem icone personalizado.")
    return icon, make_icon.build_splash()


def _package(icon, splash):
    """Roda o PyInstaller. Devolve a pasta gerada, ou None se falhou."""
    command = [sys.executable, "-m", "PyInstaller"]
    command += pyinstaller_options(icon, splash)
    command += [os.path.join(BASE_DIR, "main.py")]
    if run(command, cwd=BASE_DIR) != 0:
        return None

    app_dir = os.path.join(BASE_DIR, "dist", NAME)      # onedir
    if not os.path.exists(os.path.join(app_dir, NAME + ".exe")):
        print("Build terminou mas o exe nao foi encontrado.")
        return None
    return app_dir


def main():
    if not _pyinstaller_available() or not _ui_ready():
        return 1

    app_dir = _package(*_build_assets())
    if app_dir is None:
        return 1

    exe = os.path.join(app_dir, NAME + ".exe")
    print()
    print(f"Pronto: {exe}")
    print(f"Distribua a pasta inteira: {app_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
