"""Fábrica Flask do site público.

Serve só o que `worker.py` (processo separado) já escreveu em
`scan_store.json`/`rankings.json`. NUNCA fala com a Steam por requisição
de visitante. As rotas pessoais usam autenticação e armazenamento por
conta; a página pública chama `recommendations.buy_candidates` com
`owned_names=set()` para apresentar o ranking geral.
"""
from __future__ import annotations

import logging
import logging.handlers
import math
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import time
# Relógio da medição Server-Timing importado à parte: o roteiro dos testes
# visuais troca o módulo `time` deste arquivo por um relógio congelado
# (só com time()), e a home quebrava com 500 lá.
from time import perf_counter as _relogio
import urllib.parse
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

# A stdlib não conhece woff2 e a fonte sairia como
# "application/octet-stream" (alguns navegadores reclamam disso no
# console). Registra o tipo certo uma vez, global.
mimetypes.add_type("font/woff2", ".woff2")

from flask import (
    Flask, Response, g, jsonify, make_response, redirect, render_template,
    request, send_from_directory, session, url_for,
)
from markupsafe import Markup
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

from lodout import (
    __version__, cases, gamedata, portfolio, ranking, recommendations,
    scan_store, scan_targets, signals, steam_news,
)
from lodout._paths import DATA_DIR, atomic_write_bytes
from lodout.localization import localize_name
from lodout.public_site import (
    backtest_diario, buscas, catalogo, changelog, charts, db_backup,
    discord_notify, encomenda,
    erro_stats, estaticos_minificados, fmt, icon_cache, latencia,
    notas_historico, og_cards, online,
    profile_fetcher,
    raridade, rate_limit,
    scan_progress, user_store, uptime, visits,
)
from lodout.public_site.auth import csrf_token, csrf_valid

_MARKET_LISTING_URL = "https://steamcommunity.com/market/listings/730/{name}"
# Ícone: CDN estático da Steam (steamstatic.com), não o market/inventory
# rate-limited -- cacheado localmente via `icon_cache.py` (2a rodada,
# 2026-10-25) pela rota `/icone/<hash>.webp` abaixo. Esta constante
# continua servindo de FALLBACK (redirect) quando o cache falha.
_ICON_CDN_URL_2X = (
    "https://community.steamstatic.com/economy/image/"
    "{hash}/{tamanho}fx{tamanho}f"
)
_STEAMDB_SEARCH_URL = "https://steamdb.info/search/?q={name}"
from lodout.public_site.account import bp as account_bp
from lodout.public_site.history_routes import bp as history_bp
from lodout.public_site.trades_routes import bp as trades_bp
from lodout.public_site.watchlist_routes import bp as watchlist_bp
from lodout._ambiente import ambiente

_STATIC_DIR = Path(__file__).parent / "static"
_TEMPLATES_DIR = Path(__file__).parent / "templates"

_LIMIT_CANDIDATOS = 20
# 12: fecha a grade da vitrine em 4, 3 e 2 colunas (com 10, a última
# fileira de 4 colunas ficava com 2 cartões e 2 buracos).
_PAGINA_TAMANHO = 12
_INTERVALO_HORAS_DEFAULT = 6.0
_SECRET_KEY_PATH = DATA_DIR / "public_site_secret.key"
_ERROR_LOG_PATH = DATA_DIR / "errors.log"
# Gravado pelo Dockerfile a cada build (data/hora do build, UTC) -- sem
# isso __version__ fica preso em "1.0.0" pra sempre, sem jeito de saber
# SE um deploy novo de fato subiu. Ausente fora de Docker (dev local).
_BUILD_ID_PATH = Path(__file__).parent.parent.parent / "BUILD_ID"
# Senha do /admin: o hash pronto (ADMIN_PASSWORD_HASH, gerado com
# scripts/hash_admin_password.py) ou, mais simples pro dono, a própria
# senha (ADMIN_PASSWORD, vinda de um secret do GitHub pelo deploy), que
# vira hash aqui na subida. Senha curta demais é ignorada: sem senha
# válida o /admin finge não existir (404), nunca abre "sem senha".
_ADMIN_SENHA_MIN = 12
# Arquivo de verificação do Google Search Console (nome não é segredo).
_GOOGLE_VERIFICACAO = "google828fe430d38de239"


def _hash_senha_admin() -> str:
    pronto = ambiente("ADMIN_PASSWORD_HASH", "") or ""
    if pronto:
        return pronto
    senha = ambiente("ADMIN_PASSWORD", "") or ""
    if len(senha) >= _ADMIN_SENHA_MIN:
        return generate_password_hash(senha)
    if senha:
        logging.getLogger("lodout.site").warning(
            "ADMIN_PASSWORD com menos de %d caracteres: /admin desligado",
            _ADMIN_SENHA_MIN)
    return ""


_ADMIN_PASSWORD_HASH = _hash_senha_admin()


