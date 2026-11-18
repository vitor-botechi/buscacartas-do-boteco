"""Desenha a imagem da tela de abertura do .exe (instalador/abertura.png).

A tela de abertura aparece logo no clique, enquanto o .exe se descompacta (~2 s), e some quando a
janela do programa termina de carregar (web/app.py). Rodar de novo ao mudar nome, cores ou desenho:
    py instalador/desenhar_abertura.py      (precisa do Pillow: py -m pip install pillow)
"""

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "abertura.png")
L, A = 520, 300
ESCALA = 3  # desenha maior e reduz no fim, para as bordas ficarem lisas

VERDE, VERDE_ESCURO, FUNDO, TEXTO, CINZA = "#16794f", "#0f5a3a", "#f6f7f9", "#1d2733", "#6b7785"
CARTAS = [("#1e4f8a", -16), ("#c2410c", 0), ("#16794f", 16)]  # cor e inclinação de cada carta do leque


def fonte(tamanho, negrito=False):
    nome = "segoeuib.ttf" if negrito else "segoeui.ttf"
    try:
        return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", nome), tamanho * ESCALA)
    except OSError:
        return ImageFont.load_default()


def carta(cor):
    """Uma carta: moldura colorida, área da arte e linhas de texto (sem imitar o verso oficial)."""
    w, h = 74 * ESCALA, 104 * ESCALA
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = 8 * ESCALA
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=cor)
    m = 6 * ESCALA
    d.rounded_rectangle((m, m, w - m, h - m), r // 2, fill="#fbfaf7")
    d.rectangle((m + 4 * ESCALA, m + 14 * ESCALA, w - m - 4 * ESCALA, m + 50 * ESCALA), fill=cor)
    for i in range(3):
        y = m + (58 + i * 9) * ESCALA
        d.rounded_rectangle((m + 5 * ESCALA, y, w - m - (5 + 12 * (i == 2)) * ESCALA, y + 3 * ESCALA), ESCALA, fill="#d6dbe1")
    d.rounded_rectangle((m + 5 * ESCALA, m + 4 * ESCALA, w - m - 20 * ESCALA, m + 9 * ESCALA), ESCALA, fill="#c9ced6")
    return img


def main():
    img = Image.new("RGBA", (L * ESCALA, A * ESCALA), FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, L * ESCALA, 6 * ESCALA), fill=VERDE)  # faixa verde no alto, como o botão Buscar

    # leque de cartas, com sombra leve
    centro_x, base_y = 150 * ESCALA, 150 * ESCALA
    for cor, ang in CARTAS:
        c = carta(cor).rotate(-ang, resample=Image.BICUBIC, expand=True)
        sombra = Image.new("RGBA", c.size, (0, 0, 0, 0))
        sombra.paste((0, 0, 0, 60), mask=c.split()[3])
        sombra = sombra.filter(ImageFilter.GaussianBlur(5 * ESCALA))
        dx = int(ang * 2.2 * ESCALA)
        pos = (centro_x - c.width // 2 + dx, base_y - c.height // 2 + abs(ang) // 2 * ESCALA)
        img.alpha_composite(sombra, (pos[0] + 2 * ESCALA, pos[1] + 5 * ESCALA))
        img.alpha_composite(c, pos)

    # lupa sobre o leque
    lx, ly, lr = 196 * ESCALA, 178 * ESCALA, 22 * ESCALA
    d = ImageDraw.Draw(img)
    d.line((lx + lr * 0.7, ly + lr * 0.7, lx + lr * 1.75, ly + lr * 1.75), fill=TEXTO, width=9 * ESCALA)
    d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(255, 255, 255, 170), outline=TEXTO, width=6 * ESCALA)

    # textos
    x = 270 * ESCALA
    d.text((x, 104 * ESCALA), "BuscaCartas", font=fonte(30, True), fill=TEXTO)
    d.text((x, 140 * ESCALA), "do Boteco", font=fonte(30, True), fill=VERDE_ESCURO)
    d.text((x, 188 * ESCALA), "Abrindo o boteco…", font=fonte(13), fill=CINZA)

    d.rectangle((0, 0, L * ESCALA - 1, A * ESCALA - 1), outline="#c9ced6", width=ESCALA)  # borda: a tela não tem moldura
    img = img.resize((L, A), Image.LANCZOS).convert("RGB")
    img.save(SAIDA)
    print("ok:", SAIDA)


if __name__ == "__main__":
    main()
