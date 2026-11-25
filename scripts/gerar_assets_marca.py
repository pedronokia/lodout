"""Regera os PNGs e o ICO da identidade plana a partir dos SVGs em static/.

Uso: python scripts/gerar_assets_marca.py

Os SVGs são a fonte: `logo-lodout.svg` (marca completa) e `logo-L.svg`
(símbolo). Este script só produz os rasterizados usados pelo site e pelo
`og_cards` — nenhum PNG da marca deve ser editado à mão.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
STATIC = RAIZ / "lodout" / "public_site" / "static"


def _html(svg: str, fundo: str | None) -> str:
    css_fundo = fundo or "transparent"
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        "html,body{margin:0;padding:0;overflow:hidden;background:"
        + css_fundo
        + ";}"
        "svg{display:block;width:100vw;height:100vh;}"
        "</style></head><body>" + svg + "</body></html>"
    )


def _render(pagina, svg: str, largura: int, altura: int,
            fundo: str | None = None) -> bytes:
    pagina.set_viewport_size({"width": largura, "height": altura})
    pagina.set_content(_html(svg, fundo))
    return pagina.screenshot(omit_background=fundo is None)


def _salvar_png(dados: bytes, nome: str, modo: str = "RGBA") -> None:
    img = Image.open(io.BytesIO(dados))
    if modo == "RGB":
        img = img.convert("RGB")
    img.save(STATIC / nome, "PNG", optimize=True)


def main() -> None:
    marca = (STATIC / "logo-lodout.svg").read_text(encoding="utf-8")
    simbolo = (STATIC / "logo-L.svg").read_text(encoding="utf-8")

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(device_scale_factor=1)

        # Marca e símbolo em alta resolução, com fundo transparente: o
        # cartão de compartilhamento cola os dois sobre o fundo do cartão.
        _salvar_png(_render(pagina, marca, 1100, 267), "logo-lodout.png")
        _salvar_png(_render(pagina, simbolo, 440, 440), "logo-L.png")

        # Aba do navegador: transparência nos cantos arredondados.
        for lado in (16, 32):
            _salvar_png(_render(pagina, simbolo, lado, lado),
                        f"favicon-{lado}.png")

        # iOS/Android não contam com transparência: fundo escuro sólido.
        for lado in (192, 512):
            dados = _render(pagina, simbolo, lado, lado, fundo="#0B0B0B")
            _salvar_png(dados, f"icon-{lado}.png", modo="RGB")

        # ICO com os três tamanhos usados pelo Windows.
        imagens = []
        for lado in (16, 32, 48):
            dados = _render(pagina, simbolo, lado, lado)
            imagens.append(Image.open(io.BytesIO(dados)).convert("RGBA"))
        imagens[0].save(
            STATIC / "favicon.ico", format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48)],
        )

        navegador.close()

    print("assets da marca regenerados em", STATIC)


if __name__ == "__main__":
    main()