def _build_id() -> "str | None":
    via_env = (ambiente("BUILD_ID", "") or "").strip()
    if via_env:
        return via_env
    try:
        return _BUILD_ID_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _configurar_log_erros(app: Flask) -> None:
    """Grava exceções não tratadas em `DATA_DIR/errors.log`, separado do
    stdout do gunicorn -- achado de hoje (pedido do usuário): sem isso,
    um 500 em produção só aparece se alguém for catar `docker logs` na
    hora certa. Rotativo (1MB x 3 arquivos) pra nunca crescer sem limite."""
    handler = logging.handlers.RotatingFileHandler(
        _ERROR_LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"))
    app.logger.addHandler(handler)


def _parse_float_arg(nome: str) -> float | None:
    """Lê um query param numérico opcional. Vazio/inválido/não-finito ->
    None -- nunca `or 0`, que confundiria "não informado" com "zero"."""
    valor = request.args.get(nome)
    if valor is None or valor == "":
        return None
    try:
        numero = float(valor)
    except ValueError:
        return None
    return numero if math.isfinite(numero) else None


def _parse_int_arg(nome: str, default: int) -> int:
    valor = request.args.get(nome)
    if valor is None or valor == "":
        return default
    try:
        return max(1, int(valor))
    except ValueError:
        return default


def _paginas_visiveis(pagina: int, total_paginas: int, janela: int = 2) -> list:
    """Números de página a mostrar na paginação: a atual +/- `janela`,
    sempre com a primeira e a última, e `None` marcando uma lacuna (vira
    reticências no template). Ex.: pagina=9, total=20 -> [1, None, 7, 8,
    9, 10, 11, None, 20]. Com poucas páginas, não cria lacuna nenhuma."""
    if total_paginas <= 1:
        return [1] if total_paginas == 1 else []
    nums = sorted(set(
        [1, total_paginas]
        + list(range(max(1, pagina - janela), min(total_paginas, pagina + janela) + 1))
    ))
    visiveis: list = []
    anterior = None
    for n in nums:
        if anterior is not None and n - anterior > 1:
            visiveis.append(None)
        visiveis.append(n)
        anterior = n
    return visiveis


def _destaques_comparar(itens: list, campo: str) -> "tuple[set, set]":
    """Nomes com o menor e o maior valor de `campo` entre os itens do
    /comparar -- conjuntos vazios com menos de 2 itens ou se todos
    empatarem (marcar um entre valores iguais seria arbitrário, não
    informativo). Puramente descritivo ("maior/menor valor desta
    linha"), nunca "melhor escolha" -- ver AGENTS.md."""
    valores = [(it.get("name"), it.get(campo)) for it in itens
               if it.get(campo) is not None]
    if len(valores) < 2:
        return set(), set()
    nums = [v for _, v in valores]
    if min(nums) == max(nums):
        return set(), set()
    minimo, maximo = min(nums), max(nums)
    return ({n for n, v in valores if v == minimo},
            {n for n, v in valores if v == maximo})


def _load_or_create_secret_key() -> bytes:
    """Chave de assinatura da sessão do Flask, gerada uma vez e persistida.

    Sem isto, toda troca de processo (ou um `app.secret_key` hardcoded no
    código) invalidaria sessões -- ou peor, usaria a mesma chave previsível
    em toda instalação. Gerada com `secrets.token_bytes` (criptográfico),
    gravada com `atomic_write_bytes` (mesma disciplina de escrita atômica
    de sempre).

    0o600 (achado de auditoria, 2026-11-22): `atomic_write_bytes` não
    restringe permissão -- sem isto, o arquivo ficava no umask padrão
    (normalmente legível por qualquer usuário local), e quem o lesse
    poderia forjar cookie de sessão de qualquer pessoa. `chmod` roda
    nos dois caminhos (recém-criado e já existente) pra corrigir
    sozinho uma instalação de antes desta mudança; falha de permissão
    (ex. sistema de arquivos que não suporta, Windows) não derruba o
    site -- a chave continua funcionando, só sem esse reforço."""
    if _SECRET_KEY_PATH.exists():
        chave = _SECRET_KEY_PATH.read_bytes()
    else:
        chave = secrets.token_bytes(32)
        atomic_write_bytes(_SECRET_KEY_PATH, chave)
    try:
        os.chmod(_SECRET_KEY_PATH, 0o600)
    except OSError:
        pass
    return chave


def _admin_required(view):
    """Nega como 404 (não 403/redirect) sem hash configurado ou sem
    sessão `admin` -- mesmo padrão de `auth.login_required`, mas sem
    redirecionar pro login: estas rotas não devem nem revelar que
    existem pra quem não é o dono (achado de auditoria da skill
    flask-python, 2026-11-05: o mesmo bloco de 2 linhas estava
    duplicado em `admin_logout`, `admin_testar_webhook`,
    `admin_backup_download` e `admin_log_bruto`).

    NÃO usar em `admin()`: ali, sem sessão (mas COM hash configurado)
    redireciona pro login em vez de 404 -- comportamento diferente de
    propósito, pra guiar o dono de volta ao login em vez de escondê-lo."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _ADMIN_PASSWORD_HASH or not _admin_ativo():
            return render_template("404.html"), 404
        return view(*args, **kwargs)
    return wrapped


_ADMIN_SESSAO_MAX_S = 12 * 3600


def _admin_ativo() -> bool:
    """Sessão de admin com prazo próprio: o cookie do site dura 30 dias
    (login da Steam), o admin não. Guarda a hora do login; valor antigo
    (True, de antes do prazo) não vale mais."""
    quando = session.get("admin")
    if isinstance(quando, bool) or not isinstance(quando, (int, float)):
        return False
    return 0 <= time.time() - quando < _ADMIN_SESSAO_MAX_S


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(_STATIC_DIR),
        template_folder=str(_TEMPLATES_DIR),
    )
    app.config["JSON_AS_ASCII"] = False
    # Achado de auditoria (2026-10-24): sem isso, o CSS/favicon saiam com
    # "Cache-Control: no-cache" -- o navegador revalidava (ETag) em toda
    # visita em vez de usar o cache direto por um tempo. 1 ano agora que
    # `static_v()` (acima) faz cache-busting via `?v=<build>` -- sem o
    # cache-busting, 1 ano deixaria visitante com CSS/JS velho até expirar
    # mesmo depois de um deploy; com ele, é seguro ir longe (2026-10-25).
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 24 * 3600
    app.secret_key = _load_or_create_secret_key()
    _configurar_log_erros(app)
    app.register_blueprint(account_bp)
    app.register_blueprint(trades_bp)
    app.register_blueprint(watchlist_bp)
    app.register_blueprint(history_bp)

    # Em produção, um proxy (Render/Fly.io/nginx) termina o HTTPS e fala
    # com o gunicorn em texto puro -- sem isto, `request.url_root` (usado
    # pelo login Steam OpenID pra montar `realm`/`return_to`) reportaria
    # "http://" mesmo com o visitante em "https://", e a Steam devolveria
    # a um endereço que não bate com o que foi mandado. Inócuo localmente:
    # sem cabeçalho X-Forwarded-*, não muda nada.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Login da Steam dura 30 dias ou até "Sair" (revisão 2026-11-16; antes
    # acabava ao fechar o navegador). account.login_callback marca a sessão
    # como permanente; o admin tem limite próprio (_admin_ativo, 12 h).
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    # Teto de corpo de requisição (256 KB): qualquer formulário ou POST JSON
    # do site ocupa poucos KB; limita abuso contra os 512 MB do container.
    app.config["MAX_CONTENT_LENGTH"] = 256 * 1024
    # "Secure" exige HTTPS -- ligar sempre quebraria o dev local (http).
    # Produção seta LODOUT_PUBLIC_SITE_SECURE_COOKIES=1 (ver
    # lodout/public_site/README.md).
    app.config["SESSION_COOKIE_SECURE"] = (
        ambiente("PUBLIC_SITE_SECURE_COOKIES") == "1")

    @app.context_processor
    def _inject_versao():
        build = _build_id()

        def static_v(filename: str) -> str:
            """`url_for('static', ...)` + `?v=<build>` -- cache-busting pro
            `SEND_FILE_MAX_AGE_DEFAULT` de 1 ano (pedido, 2026-10-25): sem
            isso, aumentar o cache-control faria o navegador ficar com
            `style.css`/`app.js` velhos até expirar, mesmo depois de um
            deploy. Cada build/modificação muda o `?v=`, então o navegador sempre busca
            de novo quando o conteúdo de fato mudou."""
            filepath = Path(app.static_folder or "") / filename
            try:
                mtime = int(filepath.stat().st_mtime)
                v = f"{build}-{mtime}" if build else str(mtime)
            except OSError:
                v = build or "dev"
            return f"{url_for('static', filename=filename)}?v={v}"

        return {
            "versao": f"{__version__} ({build})" if build else __version__,
            "static_v": static_v,
        }

    @app.context_processor
    def _inject_usuario():
        """`usuario` (nome/avatar) disponível em TODO template, não só
        nas rotas que já passavam explicitamente -- sem isto,
        `_conta_link.html` mostrava "Minha conta" genérico em vez do
        nome de verdade fora de `/conta` (2026-10-26). Uma rota que já
        passa `usuario=...` explicitamente (ex. `account.conta`) apenas
        sobrescreve este valor com o mesmo dado -- sem conflito."""
        steamid = session.get("steamid")
        if not steamid:
            return {}
        return {
            "usuario": user_store.get_user(steamid),
            "avatar_local": profile_fetcher.caminho_avatar(steamid) is not None,
        }

    @app.context_processor
    def _inject_visitas_no_rodape():
        """Expõe totais de visitas pro rodapé e templates globais.

        `visits.registrar()` já soma a visita na rota `/`, então o dado de
        hoje e total está sempre disponível para todos os templates sem
        que cada rota passe isso manualmente."""
        serie = visits.serie_por_dia()
        hoje = visits.dia_local()
        visitas_hoje = next((qtd for dia, qtd in serie if dia == hoje), 0)
        return {
            "visitas_total": visits.total(),
            "visitas_hoje": visitas_hoje,
            "online_agora": online.contar(),
        }

    @app.context_processor
    def _inject_frescor_no_rodape():
        """"Dados atualizados há 2 h" no rodapé de toda página. Só um
        stat do arquivo da coleta (nada de decodificar o JSON por
        página). "Dados" e não "Preços": o arquivo também é gravado
        pela rodada rápida do Top 20 (20 itens), então o horário vale
        para os dados como um todo, não para a coleta completa.
        Atrasada = mesmo critério do banner da home (2x o intervalo
        configurado)."""
        ts = scan_store.ts_ultima_gravacao()
        if ts is None:
            return {}
        intervalo_horas = float(ambiente("WORKER_INTERVAL_HORAS", _INTERVALO_HORAS_DEFAULT))
        return {
            "coleta_quando": scan_store.idade_txt(ts),
            "coleta_atrasada": (time.time() - ts) > intervalo_horas * 3600 * 2,
        }

    @app.context_processor
    def _inject_legenda_raridade():
        """Lista fixa (7 raridades) disponível em todo template -- só a
        home e o Ranking usam hoje (popover perto da tabela), mas é
        global pra não precisar repassar manualmente se outra tela
        quiser o mesmo popover no futuro."""
        return {"legenda_raridade": raridade.legenda_raridade()}

    # Filtros Jinja: nota_classe/risco_nivel/risco_label -- centraliza a
    # classificação de nota e o rótulo de risco, repetida em 4 templates
    # até 2026-10-26 (index/item/comparar/ranking). Um filtro só precisa
    # ser registrado uma vez pra ficar disponível em todos os templates,
    # ao contrário de uma macro Jinja (que exige `{% import %}` em cada
    # arquivo).
    app.jinja_env.filters["nota_classe"] = _nota_classe
    app.jinja_env.filters["nota_anel"] = _nota_anel
    app.jinja_env.filters["risco_nivel"] = _risco_nivel
    app.jinja_env.filters["risco_label"] = _risco_label
    app.jinja_env.filters["rotulo_caixa"] = _rotulo_caixa
    app.jinja_env.filters["rotulo_caixa_curto"] = _rotulo_caixa_curto
    app.jinja_env.filters["motivo_sem_pontos"] = _motivo_sem_pontos
    app.jinja_env.filters["pontos_fmt"] = _pontos_fmt
    app.jinja_env.filters["motivo_fmt"] = _motivo_fmt
    app.jinja_env.filters["liquidez_label"] = _liquidez_label
    app.jinja_env.filters["titulo_sem_pipe_orfao"] = _titulo_sem_pipe_orfao
    app.jinja_env.filters["nome_pt"] = localize_name
    app.jinja_env.filters["data_extenso"] = _data_extenso
    app.jinja_env.globals["encomenda_sugestao"] = encomenda.sugestao

    @app.before_request
    def _marcar_inicio_latencia():
        g.inicio_ts = time.time()

    @app.before_request
    def _estatico_minificado():
        """style.css/app.js sem comentários (ver estaticos_minificados)."""
        if request.method not in ("GET", "HEAD") or not request.path.startswith("/static/"):
            return None
        nome = request.path[len("/static/"):]
        achado = estaticos_minificados.conteudo(Path(app.static_folder), nome)
        if achado is None:
            return None
        dados, etag = achado
        resp = Response(dados, mimetype=estaticos_minificados.ARQUIVOS[nome])
        resp.headers["Cache-Control"] = (
            f"public, max-age={app.config['SEND_FILE_MAX_AGE_DEFAULT']}")
        resp.set_etag(etag)
        return resp.make_conditional(request)

    @app.after_request
    def _registrar_latencia(resp):
        inicio = g.get("inicio_ts")
        if inicio is not None and request.endpoint:
            latencia.registrar(request.endpoint, (time.time() - inicio) * 1000)
        return resp

    @app.after_request
    def _sem_copia_com_login(resp):
        """Página vista com login não fica guardada no navegador: depois
        de "Sair", o botão Voltar mostraria a conta (valores pagos, lista)
        a quem usar o mesmo computador (revisão 2026-11-16). Só olha a
        sessão se o cookie existe, para não marcar toda visita anônima."""
        if ("Cache-Control" not in resp.headers and resp.mimetype == "text/html"
                and request.cookies.get(app.config["SESSION_COOKIE_NAME"])
                and session.get("steamid")):
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.route("/")
    def index():
        # Server-Timing (2026-11-14): a home levava ~0,6 s a mais que as
        # outras páginas em produção e 6 ms localmente -- o custo está em
        # disco/IO do servidor. Cada etapa sai no cabeçalho (só durações,
        # nenhum dado) pra medir em vez de adivinhar.
        _t = [("", _relogio())]

        def _marca(nome: str) -> None:
            _t.append((nome, _relogio()))

        visits.registrar()
        _marca("visitas")
        scan = scan_store.load_last_scan()
        _marca("coleta")
        categoria = request.args.get("categoria") or None
        nota_min = _parse_float_arg("nota_min")
        preco_max = _parse_float_arg("preco_max")
        busca = (request.args.get("q") or "").strip() or None
        liquidez_min = request.args.get("liquidez_min") or None
        if liquidez_min not in (None, *_LIQUIDEZ_ORDEM):
            liquidez_min = None
        exterior = request.args.get("exterior") or None
        if exterior not in _EXTERIORES:
            exterior = None
        raridade_sel = request.args.get("raridade") or None
        if raridade_sel not in raridade._RARIDADE_LABELS:
            raridade_sel = None
        versao = request.args.get("versao") or None
        if versao not in _VERSOES:
            versao = None
        filtros_steam = {"exterior": exterior, "raridade_sel": raridade_sel,
                         "versao": versao}
        # "ordenar" usa cookie de preferência: query param manda quando
        # presente, senão cai pro último escolhido (sem isso, re-ordenar
        # por preço não sobrevivia a uma nova visita).
        ordenar = (request.args.get("ordenar") if "ordenar" in request.args
                  else request.cookies.get("pref_ordenar")) or "nota"
        if ordenar not in ("nota", "preco"):
            ordenar = "nota"
        # Como mostrar a lista (revisão de direção visual 2026-11-08,
        # rodada 2): "vitrine" é a grade de cards com imagem grande;
        # "lista" é a tabela densa de sempre. Cookie guarda a escolha
        # (igual `pref_ordenar`) pra sobreviver a filtros e paginação --
        # sem isso, todo link interno voltaria pro modo padrão.
        ver = (request.args.get("ver") if "ver" in request.args
               else request.cookies.get("pref_ver")) or "vitrine"
        if ver not in ("vitrine", "lista"):
            ver = "vitrine"
        pagina = _parse_int_arg("pagina", 1)
        if busca:
            buscas.registrar(busca)

        base_candidatos = (
            recommendations.buy_candidates(
                scan["results"], owned_names=set(),
                limit=len(scan["results"]) or 1)
            if scan else [])
        # Abas de categoria contam o que a pessoa VAI VER ao clicar: a
        # mesma lista filtrada (busca, nota, preço, liquidez), só sem a
        # categoria. Filtra uma vez só (sem formatar os ~270 itens fora da
        # página) e deriva a aba selecionada da própria lista.
        sem_categoria = _candidatos_filtrados(
            scan, None, nota_min, preco_max, busca, ordenar, liquidez_min,
            com_historico=False, com_icone=False, formatar=False,
            base_candidatos=base_candidatos, **filtros_steam)
        todos = ([c for c in sem_categoria if c.get("category") == categoria]
                 if categoria else sem_categoria)
        total_geral = len(sem_categoria)
        # Itens coletados que a lista nunca mostra (risco alto de alta
        # artificial, descartados em `buy_candidates`). A linha de status
        # conta o scan inteiro; sem isto ela dizia 183 e a aba "Todas" 173,
        # sem explicar a diferença (2026-11-14).
        ocultos_risco = (len(scan["results"]) - len(base_candidatos)) if scan else 0
        contagem_abas: dict = {}
        for c in sem_categoria:
            if c.get("category"):
                contagem_abas[c["category"]] = contagem_abas.get(c["category"], 0) + 1
        # Catálogo amplo (plans/archive/catalogo-grande.md, fase 2): com
        # busca ou com os filtros "da Steam", a lista continua com os itens
        # que têm nota e depois traz o resto do mercado, "sem nota ainda".
        # Nota mínima e liquidez só existem nos itens com nota. Sem busca
        # nem filtro, a home fica igual (as notas de hoje). Só SQLite local.
        usa_catalogo = bool(busca or exterior or raridade_sel or versao
                            or preco_max is not None) \
            and nota_min is None and not liquidez_min
        filtros_cat = {"busca": busca, "categoria": categoria,
                       "exterior": exterior, "raridade": raridade_sel,
                       "versao": versao, "preco_max": preco_max}
        nomes_com_nota = ([r["name"] for r in scan["results"]]
                          if scan else [])
        total_cat = 0
        if usa_catalogo:
            # Uma contagem só, por categoria (revisão 17/11: a busca contava
            # o catálogo duas vezes, 0,1-0,4 s): o total da aba escolhida
            # sai dela, e a página de itens não conta de novo.
            por_categoria = catalogo.contar_por_categoria(
                filtros_cat, nomes_com_nota)
            total_cat = (por_categoria.get(categoria, 0) if categoria
                         else sum(por_categoria.values()))
            for cat, n in por_categoria.items():
                contagem_abas[cat] = contagem_abas.get(cat, 0) + n
                total_geral += n
        total_itens = len(todos) + total_cat
        total_paginas = max(1, -(-total_itens // _PAGINA_TAMANHO))
        # Link antigo (?pagina=15 depois que a lista encolheu) ou digitado
        # à mão: mostra a última página que existe em vez de uma lista
        # vazia sem explicação.
        pagina = min(max(1, pagina), total_paginas)
        inicio = (pagina - 1) * _PAGINA_TAMANHO
        candidatos_pagina = todos[inicio:inicio + _PAGINA_TAMANHO]
        _enriquecer_formatacao(candidatos_pagina)
        itens_catalogo_pagina: list = []
        falta = _PAGINA_TAMANHO - len(candidatos_pagina)
        if usa_catalogo and falta > 0 and total_cat:
            _total_ignorado, linhas = catalogo.consultar(
                filtros_cat, nomes_com_nota, ordenar, limite=falta,
                offset=max(0, inicio - len(todos)), contar=False)
            itens_catalogo_pagina = [_cartao_do_catalogo(r) for r in linhas]
        _marca("filtro")
        _enriquecer_com_historico(candidatos_pagina)
        _marca("historico")
        _enriquecer_com_icone(candidatos_pagina)
        _marca("icones")
        intervalo_horas = float(ambiente("WORKER_INTERVAL_HORAS", _INTERVALO_HORAS_DEFAULT))
        # Banner de "dado pode estar desatualizado" -- pedido depois do
        # bloqueio real de 429 que durou horas (2026-10-25): sem isto, a
        # tabela mostra dado velho em silêncio, como se fosse de agora.
        # 2x o intervalo configurado é a margem (um ciclo atrasado não
        # é anormal; dois seguidos geralmente é bloqueio da Steam).
        scan_desatualizado = bool(
            scan and (time.time() - scan["ts"]) > intervalo_horas * 3600 * 2)
        # Resumo "o que mudou hoje" (item #19 da lista de melhorias) -- só
        # na visão principal (página 1, sem filtro algum): com filtro ou
        # paginação ativos, o item citado podia nem aparecer na lista
        # abaixo, confuso. Reaproveita o MESMO snapshot do Top 20 que o
        # Ranking já usa (_resumo_do_dia) -- sem inventar uma segunda
        # fonte de comparação histórica.
        sem_filtro_ativo = not (categoria or nota_min or preco_max or busca
                                or liquidez_min or exterior or raridade_sel
                                or versao)
        resumo_do_dia = None
        if pagina == 1 and sem_filtro_ativo:
            snaps = ranking.load_snapshots()
            resumo_do_dia = _resumo_do_dia(snaps[-1] if snaps else None)
        _marca("ranking")
        # Hero "nota mais alta hoje" (revisão de direção visual
        # 2026-11-08) -- a home abria direto no formulário de filtro, sem
        # nenhum "rosto". Mesma condição de resumo_do_dia (só na visão
        # principal, sem filtro/busca, senão o item destacado podia nem
        # estar na lista abaixo) + ordenar == "nota": candidatos_pagina[0]
        # só é de fato "o maior nota" quando a ordenação é por nota.
        # Tom deliberadamente factual ("nota mais alta", não "melhor" ou
        # "destaque") -- é uma leitura do dado, não uma recomendação (ver
        # AGENTS.md, "não promete retorno").
        destaque_hero = None
        if pagina == 1 and sem_filtro_ativo and ordenar == "nota" and candidatos_pagina:
            destaque_hero = candidatos_pagina[0]
        resp = make_response(render_template(
            "index.html",
            candidatos=candidatos_pagina,
            destaque_hero=destaque_hero,
            scan=scan,
            resumo_do_dia=resumo_do_dia,
            idade=scan_store.idade_txt(scan["ts"]) if scan else None,
            proximo_scan=(scan_store.proxima_txt(scan["ts"], intervalo_horas)
                         if scan else None),
            scan_desatualizado=scan_desatualizado,
            ocultos_risco=ocultos_risco,
            categorias=sorted(set(scan_targets.SCAN_BY_CATEGORY.keys())
                              | set(contagem_abas.keys())),
            contagem_categorias=_contagem_por_categoria(scan),
            contagem_abas=contagem_abas,
            filtro_alem_da_categoria=bool(
                nota_min or preco_max or busca or liquidez_min or exterior
                or raridade_sel or versao),
            exterior_sel=exterior,
            raridade_filtro_sel=raridade_sel,
            versao_sel=versao,
            exterior_opcoes={k: v[1] for k, v in _EXTERIORES.items()},
            raridade_opcoes=raridade._RARIDADE_LABELS,
            versao_opcoes=_VERSOES,
            # O filtro de Versão só aparece quando há itens StatTrak™/
            # Souvenir para filtrar: na coleta com nota (checado antes em
            # memória para não abrir SQLite à toa) ou no catálogo.
            mostrar_versao=bool(versao) or any(
                _versao_do_item(r.get("name") or "") != "normal"
                for r in (scan or {}).get("results") or []
            ) or catalogo.tem_dados(),
            total_acompanhados=len(scan["results"]) if scan else 0,
            total_geral=total_geral,
            categoria_sel=categoria,
            nota_min_sel=nota_min,
            preco_max_sel=preco_max,
            liquidez_min_sel=liquidez_min,
            liquidez_opcoes=_LIQUIDEZ_ORDEM,
            busca_sel=busca,
            ordenar_sel=ordenar,
            ver_sel=ver,
            pagina=pagina,
            primeiro_item=inicio + 1,
            ultimo_item=inicio + len(candidatos_pagina) + len(itens_catalogo_pagina),
            tem_proxima_pagina=total_itens > inicio + _PAGINA_TAMANHO,
            tem_pagina_anterior=pagina > 1,
            total_candidatos=total_itens,
            itens_catalogo=itens_catalogo_pagina,
            total_com_nota=len(todos),
            total_catalogo=total_cat,
            total_paginas=total_paginas,
            paginas_visiveis=_paginas_visiveis(pagina, total_paginas),
        ))
        _UM_ANO_S = 365 * 24 * 3600
        if "ordenar" in request.args:
            # `secure` segue a mesma config do cookie de sessão -- fixo
            # em True quebraria o dev local (http); achado 2026-11-01:
            # esse cookie não tinha a flag nenhuma, inconsistente com
            # SESSION_COOKIE_SECURE.
            resp.set_cookie("pref_ordenar", ordenar, max_age=_UM_ANO_S,
                            samesite="Lax",
                            secure=app.config["SESSION_COOKIE_SECURE"])
        if "ver" in request.args:
            resp.set_cookie("pref_ver", ver, max_age=_UM_ANO_S,
                            samesite="Lax",
                            secure=app.config["SESSION_COOKIE_SECURE"])
        _marca("pagina")
        resp.headers["Server-Timing"] = ", ".join(
            f"{nome};dur={(fim - ini) * 1000:.1f}"
            for (_, ini), (nome, fim) in zip(_t, _t[1:]))
        return resp

    @app.route("/item/<name>")
    def item_detail(name: str):
        """Página por item -- permalink compartilhável. Enxuta desde 21/11
        (pedido do usuário): resumo, simulador e motivos da nota, sem
        gráficos nem listas extras. Sem chamada à Steam: os mesmos dados já
        calculados em `_candidatos_filtrados`, filtrados pelo nome.

        `com_historico=False` (2026-10-27): esta rota nunca usou
        `tendencia`/`sparkline` dos ~150 candidatos. Mesmo bug que o `index()` já teve
        corrigido em 2026-10-26 (ler histórico de TODOS os candidatos
        quando só um é exibido), que não tinha se propagado pra cá."""
        scan = scan_store.load_last_scan()
        item = _candidato_por_nome(scan, name)
        if item is None:
            # Item do catálogo amplo, sem nota ainda (catalogo-grande.md,
            # fase 2): página simples com preço do dia e a conta da revenda.
            # Item que tem nota mas está fora da lista (risco alto de alta
            # artificial) não vira "sem nota ainda": continua como antes.
            no_scan = any(r.get("name") == name
                          for r in (scan or {}).get("results") or [])
            linha = None if no_scan else catalogo.item(name)
            if linha is None or linha.get("preco") is None:
                # Nome errado ou link antigo (revisão 17/11): diz qual item
                # não achou, deixa o nome na busca e sugere parecidos.
                parecidos = [] if no_scan else [
                    _cartao_do_catalogo(r) for r in catalogo.parecidos(name)
                    if r.get("nome") != name]
                return render_template(
                    "404.html", item_procurado=name[:120],
                    item_procurado_fmt=localize_name(name)[:120],
                    parecidos=parecidos), 404
            item_cat = _cartao_do_catalogo(linha)
            na_conta = _na_sua_conta(name)
            return _resposta_item(render_template(
                "item_catalogo.html", item=item_cat,
                preco_empate=fmt.brl(portfolio.break_even_price(item_cat["price"])),
                # Sem fila de encomendas no catálogo. Passar None evita que
                # o partial pegue a função global de mesmo nome (revisão 20/11:
                # aparecia um botão de copiar vazio e "…encomenda, , e %").
                encomenda_sugestao=None,
                taxa_steam_pct=round(portfolio.STEAM_FEE * 100),
                na_conta=na_conta), na_conta)
        # Página enxuta (21/11, pedido do usuário): sem gráficos, parecidos,
        # outras versões e histórico no ranking. Ícone só deste item.
        _enriquecer_com_icone([item])
        hist = signals.load_item_history(name)
        na_conta = _na_sua_conta(name)
        fila_encomenda = next((r.get("encomenda") for r in (scan or {}).get("results") or []
                               if r.get("name") == name), None)
        return _resposta_item(render_template(
            "item.html",
            item=item,
            na_conta=na_conta,
            tempo_aposentadoria=_tempo_desde_aposentadoria(item.get("case_retired_at")),
            eventos_jogo=_eventos_do_jogo(set(), so_do_item=name),
            itens_da_caixa=cases.skins_in_case(item.get("case")),
            # "Para revender sem prejuízo" (2026-11-15): quem entra no site
            # compra pensando em vender mais caro depois, e muito iniciante
            # não sabe que a Steam fica com ~15% de cada venda. Mesma conta
            # da carteira (portfolio.break_even_price).
            preco_empate=(fmt.brl(portfolio.break_even_price(item["price"]))
                          if item.get("price") else None),
            # A mesma sugestão do Ranking (frente da fila), copiável (17/11).
            encomenda_sugestao=encomenda.sugestao(item.get("price"), fila_encomenda),
            # O simulador compara a oferta com a maior encomenda real (sem
            # isto, a sugestão de +R$ 0,01 aparecia como "empatado no topo").
            fila_encomenda=fila_encomenda,
            taxa_steam_pct=round(portfolio.STEAM_FEE * 100),
            # Preço mais recente DESTE item específico -- cada item do
            # scan é coletado em instantes diferentes dentro do ciclo de
            # ~25min (ver scan_engine.run_full_scan), então isto é mais
            # preciso que a idade do scan como um todo.
            preco_coletado_txt=(
                scan_store.idade_txt(hist[-1]["ts"]) if hist else None),
        ), na_conta)

    def _na_sua_conta(name: str):
        """"Na sua conta" na página do item (só com login)."""
        from lodout.public_site import account as _conta
        try:
            return _conta.resumo_na_conta(session.get("steamid"), name)
        except Exception:
            _logger.warning("resumo da conta no item falhou", exc_info=True)
            return None

    def _resposta_item(html: str, na_conta):
        """Com dados da conta na página, a resposta é só desta pessoa:
        nada de cache compartilhado."""
        resp = make_response(html)
        if na_conta:
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.route("/og/item.png")
    @rate_limit.rate_limited(rate_limit.API_MAX_HITS, rate_limit.API_WINDOW_S)
    def og_item():
        """Imagem de prévia (1200x630) do item, pra quando o link dele é
        compartilhado. Só dado já guardado: o ícone sai do cache local
        (nunca busca no CDN da Steam aqui) e a imagem fica em cache em
        disco até nota/preço mudarem. Nome fora da lista do site: 404."""
        nome = request.args.get("nome") or ""
        scan = scan_store.load_last_scan()
        item = _candidato_por_nome(scan, nome)
        if item is None:
            return "", 404
        icone = None
        hash_icone = item.get("icon")
        if hash_icone:
            # Só disco (v4, ou gerado do v3 guardado): a prévia nunca
            # depende do CDN da Steam.
            for tamanho in (384, icon_cache.TAMANHO_PADRAO):
                icone = icon_cache.ler_local(hash_icone, tamanho)
                if icone:
                    break
        dados = og_cards.cartao_item_em_cache(
            item.get("name_fmt") or nome, item.get("score"),
            item.get("price_fmt") or "",
            raridade.raridade_suffix(item) or None, icone)
        resp = Response(dados, mimetype="image/png")
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    @app.route("/comparar")
    def comparar():
        """Até 3 itens lado a lado -- a seleção em si vive no
        `sessionStorage` do navegador (`app.js`), isto só resolve os
        nomes recebidos em `?nomes=A,B,C` pros dados já calculados.

        `com_historico=False` + `_enriquecer_com_historico` só nos até 3
        itens exibidos (2026-10-27): `comparar.html` usa `tendencia`
        (não `sparkline`), mas só dos itens comparados -- calcular pros
        ~150 candidatos inteiros pra mostrar no máximo 3 era o mesmo
        desperdício já corrigido no `index()` em 2026-10-26."""
        scan = scan_store.load_last_scan()
        nomes = [n for n in (request.args.get("nomes") or "").split(",") if n][:3]
        itens = []
        if scan and nomes:
            nomes_set = set(nomes)
            alvos = [r for r in scan.get("results") or []
                     if r.get("name") in nomes_set]
            base = (recommendations.buy_candidates(
                alvos, owned_names=set(), limit=len(alvos) or 1)
                if alvos else [])
            por_nome = {
                c["name"]: _formatar_candidato(
                    dict(c), com_icone=False, com_historico=False)
                for c in base
            }
            itens = [por_nome[n] for n in nomes if n in por_nome]
        _enriquecer_com_historico(itens)
        _enriquecer_com_icone(itens)
        menor_preco, _ = _destaques_comparar(itens, "price")
        _, maior_nota = _destaques_comparar(itens, "score")
        for it in itens:
            it["preco_destaque"] = it.get("name") in menor_preco
            it["nota_destaque"] = it.get("name") in maior_nota
        return render_template("comparar.html", itens=itens)

    @app.route("/api/recommendations")
    @rate_limit.rate_limited(rate_limit.API_MAX_HITS, rate_limit.API_WINDOW_S)
    def api_recommendations():
        scan = scan_store.load_last_scan()
        candidatos = _candidatos_filtrados(
            scan, com_historico=False, com_icone=False,
            formatar=False)[:_LIMIT_CANDIDATOS]
        _enriquecer_formatacao(candidatos)
        _enriquecer_com_historico(candidatos)
        _enriquecer_com_icone(candidatos)
        resp = jsonify({
            "api_version": 1,
            "ultimo_scan": {
                "categoria": scan["category"] if scan else None,
                "ts": scan["ts"] if scan else None,
            },
            "candidatos": candidatos,
        })
        # O dado só muda quando um ciclo do worker termina (até 6h) --
        # cache curto evita reprocessar `_candidatos_filtrados` (passa
        # por `recommendations.buy_candidates` + localize_name por item)
        # a cada poll de quem consome a API programaticamente.
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True})

    @app.route("/readyz")
    def readyz():
        """Diferente de `/healthz` (só "o processo está de pé"): confere
        se dá pra abrir o banco de contas (quando existe) sem exceção --
        pensado pro orquestrador saber se pode receber tráfego de
        verdade, não só se o container iniciou. `scan_store` nunca
        levanta exceção por design (ver `load_last_scan`), então só o
        banco é checado de fato."""
        motivos = []
        for rotulo, caminho_db in (
            ("banco", db_backup._DB_PATH),
            ("notas", notas_historico._caminho()),
        ):
            if caminho_db.exists():
                conn = None
                try:
                    conn = sqlite3.connect(str(caminho_db), timeout=3.0)
                    conn.execute("PRAGMA busy_timeout=3000")
                    # Força ler o cabeçalho/schema de verdade -- "SELECT 1"
                    # não toca em nenhuma página do arquivo, então um banco
                    # corrompido passava como "pronto" (achado escrevendo o
                    # teste, 2026-10-25).
                    conn.execute("SELECT count(*) FROM sqlite_master")
                except sqlite3.Error as e:
                    motivos.append(f"{rotulo}: {e}")
                finally:
                    if conn is not None:
                        conn.close()
        if motivos:
            return jsonify({"ready": False, "motivos": motivos}), 503
        return jsonify({"ready": True})

    @app.route("/api/health")
    def api_health():
        """Versão detalhada do /healthz -- pensada pra quem consome a API
        saber SE pode confiar no dado agora, não só se o processo web
        está de pé (achado de 2026-10-25: distinguir "site no ar" de
        "dado fresco" importa depois do incidente de hoje)."""
        scan = scan_store.load_last_scan()
        ciclos = scan_store.load_historico_ciclos()
        ultimo_ciclo = ciclos[-1] if ciclos else None
        if ultimo_ciclo is not None:
            ultimo_ciclo = dict(ultimo_ciclo)
            ultimo_ciclo.update({
                "pausas_429": int(ultimo_ciclo.get("pausas_429") or 0),
                "encerrou_por_429": bool(
                    ultimo_ciclo.get("encerrou_por_429")),
                "ciclo_completo": scan_store.ciclo_completo(ultimo_ciclo),
                "ciclo_sem_pausa": scan_store.ciclo_sem_pausa(ultimo_ciclo),
            })
        rodadas_top = scan_store.resumo_rodadas_top()
        intervalo_horas = float(ambiente("WORKER_INTERVAL_HORAS", _INTERVALO_HORAS_DEFAULT))
        return jsonify({
            "ok": True,
            "api_version": 1,
            "scan": {
                "disponivel": scan is not None,
                "idade_segundos": (
                    round(time.time() - scan["ts"], 1) if scan else None),
                "itens": len(scan["results"]) if scan else 0,
            },
            "ultimo_ciclo_worker": ultimo_ciclo,
            # Catálogo amplo (plans/archive/catalogo-grande.md): tamanho,
            # páginas, bloqueios e tamanho real da página da Steam.
            "catalogo": catalogo.resumo(),
            # "A nota acertou no passado?" (backtest_diario.py): só leitura.
            "backtest": backtest_diario.ler(),
            "ultima_rodada_top": scan_store.load_rodada_top(),
            # 26/11: última boa acima; aqui o histórico recente, incluindo
            # rodadas cortadas por 429, pra medir "falha recorrente" sem SSH.
            "ultimas_rodadas_top": rodadas_top["rodadas"],
            "top20_total_recentes": rodadas_top["total"],
            "top20_falhas_recentes": rodadas_top["falhas"],
            # Idade em horas do backup mais recente de cada grupo
            # (banco/notas/json), ou None se nunca houve um. Mesmo dado
            # que alimenta o alerta de backup atrasado (worker_alert.py).
            "backups": db_backup.idade_dos_backups(),
            "intervalo_horas_configurado": intervalo_horas,
            "no_ar_desde": uptime.no_ar_desde(),
            "visitas_total": visits.total(),
        })

    @app.route("/icone/<hash_icone>.webp")
    @rate_limit.rate_limited(rate_limit.ICON_MAX_HITS, rate_limit.ICON_WINDOW_S)
    def icone_cache(hash_icone: str):
        """Ícone servido do próprio domínio (ver `icon_cache.py`) --
        cache em disco, só busca do CDN da Steam na primeira vez que
        aquele hash aparece (reencodando PNG/JPEG pra WebP, preservando
        transparência). Nunca 500: cache miss + rede fora
        vira redirect pro CDN direto, nunca erro pro visitante.

        `?tam=` (2026-11-08) escolhe entre os tamanhos de
        `icon_cache.TAMANHOS_PERMITIDOS` -- valor fora da lista (ou
        ausente) cai no padrão de 192px, nunca erro. Alimenta o
        `srcset` 2x que os templates já declaram (ver `icon_url_2x`).

        Rate limit (2026-10-27): sem login, cache miss grava arquivo
        novo em disco pra QUALQUER hash -- sem isto, um script batendo
        com hash diferente a cada chamada enche o disco sem fim (ver
        rate_limit.ICON_MAX_HITS)."""
        tamanho = _parse_int_arg("tam", icon_cache.TAMANHO_PADRAO)
        if tamanho not in icon_cache.TAMANHOS_PERMITIDOS:
            tamanho = icon_cache.TAMANHO_PADRAO
        dados = icon_cache.obter(hash_icone, tamanho)
        if dados is None:
            return redirect(
                _ICON_CDN_URL_2X.format(hash=hash_icone, tamanho=tamanho))
        resp = Response(dados, mimetype="image/webp")
        resp.headers["Cache-Control"] = "public, max-age=2592000, immutable"
        return resp

    @app.route("/sw.js")
    def service_worker():
        """Fora de `/static/` de propósito: um service worker só
        controla (scope) o diretório onde é servido, a menos que o
        servidor mande `Service-Worker-Allowed` -- rota própria na raiz
        é mais simples que configurar esse header por cima do
        `/static/` do Flask."""
        resp = send_from_directory(_STATIC_DIR, "sw.js")
        resp.headers["Service-Worker-Allowed"] = "/"
        return resp

    # Verificação de propriedade do Google Search Console (método
    # "Arquivo HTML", propriedade https://lodout.com/). O Google pede que
    # o arquivo continue no ar depois de verificado. O conteúdo é o padrão
    # fixo do Google: "google-site-verification: <nome do arquivo>".
    @app.route(f"/{_GOOGLE_VERIFICACAO}.html")
    def google_verificacao():
        return Response(
            f"google-site-verification: {_GOOGLE_VERIFICACAO}.html",
            mimetype="text/html")

    @app.route("/api/sugestoes")
    @rate_limit.rate_limited(rate_limit.SUGESTAO_MAX_HITS, rate_limit.SUGESTAO_WINDOW_S)
    def sugestoes_de_nome():
        """Nomes exatos do Mercado enquanto a pessoa digita (formulários de
        Watchlist, Trades e "Adicionar um item à mão", pedido 17/11), em
        português ou inglês, com o preço de hoje. Só o banco local: o
        catálogo e a última coleta; nunca a Steam."""
        q = (request.args.get("q") or "").strip()[:80]
        if len(q) < 2 or not catalogo._termos_busca_or(q):
            return jsonify([])
        grupos_busca = _compilar_busca(q)
        candidatos: list = []
        vistos: set = set()
        scan = scan_store.load_last_scan() or {}
        for r in scan.get("results") or []:
            nome = r.get("name") or ""
            if not nome or nome in vistos:
                continue
            nome_pt = localize_name(nome)
            if _busca_bate_compilada(
                    _texto_busca(_nome_para_busca(nome, nome_pt)),
                    grupos_busca):
                score = r.get("score")
                tem_score = isinstance(score, (int, float))
                candidatos.append((
                    catalogo.relevancia_busca(nome, nome_pt, q),
                    0 if tem_score else 1,
                    -float(score) if tem_score else 1.0,
                    0,
                    nome.lower(),
                    "scan",
                    nome,
                    nome_pt,
                    r,
                ))
                vistos.add(nome)
        _total, linhas = catalogo.consultar(
            {"busca": q}, list(vistos), ordenar="relevancia",
            limite=24, contar=False,
        )
        for linha in linhas:
            nome_cat = linha["nome"]
            if not nome_cat or nome_cat in vistos:
                continue
            vistos.add(nome_cat)
            nome_pt_cat = localize_name(nome_cat)
            a_venda = int(linha.get("a_venda") or 0)
            candidatos.append((
                catalogo.relevancia_busca(nome_cat, nome_pt_cat, q),
                1,
                1.0,
                -a_venda,
                nome_cat.lower(),
                "catalogo",
                nome_cat,
                nome_pt_cat,
                linha,
            ))
        candidatos.sort(key=lambda c: c[:5])
        out = []
        for _rk, _ts, _sc, _av, _nl, origem, nome, nome_pt, dado in candidatos[:8]:
            if origem == "scan":
                preco_num = dado.get("price") if isinstance(dado.get("price"), (int, float)) else None
                h = dado.get("icon")
                score = dado.get("score")
                rar_cls = raridade.raridade_classe(dado)
            else:
                preco_num = dado.get("preco")
                h = dado.get("icon")
                score = None
                rar_cls = f"raridade-{dado['raridade']}" if dado.get("raridade") else ""
            out.append({
                "nome": nome,
                "nome_pt": nome_pt,
                "preco": preco_num,
                "preco_fmt": fmt.brl(preco_num) if preco_num is not None else None,
                "score": score,
                "icon_url": url_for("icone_cache", hash_icone=h, v=3) if h else None,
                "raridade_classe": rar_cls,
                "url": url_for("item_detail", name=nome),
            })
        resp = jsonify(out)
        resp.headers["Cache-Control"] = "private, max-age=300"
        return resp

    @app.route("/api/online", methods=["POST"])
    @rate_limit.rate_limited(rate_limit.ONLINE_MAX_HITS, rate_limit.ONLINE_WINDOW_S)
    def online_agora():
        """"Estou aqui" de uma aba aberta (static/online.js, pedido do
        usuário 17/11): guarda só um código aleatório da aba e a hora, e
        devolve quantas abas estão no site agora. Sem sessão nem CSRF: não
        mexe em dado de ninguém."""
        dados = request.get_json(silent=True) or {}
        codigo = dados.get("id") if isinstance(dados, dict) else None
        if not online.id_valido(codigo):
            return jsonify({"erro": "código inválido"}), 400
        try:
            online.marcar(codigo)
        except Exception:
            _logger.warning("registro de quem está no site falhou", exc_info=True)
        return jsonify({"agora": online.contar()})

    @app.route("/favicon.ico")
    def favicon_ico():
        """Navegadores antigos, leitores de feed e alguns apps pedem o
        ícone neste endereço fixo, sem ler o <link rel="icon"> (revisão
        17/11: dava "página não encontrada"). Vai o .ico com 16, 32 e 48 px."""
        resp = send_from_directory(_STATIC_DIR, "favicon.ico",
                                   mimetype="image/x-icon")
        resp.cache_control.public = True
        resp.cache_control.max_age = 86400
        return resp

    @app.route("/robots.txt")
    def robots():
        # Disallow /admin em defesa de profundidade (2026-10-25) -- o token
        # já nega sem ele (ver rota `admin` abaixo), isto só evita que um
        # crawler sequer tente a URL ou a indexe se alguém linkar por engano.
        texto = (
            "User-agent: *\nAllow: /\nDisallow: /admin\n"
            f"Sitemap: {request.url_root}sitemap.xml\n")
        return Response(texto, mimetype="text/plain")

    @app.route("/api/csp-report", methods=["POST"])
    @rate_limit.rate_limited(
        rate_limit.CSP_REPORT_MAX_HITS, rate_limit.CSP_REPORT_WINDOW_S)
    def csp_report():
        """Endpoint de `report-uri` do CSP (Caddyfile) -- sem isto, uma
        violação de política só aparecia se um visitante abrisse o
        DevTools e reclamasse. Registrado como erro (mesmo pipeline do
        `/admin`) pra aparecer nos "Últimos erros" sem precisar de SSH.
        Sem CSRF/sessão: é o navegador que posta isto sozinho, nunca um
        formulário."""
        try:
            corpo = request.get_data(as_text=True)[:2000]
            app.logger.error("CSP violation: %s", corpo)
        except Exception:
            pass
        return "", 204

    @app.route("/sitemap.xml")
    @rate_limit.rate_limited(rate_limit.API_MAX_HITS, rate_limit.API_WINDOW_S)
    def sitemap():
        base = request.url_root.rstrip("/")
        paginas = ["/", "/privacidade", "/status", "/changelog", "/api",
                  "/ranking", "/novidades", "/metodo", "/sobre", "/faq",
                  "/glossario", "/como-usar"]
        urls_xml = "\n".join(
            f"  <url><loc>{_xml_escape(base + p)}</loc></url>" for p in paginas)
        # Páginas de item -- cada uma já tem título/descrição/JSON-LD
        # própria, mas sem link aqui um crawler só as acha indiretamente
        # via paginação da home (mais lento e menos confiável do que
        # listar direto). Mesma lista que `item_detail` usa -- um nome
        # fora dela dá 404, então o sitemap não pode divergir.
        scan = scan_store.load_last_scan()
        if scan:
            candidatos = _candidatos_filtrados(
                scan, com_historico=False, com_icone=False, formatar=False)
            itens_xml = "\n".join(
                f"  <url><loc>{_xml_escape(base + url_for('item_detail', name=c['name']))}</loc></url>"
                for c in candidatos)
            if itens_xml:
                urls_xml = urls_xml + "\n" + itens_xml
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls_xml}\n"
            "</urlset>\n"
        )
        return Response(xml, mimetype="application/xml")

    @app.route("/opensearch.xml")
    def opensearch():
        """Descrição OpenSearch -- deixa o navegador oferecer "Adicionar
        mecanismo de busca: lodout" na barra de endereço, usando a
        própria busca por nome (`q=`) que a página inicial já tem."""
        base = request.url_root.rstrip("/")
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">\n'
            "  <ShortName>lodout</ShortName>\n"
            "  <Description>Buscar uma skin de Counter-Strike 2 por nome no Lodout"
            "</Description>\n"
            f"  <Image width=\"32\" height=\"32\" type=\"image/svg+xml\">{_xml_escape(base)}/static/favicon.svg</Image>\n"
            f"  <Url type=\"text/html\" template=\"{_xml_escape(base)}/?q={{searchTerms}}\"/>\n"
            "  <InputEncoding>UTF-8</InputEncoding>\n"
            "</OpenSearchDescription>\n"
        )
        return Response(xml, mimetype="application/xml")

    @app.errorhandler(404)
    def pagina_nao_encontrada(_erro):
        if request.path.startswith("/api/"):
            return jsonify({"api_version": 1, "erro": "nao_encontrado",
                            "mensagem": "Rota não existe."}), 404
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def acesso_negado(_erro):
        """Hoje só o CSRF responde 403 com página: formulário de uma aba
        aberta antes de sair e entrar de novo. Antes era o "Forbidden" em
        inglês do Flask (revisão 2026-11-16)."""
        if request.path.startswith("/api/"):
            return jsonify({"api_version": 1, "erro": "acesso_negado",
                            "mensagem": "Acesso negado."}), 403
        # Volta à página de onde veio o formulário, se for deste site.
        voltar = None
        origem = urllib.parse.urlparse(request.referrer or "")
        if (origem.netloc == request.host and origem.path.startswith("/")
                and not origem.path.startswith("//")):
            voltar = origem.path + (f"?{origem.query}" if origem.query else "")
        if not voltar:
            voltar = url_for("account.conta") if session.get("steamid") else url_for("index")
        return render_template("403.html", voltar=voltar), 403

    @app.errorhandler(500)
    def erro_interno(erro):
        app.logger.error("500 em %s: %r", request.path, erro, exc_info=erro)
        if request.path.startswith("/api/"):
            return jsonify({"api_version": 1, "erro": "erro_interno",
                            "mensagem": "Erro interno do servidor."}), 500
        return render_template("500.html"), 500

    @app.errorhandler(429)
    def limite_excedido(_erro):
        # Achado da skill api-and-interface-design (2026-11-05): os três
        # handlers devolviam HTML mesmo pra /api/* -- quem consome a API
        # programaticamente (ver /api) recebia uma página inteira em vez
        # de JSON num erro, quebrando qualquer client que só espera JSON.
        if request.path.startswith("/api/"):
            resp = make_response(jsonify({
                "api_version": 1,
                "erro": "limite_excedido",
                "mensagem": "Muitas tentativas. Tente de novo mais tarde.",
            }), 429)
        else:
            resp = make_response(render_template("429.html"), 429)
        resp.headers["Retry-After"] = "60"
        return resp

    @app.errorhandler(413)
    def corpo_grande_demais(_erro):
        if request.path.startswith("/api/"):
            return jsonify({
                "api_version": 1,
                "erro": "corpo_grande_demais",
                "mensagem": "Requisição maior que o limite permitido.",
            }), 413
        return "Requisição grande demais.", 413

    @app.route("/privacidade")
    def privacidade():
        return render_template("privacidade.html")

    @app.route("/changelog")
    def changelog_page():
        return render_template("changelog.html", entradas=changelog.ENTRADAS)

    @app.route("/changelog.xml")
    def changelog_feed():
        base = request.url_root.rstrip("/")
        link_changelog = f"{base}/changelog"
        itens_xml = "\n".join(
            "    <item>\n"
            f"      <title>{_xml_escape(e['data'])} — {_xml_escape(e['titulo'])}</title>\n"
            # Opcional pela spec RSS 2.0, mas sem nenhum <link> o item não
            # tinha pra onde clicar -- achado 2026-11-01. Sem âncora por
            # entrada ainda (changelog.html não tem id por data), então
            # aponta pra página toda.
            f"      <link>{_xml_escape(link_changelog)}</link>\n"
            f"      <description>{_xml_escape('; '.join(e['itens']))}</description>\n"
            f"      <guid isPermaLink=\"false\">{_xml_escape(e['data'])}</guid>\n"
            "    </item>"
            for e in changelog.ENTRADAS
        )
        rss = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>\n'
            "  <title>Lodout — Mudanças</title>\n"
            f"  <link>{_xml_escape(link_changelog)}</link>\n"
            "  <description>O que mudou no site, por data.</description>\n"
            "  <language>pt-BR</language>\n"
            f"{itens_xml}\n"
            "</channel></rss>\n"
        )
        return Response(rss, mimetype="application/rss+xml",
                        headers={"Cache-Control": "public, max-age=3600"})

    @app.route("/metodo")
    def metodo():
        return render_template("metodo.html")

    @app.route("/faq")
    def faq():
        return render_template("faq.html")

    @app.route("/glossario")
    def glossario():
        return render_template("glossario.html")

    # Guia para iniciantes (pedido do usuário, 26/11): resume e linka o
    # Método e o Glossário, que continuam sendo a fonte completa.
    @app.route("/como-usar")
    def como_usar():
        return render_template("como_usar.html")

    @app.route("/sobre")
    def sobre():
        return render_template("sobre.html")

    @app.route("/novidades")
    def novidades():
        """Mudanças detectadas nos arquivos do jogo + anúncios oficiais
        do CS2. Só lê o que o worker já gravou -- abrir esta página não
        faz nenhuma requisição externa."""
        # Só vira link o nome que `item_detail` aceita (mesma lista dele);
        # um nome fora dela daria 404.
        nomes = _nomes_com_pagina(scan_store.load_last_scan())
        try:
            estado = gamedata.load_state() or {}
        except Exception:
            estado = {}
        conferido_ts = estado.get("fetched_at")
        return render_template(
            "novidades.html",
            eventos=_eventos_do_jogo(nomes),
            noticias=_noticias_oficiais(),
            arquivos_conferidos_txt=(
                scan_store.idade_txt(conferido_ts)
                if isinstance(conferido_ts, (int, float)) else None),
        )

    @app.route("/ranking")
    def ranking_page():
        """Os melhores de forma consistente (pedido do usuário, 17/11): quem
        quer comprar procura o que se mantém bem avaliado, não o que bateu
        100 numa coleta. Ordem pela nota média no período; embaixo, o que
        mudou no Top 20 desde ontem."""
        periodo = request.args.get("periodo") or _PERIODO_CONSISTENCIA_PADRAO
        if periodo not in _PERIODOS_CONSISTENCIA:
            periodo = _PERIODO_CONSISTENCIA_PADRAO
        dias = _PERIODOS_CONSISTENCIA[periodo][0]
        consistente = notas_historico.ranking_consistente(dias)
        scan = scan_store.load_last_scan()
        por_nome_scan = {r["name"]: r for r in (scan or {}).get("results") or []}
        com_pagina = _nomes_com_pagina(scan)
        # O que mudou desde ontem (24 h), como antes, numa seção menor.
        snaps = ranking.load_snapshots()
        atual = snaps[-1] if snaps else None
        anterior = _snapshot_de_comparacao(atual)
        # Item que a coleta trouxe sem imagem: completa com a do catálogo
        # (leitura local; antes ficava um quadrado vazio, achado 17/11).
        por_nome_scan = raridade.completar_com_catalogo(por_nome_scan, list({
            it["name"] for fonte in (consistente["itens"], (atual or {}).get("items") or [],
                                     (anterior or {}).get("items") or [])
            for it in fonte if it.get("name")}))
        lista = []
        for pos, it in enumerate(consistente["itens"], start=1):
            atual_scan = por_nome_scan.get(it["name"])
            # Encomenda sugerida, copiável (escolha do usuário, 17/11): a
            # frente da fila. Mudar o valor fica a critério da pessoa.
            lista.append({
                "encomenda": encomenda.sugestao((atual_scan or {}).get("price"),
                                                (atual_scan or {}).get("encomenda")),
                "preco_hoje_fmt": fmt.brl((atual_scan or {}).get("price")),
                "market_url": _MARKET_LISTING_URL.format(
                    name=urllib.parse.quote(it["name"], safe="")),
                **it,
                "position": pos,
                "name_fmt": localize_name(it["name"]),
                "media_int": int(round(it["media"])),
                "nota_hoje": atual_scan.get("score") if atual_scan else None,
                "tem_pagina": it["name"] in com_pagina,
                **_icone_raridade(atual_scan),
            })
        itens_antigos = {it["name"]: it for it in (anterior or {}).get("items") or []}
        itens = []
        if atual:
            for it in atual["items"]:
                delta = ranking.position_delta(it["name"], it["position"], anterior)
                velho = itens_antigos.get(it["name"])
                itens.append({
                    "name": it["name"], "name_fmt": localize_name(it["name"]),
                    "position": it["position"], "score": it["score"],
                    "tem_pagina": it["name"] in com_pagina,
                    "nota_diff": (it.get("score", 0) - velho.get("score", 0)) if velho else None,
                    **delta, **_icone_raridade(por_nome_scan.get(it["name"])),
                })
        movimento = None
        if anterior is not None:
            movimento = {
                "entraram": [it for it in itens if it.get("label") == "NOVO"],
                "saidas": _saidas_do_top(atual, anterior, por_nome_scan, com_pagina),
                "subiram": sorted([it for it in itens if it.get("delta", 0) > 0],
                                  key=lambda it: (-it["delta"], it["position"])),
                "cairam": sorted([it for it in itens if it.get("delta", 0) < 0],
                                 key=lambda it: (it["delta"], it["position"])),
            }
        return render_template(
            "ranking.html",
            lista=lista,
            modo=consistente["modo"],
            coletas=consistente["coletas"],
            desde=fmt.dia_mes_br(consistente["desde"]) if consistente.get("desde") else None,
            dias_minimos=notas_historico.MIN_DIAS_COMPLETOS,
            quando=scan_store.idade_txt(atual["ts"]) if atual else None,
            periodo_sel=periodo,
            periodos=_PERIODOS_CONSISTENCIA,
            movimento=movimento,
            anterior_quando=(fmt.data_hora_br(anterior["ts"])[:5] if anterior else None),
            tamanho_top=len((atual or {}).get("items") or []),
            visiveis_por_bloco=_MOVIMENTO_VISIVEIS,
        )

    @app.route("/admin/login", methods=["GET", "POST"])
    @rate_limit.rate_limited(rate_limit.LOGIN_MAX_HITS, rate_limit.LOGIN_WINDOW_S)
    def admin_login():
        """Login real (usuário único -- é literalmente o dono do site,
        não precisa de conta/"esqueci a senha"). Troca o token fixo em
        URL (vazava em log/referrer) por sessão + senha com hash
        (`werkzeug.security`, PBKDF2/scrypt, zero dependência nova --
        ver `scripts/hash_admin_password.py`). Sem hash configurado,
        a rota nem existe pro visitante: sempre 404, nunca abre
        "sem senha" por padrão."""
        if not _ADMIN_PASSWORD_HASH:
            return render_template("404.html"), 404
        erro = None
        if request.method == "POST":
            senha = request.form.get("senha") or ""
            if check_password_hash(_ADMIN_PASSWORD_HASH, senha):
                session["admin"] = time.time()
                return redirect(url_for("admin"))
            erro = "Senha incorreta."
        return render_template("admin_login.html", erro=erro)

    @app.route("/admin/logout", methods=["POST"])
    @_admin_required
    def admin_logout():
        if not csrf_valid(request.form.get("csrf_token")):
            return "", 403
        session.pop("admin", None)
        return redirect(url_for("index"))

    @app.route("/admin")
    def admin():
        """Painel só pro dono -- ver `admin_login` pra como a sessão é
        criada. Sem hash configurado OU sem sessão válida, a rota
        sempre nega (404), nunca abre "sem senha" por padrão."""
        if not _ADMIN_PASSWORD_HASH:
            return render_template("404.html"), 404
        if not _admin_ativo():
            return redirect(url_for("admin_login"))
        erros = []
        erros_agregados = []
        grafico_erros = ""
        if _ERROR_LOG_PATH.exists():
            linhas = _ERROR_LOG_PATH.read_text(encoding="utf-8",
                                               errors="replace").splitlines()
            erros = linhas[-30:]
            # Mais linhas pra agregação (tipo/dia) que pro tail cru --
            # a tendência importa mais que as últimas 30 exatas aqui.
            linhas_agregacao = linhas[-500:]
            erros_agregados = erro_stats.agregar_por_tipo(linhas_agregacao)
            serie_erros = erro_stats.serie_por_dia(linhas_agregacao)
            # Mesmo padrão de tooltip por ponto (<title> nativo do SVG) já
            # usado em /item, /conta/historico e /status.
            grafico_erros = charts.line_chart_svg(
                [{"total": qtd} for _dia, qtd in serie_erros],
                rotulos=[
                    f"{date.fromisoformat(dia).strftime('%d/%m/%Y')} — {qtd} "
                    f"{'erro' if qtd == 1 else 'erros'}"
                    for dia, qtd in serie_erros])
        _backup_re = re.compile(
            r"^(?:public_site-\d{8}-\d{6}\.db|notas_historico-\d{8}-\d{6}\.sqlite3|json-\d{8}-\d{6}\.zip)$"
        )
        backups = sorted(
            (p for p in db_backup._BACKUP_DIR.iterdir()
             if p.is_file() and _backup_re.match(p.name)),
            key=lambda p: p.stat().st_mtime,
        ) if db_backup._BACKUP_DIR.exists() else []
        progresso = scan_progress.carregar()
        if progresso:
            progresso = dict(progresso, idade=scan_store.idade_txt(progresso["ts"]))
        # Mesmo padrão de `quando` que /status já usa pro histórico de
        # ciclos -- sem isto o admin mostrava `c.ts` cru (epoch em
        # segundos, tipo "1792500195") em vez de "há 20 min" (achado
        # 2026-10-27: os dois templates leem a mesma lista, só o /status
        # formatava).
        ciclos_admin = list(reversed(scan_store.load_historico_ciclos()))[:10]
        for c in ciclos_admin:
            c["quando"] = scan_store.idade_txt(c["ts"])
        visitas_total = visits.total()
        return render_template(
            "admin.html",
            build=_build_id(),
            visitas=visitas_total,
            visitas_fmt=f"{visitas_total:,}".replace(",", "."),
            mais_buscados=buscas.mais_buscados(limite=20),
            erros=erros,
            erros_agregados=erros_agregados,
            grafico_erros=grafico_erros,
            backups=[b.name for b in reversed(backups)],
            ciclos=ciclos_admin,
            progresso=progresso,
            latencias=latencia.resumo(),
            disco=_disco_info(),
            usuarios=_contagem_usuarios(),
            webhook_configurado=bool(
                ambiente("ADMIN_DISCORD_WEBHOOK")),
            teste_webhook_msg=request.args.get("teste_webhook"),
            csrf_token=csrf_token(),
        )

    @app.route("/admin/testar-webhook", methods=["POST"])
    @rate_limit.rate_limited(rate_limit.LOGIN_MAX_HITS, rate_limit.LOGIN_WINDOW_S)
    @_admin_required
    def admin_testar_webhook():
        # CSRF checado aqui dentro (não via @csrf_protect) de propósito:
        # @_admin_required já roda antes do corpo da view (mais perto
        # de `def`, executa por último entre os decorators, logo antes
        # da função); um @csrf_protect precisaria ficar ENTRE
        # @_admin_required e `def` pra manter essa ordem, e inline é
        # mais simples que empilhar mais um decorator só pra isso. Sem
        # essa ordem, uma visita anônima sem csrf_token nenhum na sessão
        # levaria 403 em vez de 404 -- vazando que a rota existe pra
        # quem não é admin.
        if not csrf_valid(request.form.get("csrf_token")):
            return "", 403
        webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
        enviado = discord_notify.enviar(
            webhook, "🔧 Lodout: alerta de teste do painel admin. Se você "
            "está lendo isto, os alertas do site chegam neste canal.")
        flash_msg = ("Alerta de teste enviado — confira o canal no Discord."
                     if enviado else
                     "Não chegou: o Discord recusou ou o webhook está "
                     "incompleto. Confira se o secret ADMIN_DISCORD_WEBHOOK "
                     "tem a URL inteira do webhook e faça um novo deploy.")
        return redirect(url_for("admin", teste_webhook=flash_msg,
                                _anchor="alertas"))

    @app.route("/admin/backup/<nome>")
    @_admin_required
    def admin_backup_download(nome: str):
        """Download de um backup gerado por `db_backup.py` -- valida `nome`
        contra os formatos EXATOS (whitelist por regex, não só confiar no
        `send_from_directory` resolver o path)."""
        if not re.fullmatch(
            r"(?:public_site-\d{8}-\d{6}\.db|notas_historico-\d{8}-\d{6}\.sqlite3|json-\d{8}-\d{6}\.zip)",
            nome,
        ):
            return render_template("404.html"), 404
        caminho = db_backup._BACKUP_DIR / nome
        if not caminho.is_file():
            return render_template("404.html"), 404
        return send_from_directory(
            db_backup._BACKUP_DIR, nome,
            as_attachment=True, mimetype="application/octet-stream")

    @app.route("/admin/log-bruto")
    @_admin_required
    def admin_log_bruto():
        """Download do errors.log completo -- as 30 últimas linhas no
        painel bastam pro dia a dia, mas investigar um padrão (quantas
        vezes um erro específico apareceu ao longo de dias) pede o
        arquivo inteiro."""
        if not _ERROR_LOG_PATH.exists():
            return render_template("404.html"), 404
        return send_from_directory(
            _ERROR_LOG_PATH.parent, _ERROR_LOG_PATH.name,
            as_attachment=True, mimetype="text/plain")

    @app.route("/api")
    def api_docs():
        return render_template(
            "api_docs.html",
            exemplo_url=f"{request.url_root}api/recommendations")

    @app.route("/status")
    def status():
        ciclos = list(reversed(scan_store.load_historico_ciclos()))
        for c in ciclos:
            c["quando"] = scan_store.idade_txt(c["ts"])
        desde = uptime.no_ar_desde()
        # Últimos 30 dias: com mais que isso as barras ficam finas demais.
        serie = visits.serie_por_dia()[-30:]
        valores_visitas = [qtd for _dia, qtd in serie]
        # Mesmo padrão de tooltip por ponto (<title> nativo do SVG) já
        # usado no gráfico de preço de /item/<name> e no de /conta/historico
        # -- sem área/tendência aqui (visita subir ou cair não é "bom" nem
        # "ruim" como preço, então fica sem a cor verde/vermelha).
        rotulos_visitas = [
            f"{date.fromisoformat(dia).strftime('%d/%m/%Y')} — {qtd} "
            f"{'visita' if qtd == 1 else 'visitas'}"
            for dia, qtd in serie]
        # Barras com o dia embaixo e o número em cima (revisão 20/11): a
        # linha solta, sem datas nem valores, não dizia nada.
        grafico_visitas = charts.bar_chart_svg(
            valores_visitas,
            [date.fromisoformat(dia).strftime("%d/%m") for dia, _q in serie],
            rotulos_visitas)
        grafico_visitas_legenda = (
            f"De {min(valores_visitas)} a {max(valores_visitas)} visitas por dia "
            f"nos últimos {len(valores_visitas)} dias."
            if len(valores_visitas) >= 2 else None)
        ciclos_ok = sum(1 for c in ciclos if c.get("sucesso"))
        ciclos_completos = sum(
            1 for c in ciclos
            if scan_store.ciclo_completo(c)
            and scan_store.ciclo_sem_pausa(c))
        resumo_top = scan_store.resumo_rodadas_top()
        rodada_top = scan_store.load_rodada_top()
        if rodada_top:
            rodada_top = dict(rodada_top,
                              quando=scan_store.idade_txt(rodada_top["ts"]))
        visitas_total = visits.total()
        return render_template(
            "status.html",
            rodada_top=rodada_top,
            estado_scan=_estado_do_scan(
                scan_progress.carregar(), ciclos,
                float(ambiente("WORKER_INTERVAL_HORAS",
                               _INTERVALO_HORAS_DEFAULT))),
            no_ar_desde_txt=scan_store.idade_txt(desde),
            visitas=visitas_total,
            visitas_fmt=f"{visitas_total:,}".replace(",", "."),
            ciclos=ciclos,
            ciclos_sucesso_txt=(
                f"{ciclos_ok} de {len(ciclos)} coletas com sucesso"
                if ciclos else None),
            ciclos_completos_txt=(
                f"Dessas, {ciclos_completos} "
                f"{'terminou' if ciclos_completos == 1 else 'terminaram'} "
                "com todos os itens e sem pausa da Steam."
                if ciclos else None),
            top20_falhas_recentes=resumo_top["falhas"],
            top20_total_recentes=resumo_top["total"],
            grafico_visitas=grafico_visitas,
            grafico_visitas_legenda=grafico_visitas_legenda,
            catalogo_estado=_estado_do_catalogo(),
        )

    @app.route("/feed.xml")
    @rate_limit.rate_limited(rate_limit.API_MAX_HITS, rate_limit.API_WINDOW_S)
    def feed():
        categoria = request.args.get("categoria") or None
        if categoria and categoria not in scan_targets.SCAN_BY_CATEGORY:
            categoria = None
        scan = scan_store.load_last_scan()
        # O RSS não exibe tendência nem sparkline -- ler o histórico dos
        # ~150 candidatos custava ~3s por request (medido 2026-10-29).
        candidatos = _candidatos_filtrados(
            scan, categoria, com_historico=False,
            com_icone=False, formatar=False)[:_LIMIT_CANDIDATOS]
        _enriquecer_formatacao(candidatos)
        base = request.url_root.rstrip("/")
        itens_xml = "\n".join(
            "    <item>\n"
            f"      <title>{_xml_escape(c['name_fmt'])} — nota {c['score']}</title>\n"
            # Pra página do item no próprio site, não pra listagem da
            # Steam -- achado 2026-11-01: quem clicava a partir do feed
            # pulava direto pra Steam, sem ver a nota/motivo que é o
            # diferencial do feed.
            f"      <link>{_xml_escape(base + url_for('item_detail', name=c['name']))}</link>\n"
            f"      <guid isPermaLink=\"false\">{_xml_escape(c['name'])}</guid>\n"
            "      <description>"
            f"{_xml_escape(c['price_fmt'])} — "
            f"{_xml_escape('; '.join(c['reasons']) if c['reasons'] else 'Nota neutra')}"
            "</description>\n"
            "    </item>"
            for c in candidatos
        )
        titulo = (f"Lodout — Preços e notas de {_xml_escape(categoria)}"
                  if categoria else "Lodout — análise do mercado de skins de Counter-Strike 2")
        link_self = f"{base}/feed.xml" + (
            f"?categoria={urllib.parse.quote(categoria)}" if categoria else "")
        rss = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<rss version="2.0"><channel>\n'
            f"  <title>{titulo}</title>\n"
            f"  <link>{_xml_escape(link_self)}</link>\n"
            "  <description>Análise do mercado de skins de Counter-Strike 2, com notas"
            " e o motivo de cada uma.</description>\n"
            "  <language>pt-BR</language>\n"
            f"{itens_xml}\n"
            "</channel></rss>\n"
        )
        return Response(rss, mimetype="application/rss+xml",
                        headers={"Cache-Control": "public, max-age=300"})

    return app


def _contagem_por_categoria(scan: "dict | None") -> dict:
    """{categoria: quantidade} a partir do scan cru -- alimenta os rótulos
    do dropdown de filtro ("Facas (12)"). Conta `scan["results"]` direto
    (não `buy_candidates`), então é uma aproximação -- itens filtrados por
    pump_risk no dropdown continuam contados aqui. Suficiente pra dar
    noção de tamanho, não precisa ser exato."""
    if not scan:
        return {}
    contagem: dict = {}
    for r in scan["results"]:
        cat = r.get("category")
        if cat:
            contagem[cat] = contagem.get(cat, 0) + 1
    return contagem


_texto_busca = catalogo.texto_busca


def _compilar_busca(busca: "str | None") -> "tuple[tuple[str, ...], ...] | None":
    """Normaliza a consulta de busca uma vez só (em vez de repetir por item).
    Devolve `None` quando a consulta está vazia (qualquer item casa)."""
    if not busca:
        return None
    limpo = " ".join(_texto_busca(busca).split())
    grupos = [g for g in limpo.split(" or ") if g.strip()]
    if not grupos:
        return None
    return tuple(
        tuple(p for p in grupo.split() if any(ch.isalnum() for ch in p))
        for grupo in grupos
    )


def _busca_bate_compilada(
        alvo_norm: str,
        grupos: "tuple[tuple[str, ...], ...] | None") -> bool:
    if grupos is None:
        return True
    for palavras in grupos:
        if palavras and all(p in alvo_norm for p in palavras):
            return True
    return False


def _busca_bate(nome: str, busca: "str | None") -> bool:
    """A busca funciona como a do Mercado da Steam, que é de onde vem quem
    usa o site (2026-11-14): `nome` traz o nome em português E o original
    em inglês ("Testada em Campo" e "Field-Tested"), sem diferença de
    acento ou hífen, e cada palavra digitada pode estar em qualquer
    ordem ("redline ak" acha "AK-47 | Redline").

    "termo1 OR termo2" continua valendo (qualquer um dos dois basta)."""
    grupos = _compilar_busca(busca)
    if grupos is None:
        return True
    return _busca_bate_compilada(_texto_busca(nome), grupos)


_nome_para_busca = catalogo.nome_para_busca


def _tendencia_do_historico(hist: list) -> "str | None":
    if len(hist) < 2:
        return None
    anterior, atual = hist[-2]["price"], hist[-1]["price"]
    if not anterior or atual == anterior:
        return None
    pct = (atual - anterior) / anterior * 100
    if round(abs(pct), 1) < 0.1:
        return None
    if atual > anterior:
        return "alta"
    if atual < anterior:
        return "baixa"
    return None


def _variacao_pct_do_historico(hist: list) -> "float | None":
    """Variação % entre os 2 últimos preços registrados -- o mesmo par que
    `_tendencia_do_historico` compara. Só "Subiu"/"Caiu" não dizia quanto:
    uma oscilação de centavos e uma de 30% apareciam iguais na tabela."""
    if len(hist) < 2:
        return None
    anterior, atual = hist[-2]["price"], hist[-1]["price"]
    if not anterior or atual == anterior:
        return None
    pct = (atual - anterior) / anterior * 100
    if round(abs(pct), 1) < 0.1:
        return None
    return pct


_PONTOS_NO_FIM_RE = re.compile(r"\s*\(([+-]\d+(?:\.\d+)?)\)\s*$")


def _motivo_fmt(texto: "str | None") -> str:
    """"Preço 22% abaixo do típico (+26)" -> "... · +26 pts". O número
    entre parênteses é a contribuição do fator pra nota, mas solto assim
    lia como outra porcentagem. Só reformata a exibição; o rótulo
    original continua vindo de `signals` (compartilhado com o app).

    Casa decimal opcional no número -- `signals.enhanced_score` usa uma
    casa (em vez de arredondar pra "0") quando a contribuição de um
    fator é pequena o bastante pra virar "(+0)"/"(-0)" no inteiro, que
    lia como contradição (0 pontos, mas pintado de verde/vermelho).

    Espaços fixos (\\u00a0) entre "·", o número e "pts" -- achado
    2026-10-30: com espaço normal, a quebra de linha na coluna "Por
    quê" às vezes deixava só "pts" sozinho numa linha. Desde 2026-11-14
    o espaço ANTES do "·" também é fixo: com ele normal, a quebra caía
    ali e a linha de baixo começava com "· +20 pts" solto. Agora a
    última palavra do motivo desce junto ("comprar · +20 pts")."""
    if not texto:
        return ""
    return _PONTOS_NO_FIM_RE.sub(" · \\1 pts", texto)


def _tamanho_fmt(bytes_: int) -> str:
    """"1.2 MB"/"340 KB" -- só pro painel admin, não precisa de precisão."""
    valor = float(bytes_)
    for unidade in ("B", "KB", "MB", "GB"):
        if valor < 1024 or unidade == "GB":
            return f"{valor:.1f} {unidade}" if unidade != "B" else f"{int(valor)} B"
        valor /= 1024
    return f"{valor:.1f} GB"


def _disco_info() -> dict:
    """Espaço em disco da partição de `DATA_DIR` + tamanho dos arquivos
    de registro -- pensado pra avisar ANTES de faltar espaço pros
    backups, não depois (achado: numa VM pequena, 1-2GB livres somem
    rápido com `ssr_cache`/backups acumulando)."""
    try:
        uso = shutil.disk_usage(DATA_DIR)
        livre_pct = round(100 * uso.free / uso.total, 1) if uso.total else 0.0
    except OSError:
        uso = None
        livre_pct = None
    db_tamanho = (db_backup._DB_PATH.stat().st_size
                 if db_backup._DB_PATH.exists() else 0)
    backups_tamanho = sum(
        p.stat().st_size for p in db_backup._BACKUP_DIR.glob("*") if p.is_file()
    ) if db_backup._BACKUP_DIR.exists() else 0
    catalogo_path = catalogo._caminho_banco()
    catalogo_tamanho = catalogo_path.stat().st_size if catalogo_path.exists() else 0
    notas_path = notas_historico._caminho()
    notas_tamanho = notas_path.stat().st_size if notas_path.exists() else 0
    icones_tamanho = sum(
        p.stat().st_size for p in icon_cache._CACHE_DIR.glob("*") if p.is_file()
    ) if icon_cache._CACHE_DIR.exists() else 0
    return {
        "livre_fmt": _tamanho_fmt(uso.free) if uso else "—",
        "total_fmt": _tamanho_fmt(uso.total) if uso else "—",
        "livre_pct": livre_pct,
        "db_fmt": _tamanho_fmt(db_tamanho),
        "backups_fmt": _tamanho_fmt(backups_tamanho),
        "catalogo_fmt": _tamanho_fmt(catalogo_tamanho),
        "notas_fmt": _tamanho_fmt(notas_tamanho),
        "icones_fmt": _tamanho_fmt(icones_tamanho),
    }


def _contagem_usuarios() -> int:
    """Quantas contas Steam já logaram ao menos uma vez -- 0 se o banco
    ainda não existe (site sem nenhum login ainda)."""
    if not db_backup._DB_PATH.exists():
        return 0
    conn = None
    try:
        conn = sqlite3.connect(str(db_backup._DB_PATH), timeout=3.0)
        conn.execute("PRAGMA busy_timeout=3000")
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return int(n)
    except sqlite3.Error:
        return 0
    finally:
        if conn is not None:
            conn.close()


_RISCO_LABELS = {"low": "Baixo", "medium": "Médio", "high": "Alto"}

# `signals.liquidity_depth()` já calcula isto em todo scan (dias de
# listagens no ritmo atual) mas não aparecia em lugar nenhum da UI até
# 2026-11-02 -- achado numa pesquisa de como outros sites de skin
# expõem liquidez. Rótulo só pra exibição; a lógica/faixas já vêm
# prontas de `signals.py`.
_LIQUIDEZ_LABELS = {
    "muito_liquido": "Muito líquida",
    "liquido": "Líquida",
    "moderado": "Moderada",
    "fino": "Baixa liquidez",
    "iliquido": "Ilíquida",
}


def _liquidez_label(band: "str | None") -> str:
    return _LIQUIDEZ_LABELS.get(band or "", "")


_PONTOS_NO_FIM = re.compile(r"\s*\([+\-\u2212]?\d+(?:[.,]\d+)?\)\s*$")


def _pontos_fmt(delta) -> str:
    """Etiqueta de pontos do "Por quê": "+20", "−15" (sinal de menos de
    verdade) ou "0" -- fatores fracionários (-0.3) arredondam."""
    try:
        n = round(float(delta or 0))
    except (TypeError, ValueError):
        n = 0
    return f"+{n}" if n > 0 else (f"\u2212{-n}" if n < 0 else "0")


def _motivo_sem_pontos(label: "str | None") -> str:
    """"Mais gente querendo comprar (+20)" -> "Mais gente querendo
    comprar": no "Por quê" os pontos vão numa etiqueta própria."""
    return _PONTOS_NO_FIM.sub("", label or "")


_STATUS_PT = {
    "discontinued": "Descontinuada",
    "rare": "Rara",
    "active": "Ativa",
    "collection": "Coleção",
}


def _rotulo_caixa(case_label: "str | None",
                  item_name: "str | None" = None) -> str:
    """Traduz o nome da caixa em "X Case (descontinuada, 2014)" com o mesmo
    `localize_name` da coluna Item -- sem isso a linha mostrava "Caixa
    CS:GO Weapon" no nome e "CS:GO Weapon Case" ao lado.

    Com `item_name` igual à própria caixa/cápsula, devolve só o status
    ("Descontinuada · 2024"): repetir o nome que já está na
    coluna Item ocupava a célula sem dizer nada novo."""
    if not case_label:
        return ""
    nome, sep, resto = case_label.partition(" (")
    if item_name and nome == item_name and resto:
        status, _, ano = resto.rstrip(")").partition(", ")
        status_limpo = status.strip().lower()
        texto = _STATUS_PT.get(status_limpo, status[:1].upper() + status[1:])
        return f"{texto} · {ano}" if ano else texto
    return localize_name(nome) + sep + resto


def _rotulo_caixa_curto(case_label: "str | None",
                        item_name: "str | None" = None) -> str:
    """Versão concisa de `_rotulo_caixa` para cartões da vitrine onde o espaço
    é compacto. Remove prefixos óbvios como "Caixa de Armas do ", "Caixa ", etc.,
    mostrando apenas o nome distintivo e o ano (ex: "Bravo · 2013", "Prisma",
    "Sonhos e Pesadelos"). O atributo title no HTML mantém o nome completo."""
    rotulo = _rotulo_caixa(case_label, item_name)
    if not rotulo:
        return ""
    nome, sep, resto = rotulo.partition(" (")
    curto = re.sub(
        r"^(Caixa de Armas da Operação|Caixa da Operação|Caixa Operação|Caixa de Armas do|Caixa de Armas|Caixa de|Caixa|Cápsula de Autógrafos de|Cápsula de Autógrafo de|Cápsula de|Coleção da Operação|Coleção de|Coleção|The)\s+",
        "",
        nome,
        flags=re.I,
    )
    curto = re.sub(r"^(Operação da|Operação de|Operação|Operation)\s+", "", curto, flags=re.I)
    curto = re.sub(r"\s+(Case|Collection)$", "", curto, flags=re.I).strip()
    if resto:
        status, _, ano = resto.rstrip(")").partition(", ")
        status_limpo = status.strip().lower()
        texto_status = _STATUS_PT.get(status_limpo, "")
        if ano:
            return f"{curto} · {ano}"
        return f"{curto} · {texto_status}" if texto_status else curto
    return curto


# Maior palavra real conhecida logo após o "|" num nome de item (ex.
# "Asiimov", "Redline", "Doppler") fica bem abaixo disto -- serve só de
# limite de segurança (ver docstring de `_titulo_sem_pipe_orfao`).
_PIPE_COLADO_MAX = 20


def _titulo_sem_pipe_orfao(nome_fmt: "str | None") -> Markup:
    """Cola o "|" na palavra seguinte -- só pros títulos grandes (hero
    da home, h1 da página do item). Sem isso, o nome quebra de linha
    logo depois do separador "|" (ex. "Five-SeveN |" numa linha,
    "Monkey Business" na outra): a barra sozinha no fim da linha lê
    mal. Espaço duro (\xa0) sozinho NÃO resolve -- testado ao vivo: o
    motor de layout ainda abre uma quebra bem ali, com ou sem
    text-wrap:balance/overflow-wrap:anywhere na regra. Só um <span>
    com white-space:nowrap (.pipe-colado no CSS) prende os dois de
    verdade -- mas `white-space:nowrap` NÃO tem fallback de overflow
    (testado: nem `overflow-wrap:break-word` o destrava), então um
    nome fora do padrão (sem espaço nenhum ali) vazaria da caixa.
    `_PIPE_COLADO_MAX` existe só por isso: fora do comum, cai pro texto
    normal (ainda quebra mal, mas não estoura layout). Escopado nesta
    função, não em `localize_name`, de propósito -- name_fmt alimenta a
    API JSON e o texto que "Copiar nome" cola na área de transferência;
    HTML ali mudaria o contrato dos dois sem necessidade."""
    if not nome_fmt:
        return Markup("")
    antes, sep, depois = nome_fmt.partition("| ")
    if not sep:
        return Markup.escape(nome_fmt)
    palavra, _, resto = depois.partition(" ")
    if len(palavra) > _PIPE_COLADO_MAX:
        return Markup.escape(nome_fmt)
    pedaco = Markup('<span class="pipe-colado">|\xa0{}</span>').format(palavra)
    return Markup("{}{}{}{}").format(antes, pedaco, " " if resto else "", resto)


_MESES_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
             "agosto", "setembro", "outubro", "novembro", "dezembro")


