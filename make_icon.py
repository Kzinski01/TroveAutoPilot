"""Gera assets/icon.ico e assets/splash.png a partir de assets/logo.png.

Chamado pelo build.py. O logo nao e quadrado, entao ele e centralizado numa
tela quadrada transparente: recortar ou esticar distorceria a arte.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(BASE_DIR, "assets", "logo.png")
ICON = os.path.join(BASE_DIR, "assets", "icon.ico")
SPLASH = os.path.join(BASE_DIR, "assets", "splash.png")

# o Windows escolhe o tamanho conforme o contexto (lista, area de trabalho...)
SIZES = [16, 24, 32, 48, 64, 128, 256]
MARGIN = 0.04          # respiro para a arte nao encostar na borda

SPLASH_SIZE = (420, 300)
SPLASH_BG = (9, 9, 11)          # --background do tema


def build(logo=LOGO, icon=ICON):
    """Devolve o caminho do .ico, ou None se nao for possivel gerar."""
    try:
        from PIL import Image
    except ImportError:
        print("Pillow nao instalado: pip install pillow")
        return None
    if not os.path.exists(logo):
        print(f"Logo nao encontrado em {logo}")
        return None

    source = Image.open(logo).convert("RGBA")
    side = max(source.size)
    padded = int(side * (1 + MARGIN * 2))

    canvas = Image.new("RGBA", (padded, padded), (0, 0, 0, 0))
    canvas.paste(source,
                 ((padded - source.width) // 2, (padded - source.height) // 2))

    os.makedirs(os.path.dirname(icon), exist_ok=True)
    largest = canvas.resize((256, 256), Image.LANCZOS)
    largest.save(icon, format="ICO", sizes=[(size, size) for size in SIZES])
    return icon


def build_splash(logo=LOGO, splash=SPLASH):
    """Imagem mostrada assim que o usuario clica, enquanto o app carrega."""
    try:
        from PIL import Image
    except ImportError:
        return None
    if not os.path.exists(logo):
        return None

    source = Image.open(logo).convert("RGBA")
    width, height = SPLASH_SIZE
    art = source.copy()
    art.thumbnail((int(width * 0.68), int(height * 0.68)), Image.LANCZOS)

    canvas = Image.new("RGB", SPLASH_SIZE, SPLASH_BG)
    canvas.paste(art, ((width - art.width) // 2, (height - art.height) // 2 - 14),
                 art)

    os.makedirs(os.path.dirname(splash), exist_ok=True)
    canvas.save(splash, format="PNG")
    return splash


if __name__ == "__main__":
    print(f"Icone: {build()}")
    print(f"Splash: {build_splash()}")
