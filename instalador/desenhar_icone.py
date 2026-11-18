"""Desenha o ícone do programa (instalador/icone.ico), usado no .exe e na barra de tarefas.

Mesmo tema da tela de abertura (desenhar_abertura.py): uma lousa com moldura de madeira, o leque de
três cartas em giz colorido e a lupa a giz. O .ico leva vários tamanhos; nos pequenos (16 e 24 px,
os da barra de tarefas e do Explorer em lista) o desenho é simplificado, com traços mais grossos e
sem a arte hachurada, para não virar borrão.
Rodar de novo ao mudar o desenho:
    py instalador/desenhar_icone.py      (precisa do Pillow: py -m pip install pillow)
"""

import os

from PIL import Image, ImageChops, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "icone.ico")
TAMANHOS = [16, 24, 32, 48, 64, 128, 256]
BASE = 1024  # desenha grande e reduz, para as bordas ficarem lisas

MADEIRA, MADEIRA_ESCURA, MADEIRA_FRISO = (107, 63, 34), (74, 42, 21), (122, 75, 44)
LOUSA, GIZ = (34, 54, 43), (241, 240, 232)
CORES = [(127, 178, 232), (242, 163, 107), (134, 214, 166)]  # giz azul, laranja e verde


def carta(cor, w, h, detalhe):
    """Uma carta a giz: contorno colorido, arte (hachurada ou cheia) e linhas de texto."""
    borda = int(w * (0.075 if detalhe else 0.13))
    img = Image.new("RGBA", (w + borda * 2, h + borda * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    o = borda
    d.rounded_rectangle((o, o, o + w, o + h), int(w * 0.11), fill=LOUSA + (255,), outline=cor + (255,), width=borda)
    x0, y0, x1, y1 = o + w * 0.17, o + h * 0.2, o + w * 0.83, o + h * 0.52
    if detalhe:
        arte = Image.new("RGBA", img.size, (0, 0, 0, 0))
        da = ImageDraw.Draw(arte)
        passo = max(2, int(w * 0.075))
        for k in range(-int(h), int(w * 2), passo):
            da.line((x0 + k, y1, x0 + k + (y1 - y0), y0), fill=cor + (220,), width=max(1, int(w * 0.03)))
        mascara = Image.new("L", img.size, 0)
        ImageDraw.Draw(mascara).rectangle((x0, y0, x1, y1), fill=255)
        img.paste(arte, (0, 0), ImageChops.multiply(mascara, arte.getchannel("A")))
        d.rectangle((x0, y0, x1, y1), outline=cor + (240,), width=max(1, int(w * 0.025)))
        for i in range(3):
            y = o + h * (0.63 + i * 0.1)
            d.line((o + w * 0.17, y, o + w * (0.83 - 0.2 * (i == 2)), y), fill=GIZ + (170,), width=max(1, int(w * 0.035)))
    else:
        d.rectangle((x0, y0, x1, y1), fill=cor + (255,))
        d.line((o + w * 0.2, o + h * 0.7, o + w * 0.8, o + h * 0.7), fill=GIZ + (230,), width=max(1, int(w * 0.09)))
    return img


def desenhar(lado, detalhe=True):
    """O ícone num quadrado de `lado` px (desenhado em BASE e reduzido depois)."""
    S = BASE
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    raio = int(S * 0.16)
    moldura = int(S * (0.07 if detalhe else 0.085))
    # moldura de madeira, com frisos
    d.rounded_rectangle((0, 0, S - 1, S - 1), raio, fill=MADEIRA + (255,))
    if detalhe:
        frisos = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        df = ImageDraw.Draw(frisos)
        for y in range(0, S, int(S * 0.035)):
            df.line((0, y, S, y), fill=MADEIRA_FRISO + (255,), width=int(S * 0.006))
        mascara = Image.new("L", (S, S), 0)
        ImageDraw.Draw(mascara).rounded_rectangle((0, 0, S - 1, S - 1), raio, fill=255)
        img.paste(frisos, (0, 0), ImageChops.multiply(mascara, frisos.getchannel("A")))
    # lousa
    d.rounded_rectangle((moldura, moldura, S - moldura, S - moldura), int(raio * 0.55), fill=LOUSA + (255,),
                        outline=MADEIRA_ESCURA + (255,), width=int(S * 0.012))

    # leque de três cartas
    w, h = int(S * 0.33), int(S * 0.46)
    cx, cy = S * 0.47, S * 0.47
    for cor, ang in zip(CORES, (-18, 0, 18)):
        c = carta(cor, w, h, detalhe).rotate(-ang, resample=Image.BICUBIC, expand=True)
        dx = ang * S * 0.0085
        dy = abs(ang) * S * 0.002
        img.alpha_composite(c, (int(cx - c.width / 2 + dx), int(cy - c.height / 2 + dy)))

    # lupa a giz, no canto de baixo à direita
    d = ImageDraw.Draw(img)
    lx, ly, lr = S * 0.63, S * 0.64, S * (0.13 if detalhe else 0.15)
    traco = int(S * (0.04 if detalhe else 0.065))
    d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), fill=LOUSA + (200,))
    d.line((lx + lr * 0.7, ly + lr * 0.7, lx + lr * 1.75, ly + lr * 1.75), fill=GIZ + (255,), width=int(traco * 1.5))
    d.ellipse((lx - lr, ly - lr, lx + lr, ly + lr), outline=GIZ + (255,), width=traco)
    return img.resize((lado, lado), Image.LANCZOS)


def main():
    imagens = [desenhar(t, detalhe=t >= 32) for t in TAMANHOS]
    grande = imagens[-1]
    # o Pillow monta o .ico a partir da maior imagem e das outras dadas em append_images
    grande.save(SAIDA, format="ICO", sizes=[(t, t) for t in TAMANHOS], append_images=imagens[:-1])
    print("ok:", SAIDA)


if __name__ == "__main__":
    main()
