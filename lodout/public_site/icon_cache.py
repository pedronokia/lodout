"""Cache local de ícone dos itens.

Decisão nova (2a rodada, 2026-10-25): até aqui o `<img>` sempre apontava
direto pro CDN da Steam (`community.cloudflare.steamstatic.com`) de
propósito -- comentário antigo em `server.py` dizia que o site público
"nunca baixa/cacheia o ícone". Isso valia pra evitar qualquer tráfego
NOVO contra endpoint sensível da Steam (ver AGENTS.md: o rate limit real
é no market/inventory, não no CDN de imagem). O CDN de imagem é
infraestrutura pública estática, sem rate limit documentado, e
praticamente todo site que mostra item de CS2 hotlinka nela -- cachear
localmente aqui reduz UMA dependência externa no carregamento da
página (e evita o navegador do visitante mandar referrer pra
`steamstatic.com`), sem reintroduzir o risco que a decisão original
evitava.

Primeira visita busca e cacheia em disco; todas as próximas são leitura
local, sem rede. Falha de rede nunca derruba a página -- quem chama
decide o fallback (redirecionar pro CDN direto).
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from lodout._paths import DATA_DIR, atomic_write_bytes

_CACHE_DIR = DATA_DIR / "icon_cache"
# `community.cloudflare.steamstatic.com` passou a responder 301 pra este
# host (medido em 2026-10-30) -- e o httpx não segue redirect por padrão,
# então todo cache miss virava None em silêncio.
_CDN_URL_TPL = (
    "https://community.steamstatic.com/economy/image/{hash}/{tamanho}fx{tamanho}f")
# 3 s (era 5): sem resposta, o v4 sai do v3 guardado -- não vale segurar
# uma linha do servidor esperando o CDN.
_TIMEOUT = 3.0
# 192 é o tamanho original (único até 2026-11-08); 384 (exatamente 2x)
# alimenta o `srcset` "2x" que todo template já declara -- até aqui
# `icon_url_2x` era uma cópia do `icon_url` de 192px (achado da revisão
# de direção visual: o hero/vitrine mostra esse ícone bem maior que o
# nativo, perda de nitidez visível). Lista fechada e pública (sem "_")
# de propósito -- server.py valida a query string `tam` da rota contra
# ESTA MESMA lista antes de chamar `obter()`, uma fonte só pros 2
# lugares não dessincronizar.
TAMANHOS_PERMITIDOS = (192, 384)
TAMANHO_PADRAO = 192
# Hash de ícone da Steam é base64 url-safe: letras, dígitos, "-" e "_",
# ~200 caracteres. Um filtro só `isalnum()` (até 2026-10-30) arrancava os
# "-"/"_" e cortava em 128 -- a URL montada dava 404 pra TODO item.
_CHARS_HASH = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
_MAX_HASH = 512


def _sanitizar(hash_icone: str) -> str:
    return "".join(c for c in (hash_icone or "") if c in _CHARS_HASH)[:_MAX_HASH]


def _caminho(hash_icone: str, tamanho: int) -> Path:
    return _CACHE_DIR / f"{_sanitizar(hash_icone)}.v4.{tamanho}.webp"


def _caminho_antigo(hash_icone: str, tamanho: int) -> Path:
    """Cache v3 (sem enquadramento, WebP q80): só fonte de reserva pra
    gerar o v4 sem rede quando o CDN não responde."""
    return _CACHE_DIR / f"{_sanitizar(hash_icone)}.v3.{tamanho}.webp"


# v4 (2026-11-14): a Steam entrega a arte num quadro com margem
# transparente que varia muito -- caixas ocupavam 49-63% do lado, skins
# ~86% -- e o cartão mostrava as caixas pequenas e "soltas", cada item de
# um tamanho. Agora: recorta a margem e centraliza a arte ocupando a
# mesma fração do quadro em todo item; WebP q92 (era 80, com marcas
# visíveis em bordas e letras finas, ex. o "CS:GO" das caixas).
_OCUPACAO = 0.88
_AMPLIACAO_MAX = 2.0
_WEBP_QUALIDADE_V4 = 92


def _enquadrar(im):
    """Recorta a margem transparente e centraliza a arte num quadro
    quadrado, ocupando `_OCUPACAO` do lado. Imagem sem transparência
    (nada a recortar com segurança) volta como está."""
    from PIL import Image
    if im.mode != "RGBA":
        return im
    caixa = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not caixa:
        return im
    lado = max(im.size)
    arte = im.crop(caixa)
    alvo = lado * _OCUPACAO
    fator = min(alvo / arte.width, alvo / arte.height, _AMPLIACAO_MAX)
    nova = (max(1, round(arte.width * fator)), max(1, round(arte.height * fator)))
    if nova != arte.size:
        arte = arte.resize(nova, Image.LANCZOS)
    quadro = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadro.paste(arte, ((lado - arte.width) // 2, (lado - arte.height) // 2), arte)
    return quadro


def _processar(fonte: bytes, tamanho: int) -> "bytes | None":
    """PNG/JPEG/WebP de origem -> WebP v4 do `tamanho` pedido."""
    from PIL import Image
    try:
        with Image.open(BytesIO(fonte)) as origem:
            transparente = (origem.mode in ("RGBA", "LA", "PA")
                            or "transparency" in origem.info)
            im = origem.convert("RGBA" if transparente else "RGB")
        im = _enquadrar(im)
        if im.size != (tamanho, tamanho):
            im = im.resize((tamanho, tamanho), Image.LANCZOS)
        buf = BytesIO()
        # method=4 (padrão): o 6 custava bem mais CPU por quase nada de
        # tamanho a menos, e gerar ícone não pode segurar o servidor.
        im.save(buf, format="WEBP", quality=_WEBP_QUALIDADE_V4, method=4)
        return buf.getvalue()
    except Exception:
        return None


def _baixar_original(hash_seguro: str) -> "bytes | None":
    """O PNG de 384px do CDN de imagem da Steam (sem perda). Uma busca
    serve os dois tamanhos: o de 192 sai dele, reduzido aqui."""
    try:
        import httpx
        resp = httpx.get(_CDN_URL_TPL.format(hash=hash_seguro, tamanho=384),
                         timeout=_TIMEOUT, follow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception:
        pass
    return None


def _gravar(p: Path, dados: bytes) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(p, dados)
    except OSError:
        pass


def _gerar(hash_seguro: str, tamanho: int, com_rede: bool) -> "bytes | None":
    """Gera (e grava) o v4. Fonte: o original do CDN (melhor qualidade);
    sem rede ou com falha, o v3 já guardado em disco."""
    fonte = _baixar_original(hash_seguro) if com_rede else None
    da_rede = fonte is not None
    if fonte is None:
        for tam in (384, tamanho):
            antigo = _caminho_antigo(hash_seguro, tam)
            if antigo.exists():
                try:
                    fonte = antigo.read_bytes()
                    break
                except OSError:
                    pass
    if fonte is None:
        return None
    pedido = None
    # Do original da rede saem os dois tamanhos de uma vez (uma busca só).
    for tam in (TAMANHOS_PERMITIDOS if da_rede else (tamanho,)):
        dados = _processar(fonte, tam)
        if dados is None:
            continue
        _gravar(_caminho(hash_seguro, tam), dados)
        if tam == tamanho:
            pedido = dados
    return pedido


def ler_local(hash_icone: str, tamanho: int = 384) -> "bytes | None":
    """v4 do disco, ou gerado na hora a partir do v3 -- NUNCA usa rede
    (cartão de prévia, que não pode depender do CDN)."""
    hash_seguro = _sanitizar(hash_icone)
    if not hash_seguro or tamanho not in TAMANHOS_PERMITIDOS:
        return None
    p = _caminho(hash_seguro, tamanho)
    try:
        return p.read_bytes()
    except OSError:
        return _gerar(hash_seguro, tamanho, com_rede=False)


def obter(hash_icone: str, tamanho: int = TAMANHO_PADRAO) -> "bytes | None":
    """Bytes da imagem (WebP), do cache de disco ou buscando do CDN da
    Steam e reencodando antes de cachear. None se o hash for
    inválido ou a busca/reencode falhar -- quem chama decide o
    fallback.

    `tamanho` fora de `TAMANHOS_PERMITIDOS` cai no padrão (192) em vez
    de erro -- mesma postura defensiva do resto do arquivo, nunca 500
    pro visitante por um parâmetro inesperado.

    A rota `/icone/<hash>.webp` (server.py) passa o `<hash>` da URL direto
    pra cá, sem validar nada -- é QUALQUER visitante, sem login. Até
    2026-10-27 só `_caminho()` sanitizava (pro nome do arquivo em disco);
    a requisição de rede usava `hash_icone` cru, sem passar pelo mesmo
    filtro. O host de destino é fixo (`_CDN_URL_TPL` já tem o domínio
    embutido antes do `{hash}`, então não dá pra redirecionar pra outro
    host por aqui), mas um hash arbitrário ainda fazia o servidor buscar
    (e cachear em disco) qualquer path dentro de steamstatic.com por
    conta de qualquer um -- sanitiza ANTES de usar nos dois lugares,
    não só no caminho do arquivo."""
    if tamanho not in TAMANHOS_PERMITIDOS:
        tamanho = TAMANHO_PADRAO
    hash_seguro = _sanitizar(hash_icone)
    if not hash_seguro:
        return None
    p = _caminho(hash_seguro, tamanho)
    if p.exists():
        try:
            return p.read_bytes()
        except OSError:
            pass
    return _gerar(hash_seguro, tamanho, com_rede=True)
