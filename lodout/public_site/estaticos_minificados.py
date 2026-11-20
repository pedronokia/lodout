"""Entrega style.css e app.js sem comentários (revisão 20/11).

O Dockerfile já minifica esses arquivos no build (scripts/minify_static.py),
mas em produção a pasta `lodout/` do servidor é montada por cima da imagem
(`./lodout:/app/lodout:ro`, deploy rápido de 19/11) -- então o visitante
baixava o fonte com 60 KB de comentário: 362 KB, ou 72 KB comprimido, antes
de ver qualquer página. Aqui o próprio site minifica na hora (uma vez por
versão do arquivo, guardado em memória) e entrega com o mesmo cache longo.

Minificação leve, igual à do build: só tira comentário e linha em branco,
nunca reescreve token. O fonte no repositório continua comentado.
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path

ARQUIVOS = {"style.css": "text/css", "app.js": "text/javascript"}

_cache: "dict[str, tuple[tuple[int, int], bytes, str]]" = {}
_trava = threading.Lock()


def minificar_css(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    linhas = (linha.strip() for linha in texto.splitlines())
    return "\n".join(linha for linha in linhas if linha) + "\n"


def minificar_js(texto: str) -> str:
    # Só bloco /* */ e linha que COMEÇA com "//": um "//" no meio da
    # linha pode estar dentro de string ("http://...").
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    linhas = [linha.rstrip() for linha in texto.splitlines()
              if not linha.strip().startswith("//")]
    return "\n".join(linha for linha in linhas if linha.strip()) + "\n"


def conteudo(pasta: Path, nome: str) -> "tuple[bytes, str] | None":
    """(bytes minificados, etag) do arquivo, ou None se não existir.
    Refaz só quando o arquivo muda (mtime/tamanho)."""
    if nome not in ARQUIVOS:
        return None
    caminho = Path(pasta) / nome
    try:
        st = caminho.stat()
    except OSError:
        return None
    chave = (st.st_mtime_ns, st.st_size)
    guardado = _cache.get(nome)
    if guardado and guardado[0] == chave:
        return guardado[1], guardado[2]
    with _trava:
        texto = caminho.read_text(encoding="utf-8")
        mini = minificar_css(texto) if nome.endswith(".css") else minificar_js(texto)
        dados = mini.encode("utf-8")
        etag = hashlib.sha1(dados).hexdigest()[:20]
        _cache[nome] = (chave, dados, etag)
    return dados, etag
