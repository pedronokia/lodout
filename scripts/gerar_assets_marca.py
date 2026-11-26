"""Regera os PNGs e o ICO da marca a partir dos SVGs em static/.

Uso: python scripts/gerar_assets_marca.py

Fontes:
- `templates/partials/_logo_svg.html`: marca oficial "Escura Alto
  Contraste", sem TM, a mesma do topo/rodapé. Vira `logo-escura-og.png`,
  usado pelo cartão de compartilhamento (`og_cards.py`).
- `logo-L.svg`: símbolo da marca de 25/11, usado quando um item do
  cartão não tem ícone em cache.
- `favicon.svg`: monograma oficial chanfrado (aba e marcadores).
- `logo-escura-app.svg`: marca oficial completa em quadrado seguro
  (apple-touch-icon e ícones do manifest).
- `logo-lodout.svg`: marca de 25/11, mantida só como histórico; não
  é mais usada no cartão de compartilhamento.

Nenhum PNG/ICO da marca deve ser editado à mão. O Outfit é embutido
no HTML de renderização para que o texto dos SVGs não caia no fallback.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
STATIC = RAIZ / "lodout" / "public_site" / "static"
FONTE_OUTFIT = STATIC / "fonts" / "outfit-latin.woff2"
LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
_MARCA_OFICIAL = (RAIZ / "lodout" / "public_site" / "templates"
                  / "partials" / "_logo_svg.html")


def _marca_oficial_svg() -> str:
    """O SVG exato da marca do topo/rodapé, sem TM, sem comentário Jinja.

    Um único desenho para site e cartão de compartilhamento: se a marca
    mudar, basta mudar o partial e regerar os rasterizados.
    """
    texto = _MARCA_OFICIAL.read_text(encoding="utf-8")
    return re.sub(r"\{#.*?#\}", "", texto, flags=re.S).strip()


def _html(svg: str, fundo: str | None) -> str:
    css_fundo = fundo or "transparent"
    fonte = base64.b64encode(FONTE_OUTFIT.read_bytes()).decode("ascii")
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "@font-face{font-family:Outfit;src:url(data:font/woff2;base64,"
        + fonte
        + ") format('woff2');font-weight:600 800;font-display:block;}"
        "html,body{margin:0;padding:0;overflow:hidden;background:"
        + css_fundo
        + ";}"
        "svg{display:block;width:100vw;height:100vh;}"
        "svg text{font-family:Outfit,sans-serif;font-weight:800;}"
        "</style></head><body>" + svg + "</body></html>"
    )


def _render(pagina, svg: str, largura: int, altura: int,
            fundo: str | None = None, fator: int = 4) -> Image.Image:
    pagina.set_viewport_size({"width": largura * fator,
                              "height": altura * fator})
    pagina.set_content(_html(svg, fundo))
    pagina.evaluate("() => document.fonts.ready.then(() => true)")
    dados = pagina.screenshot(omit_background=fundo is None)
    img = Image.open(io.BytesIO(dados)).convert(
        "RGBA" if fundo is None else "RGB")
    if fator == 1:
        return img
    # Renderizar em 4x e reduzir com LANCZOS mantém a borda fina e o "l"
    # legíveis em 16px, onde um raster direto ficava com escada.
    return img.resize((largura, altura), LANCZOS)


def _salvar_png(img: Image.Image, nome: str, modo: str = "RGBA") -> None:
    if modo == "RGB":
        img = img.convert("RGB")
    img.save(STATIC / nome, "PNG", optimize=True)


def main(apenas_marca_og: bool = False) -> None:
    """Os SVGs abaixo são a fonte; nada de PNG editado à mão."""
    marca_oficial = _marca_oficial_svg()
    simbolo_og = (STATIC / "logo-L.svg").read_text(encoding="utf-8")
    simbolo = (STATIC / "favicon.svg").read_text(encoding="utf-8")
    aplicativo = (STATIC / "logo-escura-app.svg").read_text(encoding="utf-8")

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(device_scale_factor=1)

        # Cartão de compartilhamento: a marca oficial "Escura Alto
        # Contraste", com o mesmo SVG chanfrado e sem TM do site.
        _salvar_png(_render(pagina, marca_oficial, 1040, 448, fator=1),
                    "logo-escura-og.png")
        if apenas_marca_og:
            navegador.close()
            print("marca do cartão regenerada em", STATIC)
            return

        # Símbolo de reserva dos cartões de item sem ícone em cache.
        _salvar_png(_render(pagina, simbolo_og, 440, 440, fator=1),
                    "logo-L.png")

        # Aba e marcadores: monograma chanfrado, fundo transparente.
        for lado in (16, 32, 48):
            _salvar_png(_render(pagina, simbolo, lado, lado),
                        f"favicon-{lado}.png")

        # iOS/Android não contam com transparência: fundo escuro sólido e
        # a marca completa dentro da margem de segurança do quadrado.
        _salvar_png(_render(pagina, aplicativo, 180, 180, fundo="#080808"),
                    "apple-touch-icon.png", modo="RGB")
        for lado in (192, 512):
            _salvar_png(_render(pagina, aplicativo, lado, lado,
                                fundo="#080808"),
                        f"icon-{lado}.png", modo="RGB")

        # ICO com os três tamanhos usados pelo Windows.
        imagens = [_render(pagina, simbolo, lado, lado).convert("RGBA")
                   for lado in (16, 32, 48)]
        # O ICO é gerado a partir do maior (48px): o Pillow faz o
        # downcast pra 16/32. Salvar a partir do 16px deixava só um
        # tamanho no arquivo.
        imagens[-1].save(
            STATIC / "favicon.ico", format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
        )

        navegador.close()

    print("assets da marca regenerados em", STATIC)


if __name__ == "__main__":
    import sys

    # `--apenas-marca-og` regera só o PNG usado pelo cartão de
    # compartilhamento, sem tocar nos ícones já publicados.
    main(apenas_marca_og="--apenas-marca-og" in sys.argv)
