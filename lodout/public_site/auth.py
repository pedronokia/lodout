"""Login exigido e proteção CSRF compartilhados pelas rotas pessoais."""
from __future__ import annotations

import secrets
from functools import wraps

from flask import abort, jsonify, redirect, request, session, url_for

# Token que não bate com a sessão de quem está logado: quase sempre é uma
# aba aberta antes de sair e entrar de novo (o token recomeça no login).
PAGINA_VELHA = ("Não salvou: a página ficou desatualizada porque você "
                "entrou de novo em outra aba. ")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("steamid"):
            return redirect(url_for("account.login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token() -> str:
    """Token por sessão pras POST autenticadas -- sem isto, qualquer site
    externo poderia montar um form que muda seus dados só por você estar
    logado (CSRF clássico)."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


def csrf_valid(token: "str | None") -> bool:
    """`token` precisa existir: sem isto, uma sessao que NUNCA visitou
    uma pagina com formulario (entao nunca gerou token) e um form
    forjado que tambem omite o campo comparariam None == None e
    passariam -- o cenario exato que o CSRF tenta impedir.

    `secrets.compare_digest` (tempo constante) em vez de `==`/`!=` --
    achado de auditoria, 2026-11-04: comparar o token assim caractere a
    caractere deixa vazar, pelo tempo de resposta, em qual posição a
    tentativa divergiu do valor certo. Risco baixo na prática (ruído de
    rede atrapalha a medição), mas é a defesa padrão recomendada pra
    comparação de segredo, e não muda nenhum comportamento."""
    stored = session.get("csrf_token")
    if not stored or not token:
        return False
    return secrets.compare_digest(token, stored)


def csrf_protect(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not csrf_valid(request.form.get("csrf_token")):
            # O script da conta mostra o aviso ao lado do campo, com
            # "Recarregar"; sem script, o 403 vira a página explicativa
            # (403.html). Antes, os dois diziam "login expirou" ou
            # "Forbidden" em inglês (revisão 2026-11-16).
            if (session.get("steamid") and "application/json"
                    in (request.headers.get("Accept") or "")):
                return jsonify({"ok": False, "falha": "pagina_velha",
                                "erro": PAGINA_VELHA, "recarregar": True}), 409
            abort(403)
        return view(*args, **kwargs)
    return wrapped
