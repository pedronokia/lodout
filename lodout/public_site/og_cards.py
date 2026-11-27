"""Imagens de prévia (Open Graph, 1200x630) pra quando um link do Lodout
é colado no Discord, WhatsApp, X etc.

- `cartao_padrao()`: marca oficial "Escura Alto Contraste" (sem TM),
  fundo do tema e texto curto em Outfit / Geist. Gera o
  `static/og-image.png` (via scripts/gerar_og_image.py) usado pelas
  páginas sem imagem própria.
- `cartao_item(...)`: um por item, com ícone, nome, nota, preço e a cor
  da raridade. Feito só com dado já guardado (scan + ícone já em cache
  local): gerar a prévia nunca consulta a Steam nem o CDN dela.

Pillow já é dependência do site (icon_cache.py); as fontes são as mesmas
que o site serve (static/fonts): Outfit no título e Geist no texto e
nos números (desde 27/11, como no site: sem a Geist Mono).
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lodout import _paths
from lodout._paths import atomic_write_bytes

LARGURA, ALTURA = 1200, 630
_FONTES = {
    "outfit": Path(__file__).parent / "static" / "fonts" / "outfit-latin.woff2",
    "geist": Path(__file__).parent / "static" / "fonts" / "geist-latin.woff2",
}

# Mesmas cores do tema (style.css :root e .raridade-*, .nota-*).
_FUNDO = (22, 22, 22)          # --bg #161616
_SUPERFICIE = (30, 30, 30)     # --surface #1e1e1e
_TEXTO = (255, 255, 255)
_TEXTO_FRACO = (179, 179, 179)  # --text-muted
_LARANJA = (249, 115, 22)      # --accent
_CORES_NOTA = {"alta": (57, 194, 102), "media": (242, 187, 37),
               "baixa": (179, 179, 179)}
_CORES_RARIDADE = {
    "consumer": (176, 195, 217), "industrial": (94, 152, 217),
    "milspec": (75, 105, 255), "restricted": (136, 71, 255),
    "classified": (211, 44, 230), "covert": (235, 75, 75),
    "dourado": (228, 174, 57),
}
# Cache em disco: ~185 itens x poucas dezenas de KB. Teto pra não
# acumular versões antigas (nota/preço mudam a cada coleta).
_CACHE_MAX_ARQUIVOS = 800


def _fonte(tamanho: int, peso: int = 400,
           familia: str = "geist") -> ImageFont.FreeTypeFont:
    """Fonte do cartão. Cada número aparece sozinho (nota, preço), então
    não precisa de algarismos tabulares."""
    f = ImageFont.truetype(str(_FONTES[familia]), tamanho)
    try:
        f.set_variation_by_axes([peso])
    except (OSError, ValueError):
        pass
    return f


def _quebrar(texto: str, fonte, largura_max: int, linhas_max: int) -> "list[str]":
    """Quebra por palavra; corta com reticências se passar de linhas_max."""
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if fonte.getlength(teste) <= largura_max:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = p
    if atual:
        linhas.append(atual)
    if len(linhas) > linhas_max:
        linhas = linhas[:linhas_max]
        ultima = linhas[-1]
        while ultima and fonte.getlength(ultima + "…") > largura_max:
            ultima = ultima[:-1]
        linhas[-1] = ultima.rstrip() + "…"
    return linhas


_LOGO = Path(__file__).parent / "static" / "logo-escura-og.png"
_SIMBOLO = Path(__file__).parent / "static" / "logo-L.png"


def _simbolo(img: Image.Image, x: int, y: int, altura: int,
             opacidade: float = 1.0) -> None:
    """Símbolo de reserva: inicial l do monograma do site (static/logo-L.svg
    em PNG transparente), usada só quando o item não tem ícone em cache.
    (x, y) é o canto de cima à esquerda e `altura` a altura em pixels."""
    simbolo = Image.open(_SIMBOLO).convert("RGBA")
    largura = round(simbolo.width * altura / simbolo.height)
    simbolo = simbolo.resize((largura, altura), Image.LANCZOS)
    if opacidade < 1:
        simbolo.putalpha(simbolo.getchannel("A").point(lambda a: round(a * opacidade)))
    img.paste(simbolo, (x, y), simbolo)


def _estrela(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float,
             cor) -> None:
    """★ desenhada (as fontes servidas pelo site não têm o glifo)."""
    import math
    pontos = []
    for i in range(10):
        raio = r if i % 2 == 0 else r * 0.45
        ang = -math.pi / 2 + i * math.pi / 5
        pontos.append((cx + raio * math.cos(ang), cy + raio * math.sin(ang)))
    d.polygon(pontos, fill=cor)


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def cartao_padrao() -> bytes:
    """Cartão padrão: fundo #161616, marca oficial sem TM, título curto
    em Outfit e uma linha de dados em Geist. Sem faixas ou
    brilhos: o texto e a marca são os únicos elementos."""
    img = Image.new("RGB", (LARGURA, ALTURA), _FUNDO)
    d = ImageDraw.Draw(img)
    logo = Image.open(_LOGO).convert("RGBA")
    larg = 500
    logo = logo.resize((larg, round(logo.height * larg / logo.width)), Image.LANCZOS)
    img.paste(logo, (100, 100), logo)
    d.text((100, 350), "Entenda o mercado de skins",
           font=_fonte(64, 800, "outfit"), fill=_TEXTO)
    d.text((100, 445), "Notas, preços e histórico com dados públicos da Steam.",
           font=_fonte(30, 400), fill=_TEXTO_FRACO)
    d.text((100, 500), "Top 20  ·  7d / 30d / 90d  ·  histórico",
           font=_fonte(26, 500), fill=_TEXTO)
    d.text((100, ALTURA - 70), "lodout.com", font=_fonte(28, 600),
           fill=_LARANJA)
    return _png(img)


def _nota_classe(nota: "int | float | None") -> str:
    nota = nota or 0
    return "alta" if nota >= 70 else ("media" if nota >= 45 else "baixa")


def cartao_item(nome_fmt: str, nota: "int | None", preco_fmt: str,
                raridade: "str | None" = None,
                icone: "bytes | None" = None) -> bytes:
    """1200x630: ícone à esquerda (se houver), nome, nota e preço."""
    cor_rar = _CORES_RARIDADE.get(raridade or "", _LARANJA)
    img = Image.new("RGB", (LARGURA, ALTURA), _FUNDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, LARGURA, 10], fill=cor_rar)

    # Quadro do ícone, com o fio da cor de raridade (como no site).
    qx, qy, qt = 70, 105, 420
    d.rounded_rectangle([qx, qy, qx + qt, qy + qt], radius=28,
                        fill=_SUPERFICIE, outline=cor_rar, width=4)
    if icone:
        try:
            ic = Image.open(io.BytesIO(icone)).convert("RGBA")
            ic.thumbnail((qt - 60, qt - 60), Image.LANCZOS)
            img.paste(ic, (qx + (qt - ic.width) // 2,
                           qy + (qt - ic.height) // 2), ic)
        except Exception:
            icone = None
    if not icone:
        # Sem ícone do item: o símbolo da marca, apagado, no lugar.
        alt = 150
        with Image.open(_SIMBOLO) as s:
            larg = round(alt * s.width / s.height)
        _simbolo(img, qx + (qt - larg) // 2, qy + (qt - alt) // 2, alt,
                 opacidade=0.3)

    x = qx + qt + 60
    largura_txt = LARGURA - x - 70
    y = 110
    f_nome = _fonte(54, 700, "outfit")
    estrela = nome_fmt.startswith("★")
    nome = nome_fmt.lstrip("★ ").strip() if estrela else nome_fmt
    recuo = 50 if estrela else 0
    for i, linha in enumerate(_quebrar(nome, f_nome, largura_txt - recuo, 3)):
        if i == 0 and estrela:
            _estrela(d, x + 19, y + 33, 20, cor_rar)
            d.text((x + recuo, y), linha, font=f_nome, fill=_TEXTO)
        else:
            d.text((x, y), linha, font=f_nome, fill=_TEXTO)
        y += 66

    y = max(y + 24, 330)
    if nota is not None:
        f_nota = _fonte(120, 700)
        d.text((x, y), "Nota", font=_fonte(30, 500), fill=_TEXTO_FRACO)
        d.text((x, y + 34), f"{int(nota)}", font=f_nota,
               fill=_CORES_NOTA[_nota_classe(nota)])
    if preco_fmt:
        # Depois da nota de verdade: nota 100 tem 3 dígitos. Sem "/100"
        # desde 20/11 (pedido do usuário: a escala fica implícita).
        fim_nota = x
        if nota is not None:
            fim_nota = x + f_nota.getlength(f"{int(nota)}")
        px = max(x + 300, int(fim_nota) + 50)
        tam = 56
        while tam > 34 and _fonte(tam, 700).getlength(preco_fmt) > LARGURA - 60 - px:
            tam -= 2
        d.text((px, y), "Preço", font=_fonte(30, 500), fill=_TEXTO_FRACO)
        d.text((px, y + 62 + (56 - tam) // 2), preco_fmt,
               font=_fonte(tam, 700), fill=_TEXTO)

    # Rodapé com a mesma marca do cartão padrão, sem TM.
    marca = Image.open(_LOGO).convert("RGBA")
    larg_marca = 150
    marca = marca.resize((larg_marca,
                          round(marca.height * larg_marca / marca.width)),
                         Image.LANCZOS)
    y_rod = ALTURA - 96
    img.paste(marca, (x, y_rod), marca)
    tx = x + larg_marca + 16
    f_dominio = _fonte(26, 600)
    d.text((tx, ALTURA - 70), "lodout.com", font=f_dominio, fill=_LARANJA)
    d.text((tx + f_dominio.getlength("lodout.com") + 12, ALTURA - 70),
           "· dados públicos da Steam", font=_fonte(26, 400),
           fill=_TEXTO_FRACO)
    return _png(img)


def _dir_cache() -> Path:
    return Path(_paths.DATA_DIR) / "og_cache"


def cartao_item_em_cache(nome_fmt: str, nota, preco_fmt: str,
                         raridade: "str | None",
                         icone: "bytes | None") -> bytes:
    """`cartao_item` com cache em disco pela combinação dos dados -- nota
    ou preço novos geram arquivo novo; os velhos saem pelo teto."""
    chave = hashlib.sha1("|".join([
        nome_fmt, str(nota), preco_fmt, raridade or "",
        hashlib.sha1(icone).hexdigest() if icone else "-",
        "v7"]).encode("utf-8")).hexdigest()  # v7: números em Geist (27/11)
    pasta = _dir_cache()
    caminho = pasta / f"{chave}.png"
    try:
        return caminho.read_bytes()
    except OSError:
        pass
    dados = cartao_item(nome_fmt, nota, preco_fmt, raridade, icone)
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(caminho, dados)
        arquivos = sorted(pasta.glob("*.png"), key=lambda p: p.stat().st_mtime)
        for velho in arquivos[:-_CACHE_MAX_ARQUIVOS]:
            velho.unlink(missing_ok=True)
    except OSError:
        pass
    return dados
