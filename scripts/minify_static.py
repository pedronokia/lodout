"""Minifica os CSS/JS do site IN-PLACE -- chamado só no build da imagem
Docker (Dockerfile.public-site), nunca sobre o código-fonte do repositório
(a cópia minificada vive dentro da imagem, não no Git).

Reutiliza `lodout.public_site.estaticos_minificados` como fonte única de
verdade para que a minificação do build e a minificação em runtime (quando
`./lodout` é montado sobre a imagem em produção) produzam exatamente a
mesma saída.

Uso: `python scripts/minify_static.py [pasta]` (default:
lodout/public_site/static).
"""
from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from lodout.public_site import estaticos_minificados  # noqa: E402

_PASTA_DEFAULT = Path("lodout/public_site/static")

minify_css = estaticos_minificados.minificar_css
minify_js = estaticos_minificados.minificar_js


def main(argv: list[str]) -> None:
    pasta = Path(argv[1]) if len(argv) > 1 else _PASTA_DEFAULT
    for nome in estaticos_minificados.ARQUIVOS:
        arq = pasta / nome
        if not arq.exists():
            continue
        antes = len(arq.read_bytes())
        fn = minify_css if nome.endswith(".css") else minify_js
        arq.write_text(fn(arq.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{nome}: {antes} -> {len(arq.read_bytes())} bytes")


if __name__ == "__main__":
    main(sys.argv)
