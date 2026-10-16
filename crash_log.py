"""Registra qualquer morte do bot em `crash.log`, ao lado do executavel.

O app roda com `--windowed`: sem console, uma excecao ou um crash nativo
fechariam a janela sem deixar rastro nenhum. Aqui cobrimos os tres casos:

* excecao na thread principal      -> sys.excepthook
* excecao numa thread do bot       -> threading.excepthook (senao a rotina
                                      morre calada e o bot "para sozinho")
* crash nativo (access violation)  -> faulthandler, que imprime a pilha
                                      Python mesmo quando o processo morre
                                      dentro de uma DLL
"""

import datetime
import faulthandler
import os
import sys
import threading
import traceback

import config

CRASH_LOG = os.path.join(config.BASE_DIR, "crash.log")

_file = None


def _write(titulo, texto):
    try:
        with open(CRASH_LOG, "a", encoding="utf-8") as arquivo:
            quando = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            arquivo.write(f"\n{'=' * 60}\n{quando}  {titulo}\n{'=' * 60}\n")
            arquivo.write(texto)
            arquivo.write("\n")
    except OSError:
        pass          # sem disco/permissao: nao ha mais o que fazer aqui


def _on_exception(exc_type, exc_value, exc_tb):
    _write("EXCECAO NA THREAD PRINCIPAL",
           "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _on_thread_exception(args):
    nome = getattr(args.thread, "name", "?")
    _write(f"EXCECAO NA THREAD {nome}",
           "".join(traceback.format_exception(
               args.exc_type, args.exc_value, args.exc_traceback)))


def install():
    """Liga os tres coletores. Devolve o caminho do log."""
    global _file
    sys.excepthook = _on_exception
    threading.excepthook = _on_thread_exception
    try:
        # mantido aberto: o faulthandler escreve nele no momento do crash
        _file = open(CRASH_LOG, "a", encoding="utf-8", buffering=1)
        faulthandler.enable(file=_file, all_threads=True)
    except OSError:
        faulthandler.enable(all_threads=True)
    return CRASH_LOG


def note(mensagem):
    """Registra um marco (inicio, fim) para dar contexto ao crash."""
    _write("NOTA", mensagem)
