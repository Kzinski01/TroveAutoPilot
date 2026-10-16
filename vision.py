"""Captura de tela e analise de imagem: cooldown de skills e deteccao de janelas."""

import collections
import queue
import threading

import cv2
import mss
import numpy as np

# Um acerto do matchTemplate: centro do trecho encontrado e a confianca.
Match = collections.namedtuple("Match", "x y score")

# ---------------------------------------------------------------- captura
# Toda captura acontece nesta thread, e so nela.
#
# O mss guarda recursos do Windows (device context e DIB) que precisam ser
# devolvidos pela mesma thread que os criou. Antes havia uma instancia por
# thread: as chamadas da ponte rodam numa thread nova a cada vez, entao esses
# objetos ficavam orfaos e quem os finalizava era o coletor de lixo, numa
# thread qualquer. Isso corrompia a heap e o processo morria com
# STATUS_BREAKPOINT no meio de uma coleta - sempre em quem estivesse alocando
# na hora, o que fazia o crash parecer vir de lugares diferentes.
#
# Com uma unica instancia permanente nao existe mais nada para finalizar.

_pedidos = queue.Queue()
_worker = None
_worker_lock = threading.Lock()


class _Pedido:
    """Um trabalho enviado a thread de captura e o lugar para a resposta."""

    __slots__ = ("funcao", "valor", "erro", "pronto")

    def __init__(self, funcao):
        self.funcao = funcao
        self.valor = None
        self.erro = None
        self.pronto = threading.Event()


def _servir_capturas():
    sct = None
    while True:
        pedido = _pedidos.get()
        try:
            # Initialization errors must reach the caller, not strand its wait.
            if sct is None:
                sct = mss.MSS()
            pedido.valor = pedido.funcao(sct)
        except Exception as exc:                       # noqa: BLE001
            pedido.erro = exc
        finally:
            pedido.pronto.set()


def _no_capturador(funcao):
    """Roda `funcao(sct)` na thread de captura e devolve o resultado."""
    global _worker
    if _worker is None:
        with _worker_lock:
            if _worker is None:
                _worker = threading.Thread(target=_servir_capturas,
                                           name="captura", daemon=True)
                _worker.start()
    pedido = _Pedido(funcao)
    _pedidos.put(pedido)
    if not pedido.pronto.wait(timeout=10):
        raise TimeoutError("A captura de tela não respondeu em 10 segundos")
    if pedido.erro is not None:
        raise pedido.erro
    return pedido.valor


def grab(region):
    """Captura uma regiao (x, y, w, h) e devolve BGR (numpy)."""
    x, y, w, h = [int(v) for v in region]
    if w <= 0 or h <= 0:
        return None
    caixa = {"left": x, "top": y, "width": w, "height": h}
    shot = _no_capturador(lambda sct: np.asarray(sct.grab(caixa)))
    return shot[:, :, :3].copy()      # BGRA -> BGR


def grab_screen():
    """Captura o monitor principal. Devolve (BGR, offset_x, offset_y)."""
    def captura(sct):
        monitor = sct.monitors[1]
        return np.asarray(sct.grab(monitor)), monitor["left"], monitor["top"]

    frame, left, top = _no_capturador(captura)
    return frame[:, :, :3].copy(), left, top


def icon_score(image):
    """Pontuacao 0..1 de quao 'acesa' esta uma skill.

    Icone pronto = brilhante e colorido. Em cooldown o Trove escurece e
    dessatura o icone, entao brilho + saturacao caem juntos.
    """
    if image is None or image.size == 0:
        return 0.0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0
    value = float(np.mean(hsv[:, :, 2])) / 255.0
    return 0.65 * value + 0.35 * saturation


def skill_ratio(skill):
    """Razao entre a pontuacao atual e a pontuacao calibrada de 'pronto'."""
    region = skill.get("region")
    ready = float(skill.get("ready_score") or 0.0)
    if not region or ready <= 0.001:
        return None
    frame = grab(region)
    if frame is None:
        return None
    return icon_score(frame) / ready


def is_ready(skill):
    ratio = skill_ratio(skill)
    if ratio is None:
        return False
    return ratio >= float(skill.get("threshold", 0.80))


def auto_threshold(ready_score, cooldown_score):
    """Limite no meio do caminho entre 'em cooldown' e 'pronto'.

    Os icones do Trove pulsam, entao o ratio de uma skill pronta oscila bastante;
    um limite colado em 1.0 cai dentro desse ruido e a skill nunca dispara.
    """
    if ready_score <= 0.001 or cooldown_score <= 0.0:
        return None
    if cooldown_score >= ready_score:
        return None       # estados invertidos ou area sem contraste util
    midpoint = (ready_score + cooldown_score) / 2.0
    return round(max(0.30, min(midpoint / ready_score, 0.97)), 3)


MIN_TEMPLATE_STD = 3.0


def has_texture(image):
    """Um recorte liso casa em qualquer lugar no TM_CCOEFF_NORMED.

    Sem variacao a correlacao normalizada divide por ~zero e devolve score 1.0
    na primeira posicao testada, causando cliques aleatorios. O que importa e a
    variacao espacial (textura), nao a diferenca entre os canais de cor: uma
    area de cor solida e lisa mesmo sendo bem colorida.
    """
    if image is None or image.size == 0:
        return False
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray)) >= MIN_TEMPLATE_STD


def load_template(path):
    if not path:
        return None
    template = cv2.imread(path, cv2.IMREAD_COLOR)
    if template is None or not template.size:
        return None
    return template if has_texture(template) else None


def find_template(template, confidence=0.80, region=None):
    """Procura o template na tela. Devolve um `Match` ou None."""
    if template is None:
        return None
    if region:
        haystack = grab(region)
        off_x, off_y = int(region[0]), int(region[1])
    else:
        haystack, off_x, off_y = grab_screen()
    if haystack is None:
        return None
    th, tw = template.shape[:2]
    hh, hw = haystack.shape[:2]
    if th > hh or tw > hw:
        return None

    correlation = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, best_score, _, best_corner = cv2.minMaxLoc(correlation)
    if best_score < confidence:
        return None
    return Match(x=off_x + best_corner[0] + tw // 2,
                 y=off_y + best_corner[1] + th // 2,
                 score=float(best_score))