def _data_extenso(iso: str) -> str:
    """"2026-11-20" -> "20 de novembro de 2026" (texto da página Mudanças).
    Data inválida volta como veio, em vez de quebrar a página."""
    try:
        d = date.fromisoformat(str(iso))
    except ValueError:
        return str(iso)
    return f"{d.day} de {_MESES_PT[d.month - 1]} de {d.year}"


def _nota_classe(score: "int | float | None") -> str:
    """"alta"/"media"/"baixa" -- mesma faixa repetida em 4 templates
    (index/item/comparar/ranking) até 2026-10-26; centralizado aqui como
    filtro Jinja pra não divergir se a faixa mudar um dia."""
    score = score or 0
    if score >= 70:
        return "alta"
    if score >= 45:
        return "media"
    return "baixa"


# Raridade (cor da borda no ícone) fatorada em raridade.py 2026-11-07,
# pra watchlist/trades reusarem sem importar o módulo inteiro de rotas
# -- watchlist_routes.py e trades_routes.py cruzam pelo nome com o scan
# atual do mesmo jeito que ranking_page() já fazia.
_raridade_classe = raridade.raridade_classe
_raridade_titulo = raridade.raridade_titulo
_icone_raridade = raridade.icone_raridade


# Anel de progresso da nota (0-100) em SVG, gerado no servidor (mesmo
# padrão do sparkline) -- `stroke-dasharray` é atributo de apresentação do
# SVG, não `style=""`, então passa no CSP `style-src 'self'` sem problema.
_NOTA_ANEL_RAIO = 16


