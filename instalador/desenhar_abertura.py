"""Desenha a imagem da tela de abertura do .exe (instalador/abertura.png).

A tela de abertura aparece logo no clique, enquanto o .exe se descompacta (~2 s), e some quando a
janela do programa termina de carregar (web/app.py). Segue o tema do programa: uma lousa com moldura
de madeira, o leque de cartas em giz colorido e o nome na letra de giz (Caveat, a mesma da página).
Rodar de novo ao mudar nome, cores ou desenho:
    py instalador/desenhar_abertura.py      (precisa do Pillow: py -m pip install pillow)
"""

import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
SAIDA = os.path.join(AQUI, "abertura.png")
FONTE_GIZ = os.path.join(RAIZ, "buscador", "web", "pagina", "fontes", "caveat.woff2")
L, A = 520, 300
ESCALA = 3  # desenha maior e reduz no fim, para as bordas ficarem lisas

MADEIRA, MADEIRA_ESCURA, MADEIRA_FRISO = "#6b3f22", "#4a2a15", "#74462a"
LOUSA, GIZ = "#22362b", (241, 240, 232)
CARTAS = [((127, 178, 232), -16), ((242, 163, 107), 0), ((134, 214, 166), 16)]  # giz azul, laranja e verde
MOLDURA = 14


def s(v):
    return int(v * ESCALA)


def fonte_giz(tamanho, negrito=True):
    try:
        f = ImageFont.truetype(FONTE_GIZ, s(tamanho))
        f.set_variation_by_name("Bold" if negrito else "Regular")
        return f
    except (OSError, ValueError):
        return ImageFont.load_default()


def carta(cor):
    """Uma carta desenhada a giz: contorno colorido, arte hachurada e linhas de texto."""
    w, h = s(74), s(104)
    img = Image.new("RGBA", (w + s(8), h + s(8)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    o = s(4)
    d.rounded_rectangle((o, o, o + w, o + h), s(8), fill=LOUSA, outline=cor + (255,), width=s(4))
    # arte: hachuras diagonais na cor do giz
    x0, y0, x1, y1 = o + s(10), o + s(20), o + w - s(10), o + s(52)
    arte = Image.new("RGBA", img.size, (0, 0, 0, 0))
    da = ImageDraw.Draw(arte)
    for k in range(-s(40), s(80), s(5)):
        da.line((x0 + k, y1, x0 + k + s(30), y0), fill=cor + (215,), width=s(2))
    mascara = Image.new("L", img.size, 0)
    ImageDraw.Draw(mascara).rectangle((x0, y0, x1, y1), fill=255)
    img.paste(arte, (0, 0), ImageChops.multiply(mascara, arte.getchannel("A")))
    d.rectangle((x0, y0, x1, y1), outline=cor + (230,), width=s(1.5))
    # título e linhas de texto em giz branco
    d.line((o + s(11), o + s(12), o + w - s(26), o + s(12)), fill=GIZ + (210,), width=s(3))
    for i in range(3):
        y = o + s(62 + i * 10)
        d.line((o + s(11), y, o + w - s(11 + 14 * (i == 2)), y), fill=GIZ + (140,), width=s(2))
    return img


def granular(camada, semente=7):
    """Deixa o traço com cara de giz: falhas pequenas e aleatórias na transparência."""
    rnd = random.Random(semente)
    ruido = Image.new("L", camada.size)
    ruido.putdata([rnd.randint(150, 255) for _ in range(camada.size[0] * camada.size[1])])
    camada.putalpha(ImageChops.multiply(camada.getchannel("A"), ruido))
    return camada


def main():
    img = Image.new("RGBA", (s(L), s(A)), MADEIRA)
    d = ImageDraw.Draw(img)
    # moldura de madeira, com frisos
    for y in range(0, s(A), s(8)):
        d.line((0, y, s(L), y), fill=MADEIRA_FRISO, width=s(1.5))
    # lousa, com manchas leves de giz apagado
    d.rectangle((s(MOLDURA), s(MOLDURA), s(L - MOLDURA), s(A - MOLDURA)), fill=LOUSA,
                outline=MADEIRA_ESCURA, width=s(2))
    manchas = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dm = ImageDraw.Draw(manchas)
    for cx, cy, r in ((150, 90, 120), (380, 220, 110)):
        for k in range(10):
            rr = s(r * (1 - k / 10))
            dm.ellipse((s(cx) - rr, s(cy) - rr * 0.7, s(cx) + rr, s(cy) + rr * 0.7), fill=(255, 255, 255, 2))
    img.alpha_composite(manchas)

    giz = Image.new("RGBA", img.size, (0, 0, 0, 0))  # tudo que é "escrito a giz" vai nesta camada
    centro_x, base_y = s(150), s(150)
    for cor, ang in CARTAS:
        c = carta(cor).rotate(-ang, resample=Image.BICUBIC, expand=True)
        dx = int(ang * 2.2 * ESCALA)
        giz.alpha_composite(c, (centro_x - c.width // 2 + dx, base_y - c.height // 2 + abs(ang) // 2 * ESCALA))

    dg = ImageDraw.Draw(giz)
    lx, ly, lr = s(196), s(178), s(22)  # lupa sobre o leque
    dg.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=(34, 54, 43, 170))
    dg.line((lx + lr * 0.7, ly + lr * 0.7, lx + lr * 1.75, ly + lr * 1.75), fill=GIZ + (255,), width=s(8))
    dg.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), outline=GIZ + (255,), width=s(5))

    x = s(262)
    dg.text((x, s(86)), "BuscaCartas", font=fonte_giz(48), fill=GIZ + (255,))
    dg.text((x + s(4), s(136)), "do Boteco", font=fonte_giz(40), fill=GIZ + (235,))
    dg.text((x + s(4), s(196)), "Abrindo o boteco…", font=fonte_giz(22, negrito=False), fill=GIZ + (160,))
    img.alpha_composite(granular(giz))

    img = img.resize((L, A), Image.LANCZOS).convert("RGB")
    img.save(SAIDA)
    print("ok:", SAIDA)


if __name__ == "__main__":
    main()
