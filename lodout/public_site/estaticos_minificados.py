"""Entrega CSS e JS do site minificados em tempo de execução.

O Dockerfile também minifica esses arquivos no build (scripts/minify_static.py,
que reutiliza este módulo como fonte única), mas em produção a pasta `lodout/`
do servidor é montada por cima da imagem (`./lodout:/app/lodout:ro`, deploy
rápido de 19/11). Por isso o próprio site minifica na hora (uma vez por versão
do arquivo, guardado em memória) e entrega com o mesmo cache longo.

O fonte no repositório continua legível e comentado.
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path

ARQUIVOS = {
    "style.css": "text/css",
    "app.js": "text/javascript",
    "conta.js": "text/javascript",
    "copiar_preco.js": "text/javascript",
    "online.js": "text/javascript",
    "popover.js": "text/javascript",
}

_cache: "dict[str, tuple[tuple[int, int], bytes, str]]" = {}
_trava = threading.Lock()

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


def minificar_css(texto: str) -> str:
    """Tira comentários, quebras de linha e espaços que o navegador
    ignora, sem nunca mexer dentro de aspas."""
    texto = re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)
    partes, pos = [], 0
    for m in _STRING_CSS.finditer(texto):
        partes.append(_compactar_fora_de_strings(texto[pos:m.start()]))
        partes.append(m.group(0))
        pos = m.end()
    partes.append(_compactar_fora_de_strings(texto[pos:]))
    return "".join(partes).strip() + "\n"


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