def _nota_anel(score) -> str:
    s = max(0, min(100, round(score or 0)))
    circ = 2 * math.pi * _NOTA_ANEL_RAIO
    dash = circ * s / 100
    return (
        f'<svg class="nota-anel" viewBox="0 0 40 40" aria-hidden="true" '
        f'focusable="false">'
        f'<circle class="nota-anel-fundo" cx="20" cy="20" r="{_NOTA_ANEL_RAIO}">'
        f'</circle>'
        f'<circle class="nota-anel-progresso" cx="20" cy="20" r="{_NOTA_ANEL_RAIO}" '
        f'stroke-dasharray="{dash:.2f} {circ:.2f}"></circle></svg>'
    )


def _risco_nivel(pump_risk: "dict | None") -> str:
    return (pump_risk or {}).get("level", "low")


def _risco_label(pump_risk: "dict | None") -> str:
    return _RISCO_LABELS[_risco_nivel(pump_risk)]


def _tempo_desde_aposentadoria(data_iso: "str | None") -> "str | None":
    """"2.3 anos"/"40 dias" desde a aposentadoria registrada (ver
    `lodout/retirements.py` -- é o mesmo dado que já alimenta o
    score, só formatado pra leitura humana). None sem data registrada
    -- a maioria das caixas descontinuadas antigas não tem; o registro
    só começou em 2026-10-17."""
    if not data_iso:
        return None
    try:
        dia = date.fromisoformat(data_iso)
    except ValueError:
        return None
    dias = (date.today() - dia).days
    if dias < 0:
        return None
    anos = dias / 365.25
    return f"{anos:.1f} anos" if anos >= 1 else f"{dias} dia{'s' if dias != 1 else ''}"


