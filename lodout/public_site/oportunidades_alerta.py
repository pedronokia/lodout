"""Envio de alertas automáticos de destaques de mercado para o Discord.

Disparado ao fim de cada ciclo do worker (ou manualmente).
Verifica a presença de LODOUT_DISCORD_WEBHOOK_URL ou
LODOUT_DISCORD_OPPORTUNITIES_WEBHOOK. Se configurado, extrai os principais
destaques observados na coleta (maior nota, maior queda recente, maior volume
em 24 h e caixa/cápsula com maior nota), descartando itens com risco alto de
alta artificial, e envia um embed respeitando o intervalo mínimo entre envios.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import quote

from lodout import _paths, cases, signals
from lodout._paths import atomic_write_text, load_json_record
from lodout.localization import localize_name
from lodout.public_site import discord_notify, fmt

_logger = logging.getLogger(__name__)

_INTERVALO_MIN_S = 3600.0  # 1 hora mínima entre envios automáticos


def _caminho_dedup() -> Path:
    return Path(_paths.DATA_DIR) / "oportunidades_discord_last.json"


def _variacao_recente_pct(item: dict) -> "float | None":
    """Usa `variacao_pct` já calculado ou deriva dos 2 últimos pontos do histórico."""
    bruto = item.get("variacao_pct")
    if isinstance(bruto, (int, float)) and not isinstance(bruto, bool):
        return float(bruto)
    hist = signals.load_item_history(item.get("name") or "")
    if len(hist) < 2:
        return None
    anterior, atual = hist[-2].get("price"), hist[-1].get("price")
    if not anterior or not atual:
        return None
    return round((atual - anterior) / anterior * 100, 1)


def extrair_oportunidades(resultados: list[dict]) -> dict:
    """Extrai os itens de destaque do ciclo de varredura (sem risco alto)."""
    if not resultados:
        return {}

    validos = [
        r for r in resultados
        if r.get("name")
        and isinstance(r.get("price"), (int, float)) and r["price"] > 0
        and ((r.get("pump_risk") or {}).get("level") or "low") != "high"
    ]
    if not validos:
        return {}

    # 1. Maior nota
    maior_nota = max(validos, key=lambda r: float(r.get("score") or 0))

    # 2. Maior queda recente (mais de 4% abaixo da coleta anterior)
    com_queda = []
    for r in validos:
        pct = _variacao_recente_pct(r)
        if pct is not None and pct < -4.0:
            com_queda.append(r if r.get("variacao_pct") is not None else {**r, "variacao_pct": pct})
    maior_queda = min(com_queda, key=lambda r: float(r["variacao_pct"])) if com_queda else None

    # 3. Maior volume em 24 h
    com_volume = [
        r for r in validos
        if r.get("volume") is not None and float(r["volume"]) > 0
    ]
    mais_negociado = max(com_volume, key=lambda r: float(r["volume"])) if com_volume else None

    # 4. Caixa ou cápsula com maior nota
    containers = [
        r for r in validos
        if cases.is_container(r["name"])
        or any(k in r["name"] for k in ("Caixa", "Cápsula", "Pacote"))
    ]
    destaque_container = max(containers, key=lambda r: float(r.get("score") or 0)) if containers else None

    return {
        "maior_nota": maior_nota,
        "maior_queda": maior_queda,
        "mais_negociado": mais_negociado,
        "destaque_container": destaque_container,
        "total_analisado": len(validos),
    }


def _url_item(nome: str, base_url: str = "https://lodout.com") -> str:
    return f"{base_url.rstrip('/')}/item/{quote(nome, safe='')}"


def _nome_exibicao(item: dict) -> str:
    return item.get("name_fmt") or localize_name(item["name"])


def _preco_exibicao(item: dict) -> str:
    return item.get("price_fmt") or fmt.brl(float(item["price"]))


def montar_embed(oportunidades: dict, base_url: str = "https://lodout.com") -> dict:
    """Monta payload do Discord Embed para os destaques observados na coleta."""
    fields = []

    mn = oportunidades.get("maior_nota")
    if mn:
        nome = _nome_exibicao(mn)
        preco = _preco_exibicao(mn)
        score = int(mn.get("score") or 0)
        fields.append({
            "name": "Maior nota hoje",
            "value": f"**[{nome}]({_url_item(mn['name'], base_url)})**\nNota: `{score}` · Preço: `{preco}`",
            "inline": False,
        })

    mq = oportunidades.get("maior_queda")
    if mq:
        nome = _nome_exibicao(mq)
        preco = _preco_exibicao(mq)
        pct = float(mq["variacao_pct"])
        fields.append({
            "name": "Maior queda recente",
            "value": f"**[{nome}]({_url_item(mq['name'], base_url)})**\nVariação: `{pct:.1f}%` · Preço: `{preco}`",
            "inline": False,
        })

    vol = oportunidades.get("mais_negociado")
    if vol and vol != mn:
        nome = _nome_exibicao(vol)
        preco = _preco_exibicao(vol)
        v_num = int(vol["volume"])
        v_txt = f"{v_num / 1000:.1f}k / 24h" if v_num >= 1000 else f"{v_num} / 24h"
        fields.append({
            "name": "Maior volume em 24 h",
            "value": f"**[{nome}]({_url_item(vol['name'], base_url)})**\nVolume: `{v_txt}` · Preço: `{preco}`",
            "inline": False,
        })

    dc = oportunidades.get("destaque_container")
    if dc and dc not in (mn, mq, vol):
        nome = _nome_exibicao(dc)
        preco = _preco_exibicao(dc)
        score = int(dc.get("score") or 0)
        fields.append({
            "name": "Caixa ou cápsula com maior nota",
            "value": f"**[{nome}]({_url_item(dc['name'], base_url)})**\nNota: `{score}` · Preço: `{preco}`",
            "inline": False,
        })

    total = oportunidades.get("total_analisado") or 0
    agora_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "content": None,
        "embeds": [{
            "title": "Lodout — Destaques observados no mercado de Counter-Strike 2",
            "url": base_url,
            "description": f"Coleta concluída com **{total} itens** analisados.",
            "color": 16347158,  # #f97316 (laranja Lodout)
            "fields": fields,
            "footer": {
                "text": "Lodout · Dados observados da Steam (sem promessa de retorno)",
            },
            "timestamp": agora_iso,
        }]
    }


def verificar_e_enviar(resultados: list[dict],
                        webhook_url: str | None = None,
                        forcar: bool = False,
                        path_dedup: Path | None = None) -> bool:
    """Verifica se há webhook configurado e envia o resumo de destaques."""
    url = webhook_url or os.environ.get("LODOUT_DISCORD_WEBHOOK_URL") or os.environ.get("LODOUT_DISCORD_OPPORTUNITIES_WEBHOOK")
    if not url or not discord_notify.url_valida(url):
        return False

    caminho_dedup = Path(path_dedup) if path_dedup is not None else _caminho_dedup()
    agora = time.time()

    if not forcar and caminho_dedup.exists():
        try:
            ultimo = load_json_record(caminho_dedup, {})
            ts_ultimo = float(ultimo.get("ts", 0))
            if (agora - ts_ultimo) < _INTERVALO_MIN_S:
                _logger.info("Alerta de oportunidades ignorado: enviado há %.0fs (mínimo %ds)",
                             agora - ts_ultimo, int(_INTERVALO_MIN_S))
                return False
        except Exception:
            pass

    oportunidades = extrair_oportunidades(resultados)
    if not oportunidades.get("maior_nota"):
        return False

    payload = montar_embed(oportunidades)
    sucesso = discord_notify.enviar_embed(url, payload)

    if sucesso:
        _logger.info("Alerta de destaques de mercado enviado para o Discord com sucesso.")
        try:
            registro = {
                "ts": agora,
                "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "maior_nota": oportunidades.get("maior_nota", {}).get("name"),
            }
            atomic_write_text(caminho_dedup, json.dumps(registro))
        except Exception:
            pass

    return sucesso
