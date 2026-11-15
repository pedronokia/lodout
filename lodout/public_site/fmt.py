"""Formatação monetária e de data/hora usada pelos templates do site público."""
from __future__ import annotations

import datetime

# Visitantes são do Brasil e o servidor roda em UTC (sem TZ configurado
# no container) -- horário de Brasília é UTC-3 fixo (sem horário de
# verão desde 2019). Qualquer data/hora mostrada pra quem usa o site
# deve usar este fuso, nunca o fuso "local" ambíguo do servidor.
FUSO_BR = datetime.timezone(datetime.timedelta(hours=-3))


def brl(v: "float | None") -> str:
    if v is None:
        return "—"
    # Negativo como "−R$ 42,50" (sinal de menos antes da moeda), não
    # "R$ -42,50" -- é como se escreve prejuízo em português (2026-11-15).
    texto = f"R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("\u2212" + texto) if round(v, 2) < 0 else texto


def pct(v: "float | None") -> str:
    """1 casa decimal, vírgula -- sem o '%' (quem chama decide o rótulo)."""
    if v is None:
        return "—"
    return f"{v:.1f}".replace(".", ",")


def data_hora_br(ts: float) -> str:
    """'DD/MM/AAAA HH:MM' no horário de Brasília, a partir de um epoch UTC."""
    return datetime.datetime.fromtimestamp(ts, tz=FUSO_BR).strftime(
        "%d/%m/%Y %H:%M")


def ler_reais(texto: "str | None") -> float:
    """Valor em reais digitado ou colado: aceita "35,10", "35.10",
    "R$ 35,10" e "1.234,56" (ponto de milhar). ValueError se não for um
    número (2026-11-15: colar do histórico da Steam dava erro)."""
    t = (texto or "").replace("R$", "").replace("\u00a0", "").replace(" ", "").strip()
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)

