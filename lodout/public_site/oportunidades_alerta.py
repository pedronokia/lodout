"""Envio de alertas automáticos de oportunidades de mercado para o Discord.

Disparado ao fim de cada ciclo do worker (ou manualmente).
Verifica a presença de LODOUT_DISCORD_WEBHOOK_URL ou
LODOUT_DISCORD_OPPORTUNITIES_WEBHOOK. Se configurado, extrai as maiores
oportunidades do scan (maior nota, maior queda recente, lider de giro) e
dispara um embed formatado, respeitando intervalo mínimo entre envios (dedup).
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import time
from pathlib import Path

from lodout._paths import DATA_DIR, atomic_write_text, load_json_record
from lodout.public_site import discord_notify

_logger = logging.getLogger(__name__)

_DEDUP_FILE = DATA_DIR / "oportunidades_discord_last.json"
_INTERVALO_MIN_S = 3600.0  # 1 hora mínima entre envios automáticos


def extrair_oportunidades(resultados: list[dict]) -> dict:
    """Extrai os itens de destaque do ciclo de varredura."""
    if not resultados:
        return {}

    validos = [r for r in resultados if r.get("name") and r.get("price")]
    if not validos:
        return {}

    # 1. Maior nota
    maior_nota = max(validos, key=lambda r: float(r.get("score") or 0))

    # 2. Maior queda recente (dip)
    com_queda = [
        r for r in validos
        if r.get("variacao_pct") is not None and float(r["variacao_pct"]) < -4.0
    ]
    maior_queda = min(com_queda, key=lambda r: float(r["variacao_pct"])) if com_queda else None

    # 3. Mais negociado (volume)
    com_volume = [
        r for r in validos
        if r.get("volume") is not None and float(r["volume"]) > 0
    ]
    mais_negociado = max(com_volume, key=lambda r: float(r["volume"])) if com_volume else None

    # 4. Caixa ou cápsula destaque
    containers = [
        r for r in validos
        if any(k in r["name"] for k in ("Case", "Caixa", "Capsule", "Cápsula", "Package", "Pacote"))
    ]
    destaque_container = max(containers, key=lambda r: float(r.get("score") or 0)) if containers else None

    return {
        "maior_nota": maior_nota,
        "maior_queda": maior_queda,
        "mais_negociado": mais_negociado,
        "destaque_container": destaque_container,
        "total_analisado": len(validos),
    }


def _url_item(nome: str) -> str:
    from urllib.parse import quote
    return f"https://lodout.com/item/{quote(nome)}"


def montar_embed(oportunidades: dict, base_url: str = "https://lodout.com") -> dict:
    """Monta payload do Discord Embed para as oportunidades detectadas."""
    fields = []

    mn = oportunidades.get("maior_nota")
    if mn:
        nome = mn.get("name_fmt") or mn["name"]
        preco = mn.get("price_fmt") or f"R$ {float(mn['price']):.2f}".replace(".", ",")
        score = int(mn.get("score") or 0)
        fields.append({
            "name": "🏆 Maior Pontuação Algorítmica",
            "value": f"**[{nome}]({_url_item(mn['name'])})**\nNota: `{score}/100` · Preço: `{preco}`",
            "inline": False,
        })

    mq = oportunidades.get("maior_queda")
    if mq:
        nome = mq.get("name_fmt") or mq["name"]
        preco = mq.get("price_fmt") or f"R$ {float(mq['price']):.2f}".replace(".", ",")
        pct = float(mq["variacao_pct"])
        fields.append({
            "name": "📉 Maior Recuo Recente (Dip)",
            "value": f"**[{nome}]({_url_item(mq['name'])})**\nVariação: `{pct:.1f}%` · Preço: `{preco}`",
            "inline": False,
        })

    vol = oportunidades.get("mais_negociado")
    if vol and vol != mn:
        nome = vol.get("name_fmt") or vol["name"]
        preco = vol.get("price_fmt") or f"R$ {float(vol['price']):.2f}".replace(".", ",")
        v_num = int(vol["volume"])
        v_txt = f"{v_num / 1000:.1f}k / 24h" if v_num >= 1000 else f"{v_num} / 24h"
        fields.append({
            "name": "⚡ Líder em Giro e Liquidez",
            "value": f"**[{nome}]({_url_item(vol['name'])})**\nVolume: `{v_txt}` · Preço: `{preco}`",
            "inline": False,
        })

    dc = oportunidades.get("destaque_container")
    if dc and dc not in (mn, mq, vol):
        nome = dc.get("name_fmt") or dc["name"]
        preco = dc.get("price_fmt") or f"R$ {float(dc['price']):.2f}".replace(".", ",")
        score = int(dc.get("score") or 0)
        fields.append({
            "name": "📦 Caixa / Cápsula em Alta",
            "value": f"**[{nome}]({_url_item(dc['name'])})**\nNota: `{score}/100` · Preço: `{preco}`",
            "inline": False,
        })

    total = oportunidades.get("total_analisado") or 0
    agora_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return {
        "content": None,
        "embeds": [{
            "title": "🎯 Lodout — Oportunidades Detectadas no Mercado CS2",
            "url": base_url,
            "description": f"Varredura concluída com **{total} itens** analisados pelo algoritmo da Lodout.",
            "color": 16347158,  # #f97316 (laranja Lodout)
            "fields": fields,
            "footer": {
                "text": "Lodout.com · Inteligência Algorítmica de Mercado CS2",
            },
            "timestamp": agora_iso,
        }]
    }


def verificar_e_enviar(resultados: list[dict],
                        webhook_url: str | None = None,
                        forcar: bool = False,
                        path_dedup: Path | None = None) -> bool:
    """Verifica se há webhook configurado e envia o resumo de oportunidades."""
    url = webhook_url or os.environ.get("LODOUT_DISCORD_WEBHOOK_URL") or os.environ.get("LODOUT_DISCORD_OPPORTUNITIES_WEBHOOK")
    if not url or not discord_notify.url_valida(url):
        return False

    caminho_dedup = path_dedup or _DEDUP_FILE
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
        _logger.info("Alerta de oportunidades de mercado enviado para o Discord com sucesso.")
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