# Quantos itens aparecem nos cards de "maiores mudanças de nota" (home).
_MOVIMENTOS_DESTAQUE = 3


# /ranking = os melhores de forma consistente (pedido 17/11): nota média no
# período (notas_historico.ranking_consistente). chave -> (dias, rótulo).
_PERIODOS_CONSISTENCIA = {
    "7d": (7, "7 dias"),
    "30d": (30, "30 dias"),
    "90d": (90, "90 dias"),
    "365d": (365, "1 ano"),
}
_PERIODO_CONSISTENCIA_PADRAO = "7d"
# Folga pra um ciclo que terminou um pouco mais cedo ainda contar como
# "de 24h atrás" (é a mesma régua de 20h que `_resumo_do_dia` já usava).
_FOLGA_PERIODO_H = 4


def _snapshot_de_comparacao(atual: "dict | None") -> "dict | None":
    """Snapshot de ~24h atrás, contra o qual o /ranking e o resumo da home
    comparam. None quando ainda não existe um velho o suficiente -- a tela
    diz isso em vez de comparar com um mais recente e chamar de "24h"."""
    if not atual:
        return None
    alvo = atual["ts"] - (24 - _FOLGA_PERIODO_H) * 3600
    antigo = ranking.latest_before(alvo)
    if antigo is None:
        # Mais velho que o rankings.json guarda: a foto do dia no histórico
        # da nota, cortada no Top 20 (a base de comparação de sempre).
        antigo = notas_historico.snapshot_ate(alvo)
        if antigo:
            antigo = {"ts": antigo["ts"], "items": [
                it for it in antigo["items"] if (it.get("position") or 99) <= 20]}
    return antigo


