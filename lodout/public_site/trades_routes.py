"""Redirecionamento de `/conta/trades` para `/conta` após remoção do recurso."""
from __future__ import annotations

from flask import Blueprint, redirect, url_for

from lodout.public_site.auth import login_required

bp = Blueprint("trades", __name__)


@bp.route("/conta/trades", methods=["GET", "POST"])
@login_required
def listar():
    return redirect(url_for("account.conta"))


@bp.route("/conta/trades/<path:_extra>", methods=["GET", "POST"])
@login_required
def redirecionar(_extra: str = ""):
    return redirect(url_for("account.conta"))
