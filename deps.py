"""Checagem e instalacao das dependencias (usa so a stdlib).

Este modulo nao pode importar cv2/mss/pynput: ele precisa funcionar justamente
quando esses pacotes ainda nao existem.
"""

import importlib.util
import os
import subprocess
import sys

# (modulo importavel, nome no pip)
REQUIRED = [
    ("webview", "pywebview"),
    ("cv2", "opencv-python"),
    ("numpy", "numpy"),
    ("mss", "mss"),
    ("pynput", "pynput"),
]


def is_frozen():
    return getattr(sys, "frozen", False)


def missing():
    """Pacotes do pip que faltam. No exe nunca falta nada (vem embutido)."""
    if is_frozen():
        return []
    return [pkg for module, pkg in REQUIRED
            if importlib.util.find_spec(module) is None]


def _pip_command(base_dir):
    """Monta a linha do pip: requirements.txt se existir, senao a lista fixa."""
    base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
    req = os.path.join(base_dir, "requirements.txt")
    command = [sys.executable, "-m", "pip", "install"]
    if os.path.exists(req):
        return command + ["-r", req]
    return command + [pacote for _modulo, pacote in REQUIRED]


def _run_pip(command, log):
    """Roda o pip repassando cada linha da saida. Devolve o codigo de saida."""
    try:
        processo = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for linha in processo.stdout:
            linha = linha.rstrip()
            if linha:
                log("  pip| " + linha[:110])
        return processo.wait()
    except OSError as exc:
        log(f"Falha ao rodar o pip: {exc}")
        return -1


def install(log, base_dir=None):
    """Instala as dependencias que faltam. Devolve o codigo de saida do pip."""
    if is_frozen():
        log("Executável: dependências já embutidas, nada a instalar.")
        return 0

    command = _pip_command(base_dir)
    log("Instalando: " + " ".join(command[2:]))

    code = _run_pip(command, log)
    log("Dependências instaladas." if code == 0
        else f"pip terminou com erro (código {code}).")
    return code