def _resumo_do_dia(atual: "dict | None") -> "dict | None":
    """Resumo factual do Top 20 comparado com o snapshot de ~1 dia atrás
    (nunca previsão). None sem
    snapshot velho o suficiente (site novo ou só 1 scan até agora)."""
    if not atual:
        return None
    return _resumo_entre(atual, _snapshot_de_comparacao(atual))


def _resumo_entre(atual: "dict | None",
                  antigo: "dict | None") -> "dict | None":
    """Resumo factual (nunca previsão) do Top 20 `atual` contra `antigo`."""
    if not atual or not antigo:
        return None
    itens_antigos = {it["name"]: it for it in antigo.get("items", [])}
    novos = [it for it in atual["items"] if it["name"] not in itens_antigos]
    maior_alta = None
    maior_queda = None
    # `movimentos` alimenta os mini-cards da home (item #19 da lista de
    # melhorias): os maiores vaivens de nota, pra alta E pra baixa, sem
    # escolher "vencedor". Fica só com o que realmente mudou -- item que
    # repetiu a mesma nota não é notícia e só gastaria card.
    movimentos = []
    for it in atual["items"]:
        velho = itens_antigos.get(it["name"])
        if not velho:
            continue
        diff = it.get("score", 0) - velho.get("score", 0)
        if diff:
            movimentos.append({
                "name": it["name"],
                "name_fmt": localize_name(it["name"]),
                "diff": diff,
                "de": velho.get("score"),
                "para": it.get("score"),
            })
        if diff > 0 and (maior_alta is None or diff > maior_alta["diff"]):
            maior_alta = {
                "name_fmt": localize_name(it["name"]),
                "diff": diff,
                "de": velho.get("score"),
                "para": it.get("score"),
            }
        if diff < 0 and (maior_queda is None or diff < maior_queda["diff"]):
            maior_queda = {
                "name_fmt": localize_name(it["name"]),
                "diff": diff,
                "de": velho.get("score"),
                "para": it.get("score"),
            }
    # Maior mudança primeiro (em módulo); empate resolvido pelo nome só
    # pra ordem ser estável entre renders com os mesmos dados.
    movimentos.sort(key=lambda m: (-abs(m["diff"]), m["name"]))
    return {
        "novos_no_top": len(novos),
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
        "movimentos": movimentos[:_MOVIMENTOS_DESTAQUE],
        "quando": scan_store.idade_txt(antigo["ts"]),
        "desde": _desde_txt(antigo["ts"]),
        "dia_ref": _desde_txt(antigo["ts"]).removeprefix("desde "),
    }


