"""Monitoramento externo independente do worker: valida `/readyz` e
`/api/health` do site público a partir de fora da VM.

Diferente de `worker_alert.py` (que roda dentro do próprio `worker`),
este script detecta quando o site caiu, o banco falhou ou o `worker`
parou de concluir coletas. Usa só stdlib (sem `pip install` no CI).

Uso:
    python scripts/check_site_health.py https://lodout.com
    ADMIN_DISCORD_WEBHOOK=... python scripts/check_site_health.py https://lodout.com
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Callable

_TIMEOUT_S = 15.0
_UA = "Lodout-HealthCheck/1.0"
_WEBHOOK_RE = re.compile(
    r"^https://(discord|discordapp)\.com/api/webhooks/\d+/[\w.-]+/?$"
)


def _http_get_json(url: str, timeout: float = _TIMEOUT_S) -> tuple[int, dict | None, str | None]:
    """Retorna `(status, dados_json, erro)` usando só stdlib."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(resp.status)
            corpo = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), None, f"HTTP {e.code}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, None, str(e)
    try:
        dados = json.loads(corpo)
    except ValueError as e:
        return status, None, f"JSON inválido: {e}"
    if not isinstance(dados, dict):
        return status, None, "JSON inesperado (esperado objeto)"
    return status, dados, None


def verificar_saude(
    base: str,
    *,
    fator_atraso: float = 2.5,
    fetcher: Callable[[str], tuple[int, dict | None, str | None]] = _http_get_json,
) -> list[str]:
    """Confere `/readyz` e `/api/health`. Retorna lista de problemas (vazia = OK)."""
    base = base.rstrip("/")
    problemas: list[str] = []

    status_r, ready_json, erro_r = fetcher(f"{base}/readyz")
    if erro_r:
        problemas.append(f"/readyz falhou: {erro_r}")
    elif status_r != 200 or not ready_json or ready_json.get("ready") is not True:
        motivos = (ready_json or {}).get("motivos")
        detalhe = f" ({'; '.join(motivos)})" if isinstance(motivos, list) and motivos else ""
        problemas.append(f"/readyz não está pronto (HTTP {status_r}){detalhe}")

    status_h, health_json, erro_h = fetcher(f"{base}/api/health")
    if erro_h:
        problemas.append(f"/api/health falhou: {erro_h}")
    elif status_h != 200 or not health_json or health_json.get("ok") is not True:
        problemas.append(f"/api/health respondeu HTTP {status_h} sem ok=true")
    else:
        scan = health_json.get("scan")
        intervalo_h = float(health_json.get("intervalo_horas_configurado") or 6.0)
        limite_s = max(intervalo_h, 1.0) * fator_atraso * 3600.0
        if isinstance(scan, dict) and scan.get("disponivel"):
            idade = scan.get("idade_segundos")
            if isinstance(idade, (int, float)) and idade > limite_s:
                problemas.append(
                    f"scan atrasado: última coleta há {idade / 3600:.1f}h "
                    f"(limite {limite_s / 3600:.1f}h)"
                )

    return problemas


def enviar_alerta_discord(webhook_url: str, mensagem: str) -> bool:
    """Envia alerta simples no webhook do Discord (stdlib)."""
    if not webhook_url or not _WEBHOOK_RE.match(webhook_url):
        return False
    payload = json.dumps({"content": mensagem[:2000]}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": _UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return int(resp.status) in (200, 204)
    except Exception:
        return False


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica saúde externa do Lodout.")
    parser.add_argument("url", help="URL base do site (ex.: https://lodout.com)")
    parser.add_argument(
        "--fator-atraso",
        type=float,
        default=2.5,
        help="Múltiplo do intervalo do worker para considerar scan atrasado (default: 2.5).",
    )
    args = parser.parse_args(argv)

    problemas = verificar_saude(args.url, fator_atraso=args.fator_atraso)
    if not problemas:
        print(f"OK: {args.url} saudável (/readyz e /api/health)")
        return 0

    resumo = "; ".join(problemas)
    print(f"FALHA em {args.url}: {resumo}")
    webhook = os.environ.get("ADMIN_DISCORD_WEBHOOK", "").strip()
    if webhook:
        enviado = enviar_alerta_discord(
            webhook,
            f"🚨 Lodout (checagem externa): {resumo}. Ver {args.url.rstrip('/')}/status",
        )
        print("Alerta Discord:", "enviado" if enviado else "falhou")
    return 1


if __name__ == "__main__":
    sys.exit(main())
