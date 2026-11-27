"""Minifica style.css/app.js IN-PLACE -- chamado só no build da imagem
Docker (Dockerfile.public-site), nunca sobre o código-fonte do repositório
(a cópia minificada vive dentro da imagem, não no Git).

Minificação "leve" de propósito: só remove comentário e linha em branco
ociosa, nunca reescreve token. Um minificador de JS de verdade precisa de
um parser pra não quebrar string literal/regex -- sem isso aqui, arriscado
demais pra um ganho pequeno (os dois arquivos juntos têm poucos KB). CSS
usa a mesma lógica conservadora, mesmo sendo mais seguro de comprimir.

Uso: `python scripts/minify_static.py [pasta]` (default:
lodout/public_site/static).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_PASTA_DEFAULT = Path("lodout/public_site/static")


# Texto entre aspas (content: "...", url("..."), nomes de fonte) passa
# intacto; só o que está fora das aspas é compactado.
_STRING_CSS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')


def _compactar_fora_de_strings(trecho: str) -> str:
    trecho = re.sub(r"\s+", " ", trecho)
    # Espaço em volta de { } ; , > não muda nada no CSS. ":" fica de
    # fora de propósito: "a :hover" (descendente) é diferente de
    # "a:hover"; "+" e "~" também ficam, por causa do calc().
    trecho = re.sub(r"\s*([{};,>])\s*", r"\1", trecho)
    return trecho.replace(";}", "}")


def minify_css(texto: str) -> str:
    """Tira comentários, quebras de linha e espaços que o navegador
    ignora (27/11: antes só tirava comentários; o Lighthouse ainda via
    ~6 KB de sobra). Nunca mexe dentro de aspas. O teste
    test_minify_css_mantem_as_regras confere, no style.css real, que as
    regras e declarações continuam as mesmas."""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    partes, pos = [], 0
    for m in _STRING_CSS.finditer(texto):
        partes.append(_compactar_fora_de_strings(texto[pos:m.start()]))
        partes.append(m.group(0))
        pos = m.end()
    partes.append(_compactar_fora_de_strings(texto[pos:]))
    return "".join(partes).strip() + "\n"


def minify_js(texto: str) -> str:
    # Só remove bloco /* */ e linha que COMEÇA com "//" (depois de
    # trim) -- nunca um "// comentário" no fim de uma linha de código,
    # que poderia estar dentro de uma string ("http://..." não começa
    # a linha com "//", então não bate aqui).
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    linhas = []
    for linha in texto.splitlines():
        if linha.strip().startswith("//"):
            continue
        linhas.append(linha.rstrip())
    return "\n".join(l for l in linhas if l.strip()) + "\n"


def main(argv: list[str]) -> None:
    pasta = Path(argv[1]) if len(argv) > 1 else _PASTA_DEFAULT
    css = pasta / "style.css"
    js = pasta / "app.js"
    if css.exists():
        antes = len(css.read_bytes())
        css.write_text(minify_css(css.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"style.css: {antes} -> {len(css.read_bytes())} bytes")
    if js.exists():
        antes = len(js.read_bytes())
        js.write_text(minify_js(js.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"app.js: {antes} -> {len(js.read_bytes())} bytes")


if __name__ == "__main__":
    main(sys.argv)