def _desde_txt(ts: float) -> str:
    """ "desde ontem" para o ranking de ~1 dia atrás; senão a data
    (revisão 17/11: "desde o ranking salvo há 1 dia" era jargão)."""
    idade = time.time() - float(ts)
    if 0 <= idade < 48 * 3600 and fmt.dia_mes_br(ts) == fmt.dia_mes_br(time.time() - 86400):
        return "desde ontem"
    return "desde " + fmt.dia_mes_br(ts)


_logger = logging.getLogger("lodout.site")

# Eventos detectados nos arquivos do jogo (gamedata.py, gravados pelo
# worker) em português de quem está começando: o que mudou + o que isso
# quer dizer na prática. Descreve o fato, não prevê preço.
_EVENTOS_JOGO = {
    "drop_pool_added": (
        "entrou no drop semanal",
        "Jogadores voltam a receber itens desta coleção nos drops "
        "semanais, então novas unidades entram no jogo por esse caminho."),
    "drop_pool_removed": (
        "saiu do drop semanal",
        "A coleção deixou de cair nos drops semanais: novas unidades "
        "param de entrar no jogo por esse caminho."),
    "xpshop_added": (
        "entrou no Armory",
        "Passou a poder ser resgatado no Armory, a loja de recompensas "
        "do passe."),
    "xpshop_removed": (
        "saiu do Armory",
        "Deixou de poder ser resgatado no Armory. Quando é uma caixa, "
        "o lodout passa a tratá-la como aposentada nesta data."),
    "new_container": (
        "apareceu nos arquivos do jogo",
        "Caixa nova nos arquivos do jogo. Pode ainda não estar à venda "
        "no Market."),
}
_EVENTOS_JOGO_MAX = 30


