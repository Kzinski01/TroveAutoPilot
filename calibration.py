"""Regras de calibracao (skills e templates), sem dependencia de interface."""

import os
import time

import cv2

import config
import vision

SAMPLES = 8
SAMPLE_DELAY = 0.06

READY = "ready"
COOLDOWN = "cooldown"


def sample_scores(region, samples=SAMPLES, delay=SAMPLE_DELAY):
    """Varias leituras do icone: uma so engana, porque o icone pulsa."""
    scores = []
    for index in range(samples):
        scores.append(vision.icon_score(vision.grab(region)))
        if index < samples - 1:
            time.sleep(delay)
    return scores


def _record_sample(skill, state, scores):
    """Grava a amostra no slot e devolve (score usado, minimo, maximo).

    'Pronta' usa o piso da oscilacao e 'em cooldown' o teto, para o limite
    cair fora da faixa de ruido dos dois estados.
    """
    menor, maior = min(scores), max(scores)
    score = menor if state == READY else maior
    skill["ready_score" if state == READY else "cooldown_score"] = score
    return score, menor, maior


def _threshold_hint(skill):
    """Sugere um limite a partir dos dois estados, **sem aplicar**.

    Quem decide o limite e o usuario, na caixa da aba Skills. A sugestao fica
    no log so como ponto de partida.
    """
    sugestao = vision.auto_threshold(skill.get("ready_score", 0.0),
                                     skill.get("cooldown_score", 0.0))
    if sugestao is not None:
        return (f"  -> sugestao de limite: {sugestao:.2f} "
                f"(atual: {float(skill.get('threshold', 0.8)):.2f}). "
                "Ajuste na caixa 'Limite' se quiser.")
    if not skill.get("ready_score"):
        return "  -> capture o estado 'Pronta': e a base do ratio."
    if not skill.get("cooldown_score"):
        return ("  -> capture 'Em cooldown' se quiser uma sugestao de limite "
                "(opcional).")
    return ("  ! o cooldown não ficou mais escuro que o estado pronto, "
            "entao nao da para sugerir limite. Confira a area do icone.")


def apply_skill_sample(skill, state, scores):
    """Grava a amostra medida e devolve as linhas de log.

    O limite nao e mexido aqui: quem define e o usuario, na caixa da aba
    Skills. A calibracao so mede e sugere.
    """
    if not scores:
        return ["Nenhuma amostra capturada."]

    score, menor, maior = _record_sample(skill, state, scores)
    rotulo = "PRONTA" if state == READY else "COOLDOWN"
    return [
        f"Skill {skill['name']} [{rotulo}]: {score:.3f} "
        f"(oscilou {menor:.3f}-{maior:.3f})",
        _threshold_hint(skill),
    ]


def save_template(name, image):
    """Grava o recorte em templates/ e devolve o nome relativo do arquivo."""
    os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
    filename = f"{name}.png"
    cv2.imwrite(os.path.join(config.TEMPLATE_DIR, filename), image)
    return filename


def click_offset(template_region, point):
    """Deslocamento do centro do template ate o ponto a clicar."""
    x, y, width, height = template_region
    return [point[0] - (x + width // 2), point[1] - (y + height // 2)]
