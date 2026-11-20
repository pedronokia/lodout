"""Verifica se as env vars esperadas pelo site público estão definidas
no ambiente atual.

Roda manualmente ou como passo informativo de deploy (SSH na VM) --
NUNCA automaticamente de dentro do app (ler env var de produção já é
coisa do próprio `server.py`; isto é só um script de apoio, pensado pra
rodar contra o ambiente real na hora de investigar um deploy estranho).

Uso:
    python scripts/check_env_drift.py
    python scripts/check_env_drift.py --servico web
    python scripts/check_env_drift.py --servico worker
    python scripts/check_env_drift.py --servico caddy
"""
from __future__ import annotations

import argparse
import os
import sys

# (variável, descrição, serviços, obrigatória?)
_ESPERADAS: list[tuple[str, str, tuple[str, ...], bool]] = [
    ("SITE_DOMAIN", "domínio público servido pelo Caddy", ("caddy",), True),
    ("LODOUT_DATA_DIR", "pasta de dados persistida (volume)", ("web", "worker"), True),
    ("LODOUT_PUBLIC_SITE_SECURE_COOKIES", "cookies Secure (HTTPS)", ("web",), False),
    ("LODOUT_ADMIN_PASSWORD", "senha do /admin/login (secret GitHub)", ("web",), False),
    ("LODOUT_ADMIN_PASSWORD_HASH", "hash pronto da senha do /admin/login", ("web",), False),
    ("LODOUT_BUILD_ID", "identificador do deploy no rodapé", ("web",), False),
    ("LODOUT_ADMIN_DISCORD_WEBHOOK", "alerta Discord do dono", ("web", "worker"), False),
    ("LODOUT_WORKER_INTERVAL_HORAS", "intervalo entre ciclos do worker (default 6h)", ("web", "worker"), False),
    ("LODOUT_WORKER_ALERT_HORAS", "limite de horas pro alerta de atraso", ("worker",), False),
    ("LODOUT_ITENS_EXTRAS", "itens extras com nota do catálogo", ("worker",), False),
    ("LODOUT_CATALOGO", "liga varredura do catálogo amplo", ("worker",), False),
    ("LODOUT_INVENTARIO_DIARIO", "sincroniza inventário das contas 1x/dia", ("worker",), False),
    ("LODOUT_BACKTEST_DIARIO", "roda backtest diário da nota", ("worker",), False),
    ("LODOUT_TOP_RAPIDO_HORAS", "cadência da rodada rápida do Top 20", ("worker",), False),
]


def verificar_env(servico: str = "todos", env: "dict[str, str] | None" = None) -> list[str]:
    """Confere variáveis do `servico` em `env` (default `os.environ`) e
    retorna a lista de variáveis obrigatórias ausentes."""
    atual = os.environ if env is None else env
    faltando_obrigatorias: list[str] = []
    for nome, desc, servicos, obrigatoria in _ESPERADAS:
        if servico != "todos" and servico not in servicos:
            continue
        presente = nome in atual and atual[nome] != ""
        estado = "OK" if presente else "AUSENTE"
        marca = " (obrigatória)" if obrigatoria and not presente else ""
        print(f"{estado:8} {nome:42} {desc}{marca}")
        if obrigatoria and not presente:
            faltando_obrigatorias.append(nome)
    return faltando_obrigatorias


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Confere env vars do Lodout.")
    parser.add_argument(
        "--servico",
        choices=("todos", "web", "worker", "caddy"),
        default="todos",
        help="Filtra as variáveis esperadas pelo serviço (default: todos).",
    )
    args = parser.parse_args(argv)
    faltando = verificar_env(args.servico)
    if faltando:
        print(f"\nFALTAM OBRIGATÓRIAS: {', '.join(faltando)}")
        return 1
    print("\nTudo que é obrigatório está presente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