def _data_do_evento(ev: dict) -> "float | None":
    """Data do commit dos arquivos (quando a Valve mudou), com a data da
    detecção como reserva."""
    bruto = ev.get("commit_date")
    if isinstance(bruto, str) and bruto:
        try:
            return datetime.fromisoformat(bruto.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    ts = ev.get("ts")
    return float(ts) if isinstance(ts, (int, float)) else None


def _eventos_do_jogo(nomes_no_site: "set[str]",
                     so_do_item: "str | None" = None) -> "list[dict]":
    """Eventos de `gamedata.load_events_log()` prontos pro template, do
    mais novo pro mais antigo. Só vira link o nome que o site acompanha."""
    try:
        brutos = gamedata.load_events_log()
    except Exception:
        _logger.warning("log de eventos do jogo ilegível", exc_info=True)
        return []
    out = []
    for ev in brutos:
        if not isinstance(ev, dict) or ev.get("type") not in _EVENTOS_JOGO:
            continue
        nome = str(ev.get("name") or "")
        if not nome or (so_do_item is not None and nome != so_do_item):
            continue
        ts = _data_do_evento(ev)
        verbo, explicacao = _EVENTOS_JOGO[ev["type"]]
        out.append({
            "nome": nome,
            "nome_fmt": localize_name(nome),
            "verbo": verbo,
            "explicacao": explicacao,
            "ts": ts or 0.0,
            "data": (datetime.fromtimestamp(ts, tz=fmt.FUSO_BR).strftime("%d/%m/%Y")
                     if ts else None),
            "no_site": nome in nomes_no_site,
        })
    out.sort(key=lambda e: -e["ts"])
    return out[:_EVENTOS_JOGO_MAX]


def _noticias_oficiais() -> "list[dict]":
    try:
        itens = steam_news.carregar_noticias()
    except Exception:
        _logger.warning("cache de notícias ilegível", exc_info=True)
        return []
    out = []
    for n in itens:
        if not isinstance(n, dict) or not n.get("titulo"):
            continue
        ts = n.get("ts")
        out.append({
            "titulo": n["titulo"],
            "resumo": n.get("resumo") or "",
            "url": n.get("url"),
            "data": (datetime.fromtimestamp(ts, tz=fmt.FUSO_BR).strftime("%d/%m/%Y")
                     if isinstance(ts, (int, float)) else None),
        })
    return out


# Progresso gravado há mais que isto não é "agora": o worker grava a cada
# item (~9 s), então 3 min sem atualizar = ciclo parado ou já terminou.
_PROGRESSO_VIVO_S = 180


def _estado_do_scan(progresso: "dict | None", ciclos: "list[dict]",
                    intervalo_horas: float,
                    now: "float | None" = None) -> dict:
    """O que o /status diz do scan agora: em andamento (item N de M, com
    previsão pelo ritmo do último ciclo) ou a próxima rodada prevista.
    `ciclos` vem do mais novo pro mais antigo (como em /status)."""
    agora = time.time() if now is None else now
    if (progresso and agora - float(progresso.get("ts") or 0) <= _PROGRESSO_VIVO_S
            and int(progresso.get("indice") or 0) < int(progresso.get("total") or 0)):
        indice, total = int(progresso["indice"]), int(progresso["total"])
        faltam_txt = None
        ultimo = next((c for c in ciclos if c.get("sucesso")
                       and c.get("itens")), None)
        if ultimo and ultimo.get("duracao_min"):
            por_item_s = float(ultimo["duracao_min"]) * 60 / max(
                1, int(ultimo.get("alvos") or ultimo["itens"]))
            faltam_min = max(1, round((total - indice) * por_item_s / 60))
            faltam_txt = f"~{faltam_min} min"
        return {"rodando": True, "indice": indice, "total": total,
                "item_fmt": localize_name(str(progresso.get("item") or "")),
                "faltam_txt": faltam_txt}
    if not ciclos:
        return {"rodando": False, "proximo_txt": None}
    return {"rodando": False,
            "proximo_txt": scan_store.proxima_txt(
                ciclos[0]["ts"], intervalo_horas, now=agora)}


def _nomes_com_pagina(scan: "dict | None") -> "set[str]":
    """Nomes que têm página em /item/<nome> -- a mesma lista filtrada
    que `item_detail` usa."""
    if not scan:
        return set()
    return {c["name"] for c in _candidatos_filtrados(
        scan, com_historico=False, com_icone=False, formatar=False)}


def _saidas_do_top(atual: "dict | None", anterior: "dict | None",
                   por_nome_scan: dict,
                   com_pagina: "set[str]") -> "list[dict]":
    """Quem estava no Top 20 de `anterior` e não está no `atual`, na
    ordem da posição antiga -- a outra metade do selo NOVO."""
    if not atual or not anterior:
        return []
    nomes_atuais = {it["name"] for it in atual.get("items", [])}
    out = []
    for it in sorted(anterior.get("items", []),
                     key=lambda i: i.get("position") or 0):
        if it["name"] in nomes_atuais:
            continue
        agora = por_nome_scan.get(it["name"])
        out.append({
            "name": it["name"],
            "name_fmt": localize_name(it["name"]),
            "prev_pos": it.get("position"),
            "prev_score": it.get("score"),
            "score": agora.get("score") if agora else None,
            "tem_pagina": it["name"] in com_pagina,
            **_icone_raridade(agora),
        })
    return out


# "O que mudou desde ontem": quantas linhas cada bloco mostra antes do
# "ver mais" (17/11: com 17 entradas num dia, o bloco ficava 3x mais alto
# que os vizinhos e empurrava "Saíram" para longe).
_MOVIMENTO_VISIVEIS = 5


_HISTORICO_CURTO_LIMIAR = 5


def _sparkline_do_historico(hist: list) -> str:
    pontos = [{"total": p["price"]} for p in hist[-20:] if p.get("price")]
    return charts.line_chart_svg(
        pontos, width=120, height=28, padding=2, css_class="mini-sparkline")


def _enriquecer_com_icone(candidatos: list[dict]) -> None:
    """Preenche `icon_url`/`icon_url_2x` -- feito à parte de
    `_candidatos_filtrados` (mesma ideia de `_enriquecer_com_historico`,
    acima) de propósito: cada `url_for` aqui builda uma URL via o
    roteador do Flask, caro à toa pros ~150-180 candidatos quando só
    uma fatia pequena é exibida de verdade. Profiling 2026-11-09: 42%
    do tempo de `/` inteiro vinha dessas duas chamadas rodando pra
    TODOS os candidatos, mesmo só 10 aparecendo na página -- mesmo
    desperdício que `_enriquecer_com_historico` já corrigiu pro
    histórico em 2026-10-26, nunca estendido ao ícone. Só chamar com a
    fatia que vai renderizar de verdade."""
    for c in candidatos:
        c["icon_url"] = (
            url_for("icone_cache", hash_icone=c["icon"], v=3)
            if c.get("icon") else None)
        c["icon_url_2x"] = (
            url_for("icone_cache", hash_icone=c["icon"], v=3, tam=384)
            if c.get("icon") else None)


def _enriquecer_com_historico(candidatos: list[dict]) -> None:
    """Preenche `tendencia`/`sparkline` -- feito à parte de
    `_candidatos_filtrados` (acima) de propósito: ler o histórico de
    TODOS os candidatos (até ~150) quando só 10 aparecem na página é
    caro à toa (2 leituras de disco por item, uma pra cada campo, antes
    desta função existir). Só chamar com a fatia que vai renderizar de
    verdade (a página atual, ou o grupo aberto)."""
    for c in candidatos:
        hist = signals.load_item_history(c.get("name") or "")
        c["tendencia"] = _tendencia_do_historico(hist)
        c["variacao_pct"] = _variacao_pct_do_historico(hist)
        c["sparkline"] = _sparkline_do_historico(hist)
        # Com poucos pontos a linha fica tão "confiante" quanto uma de
        # 20 -- sem aviso, parece preço estável em vez de "ainda não
        # temos dado suficiente" (achado 2026-11-02, pesquisa de
        # padrões de sites de skin). Não esconde o gráfico, só avisa.
        n_pontos = sum(1 for p in hist[-20:] if p.get("price"))
        c["historico_curto"] = 0 < n_pontos < _HISTORICO_CURTO_LIMIAR
        c["historico_pontos"] = n_pontos


_LIQUIDEZ_ORDEM = ["iliquido", "fino", "moderado", "liquido", "muito_liquido"]

# Filtros como os do Mercado da Steam (2026-11-14): Exterior, Raridade e
# Versão. As regras de nome ficam em catalogo.py (o catálogo usa as mesmas).
_EXTERIORES = catalogo.EXTERIORES
_VERSOES = catalogo.VERSOES
_versao_do_item = catalogo.versao_do_item


def _estado_do_catalogo() -> "dict | None":
    """Resumo do catálogo amplo para a página Status (transparência da
    coleta): tamanho, última volta completa, andamento e bloqueios."""
    est = catalogo.resumo()
    if not est:
        return None
    totais = est.get("totais") or {}
    nomes = [n for n, _tag in catalogo.FATIAS]
    fatia = est.get("fatia")
    andamento = None
    if isinstance(fatia, int) and 0 <= fatia < len(nomes) and totais:
        feito = sum(totais.get(n, 0) for n in nomes[:fatia]) + int(est.get("start") or 0)
        total = sum(totais.values())
        if total:
            andamento = {"pct": min(99, round(100 * feito / total)),
                         "fatia": nomes[fatia]}
    ultima = est.get("ultima_completa_ts")
    ultimo_bloqueio = est.get("ultimo_bloqueio_ts")
    return {
        "itens": est.get("itens_no_banco"),
        "itens_fmt": f"{int(est.get('itens_no_banco') or 0):,}".replace(",", "."),
        "ultima_completa_txt": scan_store.idade_txt(ultima) if ultima else None,
        "duracao_h": (round(est["duracao_ultima_min"] / 60, 1)
                      if est.get("duracao_ultima_min") else None),
        "andamento": andamento,
        "bloqueios": int(est.get("bloqueios") or 0),
        "ultimo_bloqueio_txt": (scan_store.idade_txt(ultimo_bloqueio)
                                if ultimo_bloqueio else None),
        "cotacao_fmt": (f"{est['cotacao_brl_por_usd']:.2f}".replace(".", ",")
                        if est.get("cotacao_brl_por_usd") else None),
        "cotacao_pares": est.get("cotacao_pares"),
    }


def _cartao_do_catalogo(r: dict) -> dict:
    """Item do catálogo amplo (sem nota) no formato que os templates
    usam: nome, preço do dia, quantos à venda, imagem e raridade."""
    icon = r.get("icon")
    suf = r.get("raridade") or ""
    return {
        "catalogo": True,
        "name": r["nome"],
        # Tradução atual, não a gravada na varredura (17/11: "Bastante
        # Usada" virou "Bem Desgastada", o nome da Steam).
        "name_fmt": localize_name(r["nome"]),
        "price": r.get("preco"),
        "price_fmt": fmt.brl(r.get("preco")),
        "a_venda": f"{int(r.get('a_venda') or 0):,}".replace(",", "."),
        "category": r.get("categoria"),
        "icon_url": url_for("icone_cache", hash_icone=icon, v=3) if icon else None,
        "icon_url_2x": (url_for("icone_cache", hash_icone=icon, v=3, tam=384)
                        if icon else None),
        "raridade_classe": "raridade-" + suf if suf else "",
        "raridade_titulo": ("Raridade: " + raridade._RARIDADE_LABELS[suf]
                            if suf in raridade._RARIDADE_LABELS else ""),
        "market_url": _MARKET_LISTING_URL.format(
            name=urllib.parse.quote(r["nome"], safe="")),
        "atualizado_txt": (scan_store.idade_txt(r["atualizado_em"])
                           if r.get("atualizado_em") else None),
    }


def _passa_filtros_steam(c: dict, exterior: "str | None",
                         raridade_sel: "str | None",
                         versao: "str | None") -> bool:
    nome = c.get("name") or ""
    if exterior and not nome.endswith(_EXTERIORES[exterior][0]):
        return False
    if raridade_sel and raridade.raridade_suffix(c) != raridade_sel:
        return False
    if versao and _versao_do_item(nome) != versao:
        return False
    return True


def _formatar_candidato(c: dict, *, com_icone: bool = False,
                        com_historico: bool = False,
                        name_fmt: "str | None" = None) -> dict:
    """Preenche os campos de exibição de um candidato (preço/nome formatados,
    raridade, margem de nota, confiança, URLs e selo de descontinuada).

    Mantido à parte de `_candidatos_filtrados(..., formatar=False)` para que
    rotas paginadas ou de item único só formatem os itens exibidos de fato.
    """
    nome = c.get("name") or ""
    c["price_fmt"] = fmt.brl(c.get("price"))
    c["name_fmt"] = name_fmt if name_fmt is not None else localize_name(nome)
    c["raridade_classe"] = _raridade_classe(c)
    c["raridade_titulo"] = _raridade_titulo(c)
    # Nota crua (signals.raw_score) sem o corte em [0, 100] -- achado
    # 2026-11-04: a soma dos fatores passa de 100 (ou de 0) com
    # frequência pra item muito bom (ou muito ruim), e o corte faz
    # vários itens diferentes mostrarem o mesmo "100"/"0" na tela,
    # mesmo a ORDEM deles já sendo correta por dentro (buy_candidates
    # já desempata por isto). margem != 0 só quando o corte realmente
    # aconteceu -- pra nota normal (1-99) a nota crua bate exatamente
    # com a exibida, margem sempre 0, não aparece nada. Exige
    # `breakdown` não-vazio: sem ele não dá pra confiar que bate com
    # `score` (ex.: dado sintético de teste que só define `score`).
    c["nota_margem"] = None
    if c.get("breakdown"):
        margem = round(signals.raw_score(c["breakdown"])) - (c.get("score") or 0)
        c["nota_margem"] = margem if margem != 0 else None
    # Confiança do dado por trás da nota (signals.data_quality) --
    # achado 2026-11-04: calculada a cada scan, nunca exibida em
    # lugar nenhum (a própria função já dizia "Util para... UI
    # badge: mostrar ao usuário quando confiar no score"). Um item
    # com poucos pontos de histórico (ou histórico velho) calcula a
    # MESMA nota que um com dado rico -- vários fatores (momentum,
    # drawdown, rel_ath, pump_risk) são gateados por tamanho mínimo
    # de amostra, mas isso não aparece pro visitante hoje. Mostra só
    # quando a confiança é baixa -- caso raro é o esperado (como
    # risco baixo não vira coluna), então sem selo nenhum na maioria
    # das linhas.
    dq = c.get("data_quality") or {}
    c["confianca_baixa"] = dq.get("level") in ("low", "very_low", "none")
    if c["confianca_baixa"]:
        n = dq.get("n") or 0
        age = dq.get("age_days")
        if age is not None:
            c["confianca_baixa_titulo"] = (
                f"Nota calculada com só {n} ponto{'s' if n != 1 else ''} de "
                f"histórico da Steam, o mais recente de {age:.0f} dia"
                f"{'s' if round(age) != 1 else ''} atrás — alguns fatores "
                "podem não ter tido dado suficiente pra entrar no cálculo.")
        else:
            c["confianca_baixa_titulo"] = (
                "Nota calculada sem histórico de preço da Steam pra esse "
                "item — a maioria dos fatores não tinha dado suficiente "
                "pra entrar no cálculo.")
    # icon_url_2x pede 384px (2x de 192) -- até 2026-11-08 era cópia
    # do icon_url de 192px (achado da revisão de direção visual: o
    # hero/vitrine mostra esse ícone bem maior que o nativo, perda
    # de nitidez visível). Mesmo hash, cache separado por tamanho
    # (ver icon_cache.py) -- o navegador já escolhe sozinho qual
    # usar pelo density do visitante, sem mudar nenhum template.
    if com_icone:
        c["icon_url"] = (
            url_for("icone_cache", hash_icone=c["icon"], v=3)
            if c.get("icon") else None)
        c["icon_url_2x"] = (
            url_for("icone_cache", hash_icone=c["icon"], v=3, tam=384)
            if c.get("icon") else None)
    else:
        c["icon_url"] = None
        c["icon_url_2x"] = None
    nome_url = urllib.parse.quote(nome, safe="")
    c["market_url"] = _MARKET_LISTING_URL.format(name=nome_url)
    c["coletado_txt"] = (
        scan_store.idade_txt(c["coletado_em"])
        if isinstance(c.get("coletado_em"), (int, float)) else None)
    c["steamdb_url"] = _STEAMDB_SEARCH_URL.format(name=nome_url)
    # achado 2026-10-30: quando tem data exata registrada em
    # retirements.py, cases.py gera "aposentada em DD/MM/AAAA" em
    # vez de "descontinuada" -- esse rótulo (o mais confiável, por
    # ter fonte factual) ficava sem o selo .selo-descontinuada.
    _rotulo_cx = c.get("case_label") or ""
    c["descontinuada"] = (
        "descontinuada" in _rotulo_cx or "aposentada" in _rotulo_cx)
    if com_historico:
        _enriquecer_com_historico([c])
    return c


def _enriquecer_formatacao(candidatos: list[dict], *,
                           com_icone: bool = False,
                           com_historico: bool = False) -> None:
    """Aplica `_formatar_candidato` só na fatia que vai ser exibida."""
    for c in candidatos:
        _formatar_candidato(c, com_icone=com_icone, com_historico=com_historico)


def _candidato_por_nome(scan: "dict | None", name: str) -> "dict | None":
    """Encontra e formata um único item público do scan pelo nome exato,
    aplicando exatamente o filtro de `buy_candidates` sem formatar os demais."""
    if not scan or not name:
        return None
    alvos = [r for r in scan.get("results") or [] if r.get("name") == name]
    if not alvos:
        return None
    base = recommendations.buy_candidates(alvos, owned_names=set(), limit=1)
    if not base:
        return None
    return _formatar_candidato(dict(base[0]), com_icone=False, com_historico=False)


def _candidatos_filtrados(
        scan: "dict | None", categoria: "str | None" = None,
        nota_min: "float | None" = None,
        preco_max: "float | None" = None,
        busca: "str | None" = None,
        ordenar: str = "nota",
        liquidez_min: "str | None" = None,
        com_historico: bool = True,
        com_icone: bool = True,
        exterior: "str | None" = None,
        raridade_sel: "str | None" = None,
        versao: "str | None" = None,
        base_candidatos: "list[dict] | None" = None,
        formatar: bool = True) -> list[dict]:
    """Candidatos públicos: sem dono (sem login ainda), já filtrados.

    Sem limite aqui de propósito -- a paginação é responsabilidade de quem
    chama (a rota), não desta função. `buy_candidates` já ordena por nota
    (desc); `ordenar="preco"` reordena por preço (asc) depois.

    `com_historico=False` pula tendência/sparkline (2 leituras de disco
    por item) -- usar quando quem chama só vai exibir uma FATIA do
    resultado (ex. uma página de 10 em até ~150 candidatos) e vai chamar
    `_enriquecer_com_historico` só nessa fatia depois. Achado 2026-10-26:
    o `index()` lia o histórico de TODOS os candidatos em toda visita,
    mesmo mostrando só uma página por vez.

    `com_icone=False` pula `icon_url`/`icon_url_2x` (2 `url_for` por
    item, caro -- envolve o roteador do Flask) pelo mesmo motivo; usar
    `_enriquecer_com_icone` só na fatia exibida depois. Achado
    2026-11-09 (profiling ao vivo): essas duas chamadas pra TODOS os
    candidatos eram 42% do tempo da home inteira.

    `formatar=False` pula também os campos derivados de exibição (URLs
    escapadas, raridade, `fmt.brl`, `raw_score` e `localize_name` quando
    não há busca) -- quem exibe uma fatia chama `_enriquecer_formatacao`
    depois só nos itens que aparecem na tela.

    `liquidez_min` usa a mesma faixa nomeada de `signals.liquidity_depth`
    (pedido numa pesquisa de como outros sites de skin expõem liquidez,
    2026-11-02) -- item sem o dado (volume/histórico insuficiente) fica
    de fora quando o filtro está ativo: não dá pra confirmar que atende
    o mínimo pedido, mesmo critério "não promete o que não sabe" do
    resto do site.
    """
    if not scan:
        return []
    candidatos = ([dict(r) for r in base_candidatos]
                  if base_candidatos is not None
                  else recommendations.buy_candidates(
                      scan["results"], owned_names=set(),
                      limit=len(scan["results"]) or 1))
    grupos_busca = _compilar_busca(busca) if busca else None
    liquidez_idx = (_LIQUIDEZ_ORDEM.index(liquidez_min)
                    if liquidez_min and liquidez_min in _LIQUIDEZ_ORDEM
                    else None)
    out = []
    for c in candidatos:
        if categoria and c.get("category") != categoria:
            continue
        if nota_min is not None and (c.get("score") or 0) < nota_min:
            continue
        if preco_max is not None and (c.get("price") or 0) > preco_max:
            continue
        if liquidez_idx is not None:
            band = (c.get("liquidity_depth") or {}).get("band")
            if band not in _LIQUIDEZ_ORDEM:
                continue
            if _LIQUIDEZ_ORDEM.index(band) < liquidez_idx:
                continue
        if not _passa_filtros_steam(c, exterior, raridade_sel, versao):
            continue
        name_fmt = None
        if grupos_busca is not None:
            nome = c.get("name") or ""
            name_fmt = localize_name(nome)
            if not _busca_bate_compilada(
                    _texto_busca(_nome_para_busca(nome, name_fmt)),
                    grupos_busca):
                continue
        if formatar:
            _formatar_candidato(c, com_icone=com_icone,
                                com_historico=com_historico, name_fmt=name_fmt)
        out.append(c)
    if ordenar == "preco":
        out.sort(key=lambda c: c.get("price") if c.get("price") is not None
                 else float("inf"))
    return out


def run(host: str = "127.0.0.1", port: int = 5050) -> None:
    """Dev server do Flask. Produção troca por gunicorn/waitress (Fase 3)."""
    create_app().run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run()
