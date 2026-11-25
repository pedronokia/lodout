"""Alerta no Discord do DONO (não do usuário -- isso é `user_webhook.py`,
por conta/watchlist) quando o worker passa N horas sem completar um
ciclo com itens > 0.

Motivo: o bloqueio real de 429 de 2026-10-25 durou mais de 5 horas sem
ninguém notar até abrir o `/admin` manualmente. Webhook fica em
`LODOUT_ADMIN_DISCORD_WEBHOOK` (env var, nunca hardcoded -- só o dono
tem o link do canal dele). Dedup por `_DEDUP_HORAS`: sem isso, cada
ciclo de 6h sem sucesso mandaria outro alerta pro mesmo incidente.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from lodout._paths import DATA_DIR, atomic_write_text, load_json_record
from lodout.public_site import catalogo, db_backup, discord_notify
from lodout._ambiente import ambiente

_ESTADO_PATH = DATA_DIR / "worker_alert_state.json"
_HORAS_LIMITE_DEFAULT = 3.0
_DEDUP_HORAS = 6.0

_ESTADO_DISCO_PATH = DATA_DIR / "disk_alert_state.json"
_ESTADO_QUALIDADE_PATH = DATA_DIR / "scan_quality_alert_state.json"
# Cobertura (itens com preço novo / alvos) abaixo disto num ciclo que
# "deu certo" é scan degradado -- o alerta de atraso acima não vê isso.
_COBERTURA_MIN_PCT = 85.0
_DEDUP_QUALIDADE_HORAS = 24.0
_DISCO_LIVRE_PCT_LIMITE = 10.0
_DEDUP_DISCO_HORAS = 24.0

_ESTADO_BACKUP_PATH = DATA_DIR / "backup_alert_state.json"
# Os três grupos renovam a cada ~20h (db_backup._INTERVALO_MIN_S); 48h é
# 2x essa janela -- margem pra 1 ciclo perdido (Steam bloqueando, VM
# reiniciando) não virar alarme falso.
_BACKUP_IDADE_LIMITE_H = 48.0
_DEDUP_BACKUP_HORAS = 24.0

_ESTADO_CATALOGO_PATH = DATA_DIR / "catalogo_alert_state.json"
# Uma volta completa renova a cada ~24h (catalogo._INTERVALO_RODADA_H_
# PADRAO); 72h é 3x essa janela -- margem pra 1-2 voltas perdidas por
# bloqueio real da Steam não virarem alarme falso.
_CATALOGO_IDADE_LIMITE_H = 72.0
_DEDUP_CATALOGO_HORAS = 24.0
# Rodada que termina com fatias puladas por 404 não renova o relógio da
# volta completa. Com 3+ fatias perdidas, avisa na hora em vez de esperar
# as 72h do alerta genérico (25/11: 10 fatias puladas e "completa" no ar).
_CATALOGO_404_FATIAS_ALERTA = 3


def verificar_e_alertar(historico_ciclos: list[dict],
                        now: "float | None" = None,
                        path: "Path | str | None" = None) -> bool:
    """Manda o alerta se: webhook configurado + último ciclo com itens>0
    foi há mais de `LODOUT_WORKER_ALERT_HORAS` (default 3h) + não
    mandou outro alerta nas últimas `_DEDUP_HORAS`. True se mandou."""
    webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
    if not webhook or not historico_ciclos:
        return False
    agora = time.time() if now is None else now
    limite_horas = float(ambiente("WORKER_ALERT_HORAS", _HORAS_LIMITE_DEFAULT))
    ultimo_sucesso = next(
        (c for c in reversed(historico_ciclos) if c.get("itens", 0) > 0), None)
    referencia_ts = (ultimo_sucesso or historico_ciclos[0])["ts"]
    horas_sem_sucesso = (agora - referencia_ts) / 3600
    if horas_sem_sucesso < limite_horas:
        return False

    p = Path(path) if path is not None else _ESTADO_PATH
    estado = load_json_record(p, {})
    if not isinstance(estado, dict):
        estado = {}
    if agora - estado.get("ultimo_alerta_ts", 0) < _DEDUP_HORAS * 3600:
        return False

    enviado = discord_notify.enviar(
        webhook,
        f"⚠️ Lodout: o worker está há {horas_sem_sucesso:.1f}h sem "
        "trazer nenhum item (provável bloqueio da Steam). Ver /status ou "
        "/admin pro histórico de ciclos.")
    if enviado:
        try:
            atomic_write_text(p, json.dumps({"ultimo_alerta_ts": agora}))
        except OSError:
            pass
    return enviado


def verificar_disco_e_alertar(now: "float | None" = None,
                              path: "Path | str | None" = None) -> bool:
    """Alerta se o disco da partição de `DATA_DIR` tiver menos de
    `_DISCO_LIVRE_PCT_LIMITE`% livre -- numa VM pequena, backups/cache
    acumulando podem encher o disco sem avisar antes do app começar a
    falhar gravação. Dedup separado do alerta de worker atrasado (outro
    tipo de problema, mesmo princípio de não repetir o alerta a cada
    ciclo)."""
    webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
    if not webhook:
        return False
    try:
        uso = shutil.disk_usage(DATA_DIR)
    except OSError:
        return False
    if not uso.total:
        return False
    livre_pct = 100 * uso.free / uso.total
    if livre_pct >= _DISCO_LIVRE_PCT_LIMITE:
        return False

    agora = time.time() if now is None else now
    p = Path(path) if path is not None else _ESTADO_DISCO_PATH
    estado = load_json_record(p, {})
    if not isinstance(estado, dict):
        estado = {}
    if agora - estado.get("ultimo_alerta_ts", 0) < _DEDUP_DISCO_HORAS * 3600:
        return False

    enviado = discord_notify.enviar(
        webhook,
        f"⚠️ Lodout: disco com só {livre_pct:.1f}% livre na VM. "
        "Ver /admin pro tamanho do banco/backups.")
    if enviado:
        try:
            atomic_write_text(p, json.dumps({"ultimo_alerta_ts": agora}))
        except OSError:
            pass
    return enviado


def _ciclo_bom(ciclo: dict) -> bool:
    """True se `ciclo` teve cobertura boa (>= `_COBERTURA_MIN_PCT`) e sem
    throttle silencioso -- o mesmo critério de "deu certo" que decide se
    `verificar_qualidade_e_alertar` dispara, usado também pra saber se a
    situação se recuperou entre um alerta e outro."""
    alvos = ciclo.get("alvos")
    if not isinstance(alvos, int) or alvos <= 0:
        return False
    itens = int(ciclo.get("itens") or 0)
    cobertura = 100.0 * itens / alvos
    throttle = int(ciclo.get("throttle_silencioso") or 0)
    return cobertura >= _COBERTURA_MIN_PCT and not throttle


def _teve_ciclo_bom_desde(historico_ciclos: list[dict], desde_ts: float) -> bool:
    """True se algum ciclo depois de `desde_ts` (exceto o mais recente,
    que é o que `verificar_qualidade_e_alertar` está avaliando agora)
    teve cobertura boa -- usado pra NÃO deixar o dedup de 24h engolir um
    novo episódio de bloqueio só porque o anterior ainda está dentro da
    janela (achado real, 2026-11-21: uma coleta de 0,4% de cobertura
    ficou muda porque o alerta de uma coleta de 28%, outro episódio,
    tinha disparado 18h antes -- no meio das duas, uma coleta de 100%)."""
    for ciclo in historico_ciclos[:-1]:
        ts = ciclo.get("ts")
        if isinstance(ts, (int, float)) and ts > desde_ts and _ciclo_bom(ciclo):
            return True
    return False


def verificar_qualidade_e_alertar(historico_ciclos: list[dict],
                                  now: "float | None" = None,
                                  path: "Path | str | None" = None) -> bool:
    """Alerta se o ÚLTIMO ciclo trouxe preço novo pra menos de
    `_COBERTURA_MIN_PCT`% dos alvos, ou se detectou throttle silencioso.
    O alerta de atraso só dispara com zero item por horas; um scan que
    volta pela metade todo ciclo passava em silêncio. Dedup de 24h --
    mas só enquanto a degradação for a MESMA: um ciclo de cobertura boa
    no meio reseta a janela, pra um novo episódio sempre avisar."""
    webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
    if not webhook or not historico_ciclos:
        return False
    ultimo = historico_ciclos[-1]
    alvos = ultimo.get("alvos")
    if not isinstance(alvos, int) or alvos <= 0:
        return False  # ciclo de antes do registro de cobertura
    itens = int(ultimo.get("itens") or 0)
    cobertura = 100.0 * itens / alvos
    throttle = int(ultimo.get("throttle_silencioso") or 0)
    if itens == 0 or (cobertura >= _COBERTURA_MIN_PCT and not throttle):
        return False  # zero item já é do alerta de atraso

    agora = time.time() if now is None else now
    p = Path(path) if path is not None else _ESTADO_QUALIDADE_PATH
    estado = load_json_record(p, {})
    if not isinstance(estado, dict):
        estado = {}
    ultimo_alerta_ts = estado.get("ultimo_alerta_ts", 0)
    dentro_do_dedup = agora - ultimo_alerta_ts < _DEDUP_QUALIDADE_HORAS * 3600
    if dentro_do_dedup and not _teve_ciclo_bom_desde(historico_ciclos, ultimo_alerta_ts):
        return False

    partes = []
    if cobertura < _COBERTURA_MIN_PCT:
        partes.append(f"só {itens} de {alvos} itens ({cobertura:.0f}%) "
                      "vieram com preço novo")
    if throttle:
        partes.append(f"throttle silencioso detectado {throttle}x")
    enviado = discord_notify.enviar(
        webhook,
        "⚠️ Lodout: última coleta de preços degradada — "
        + "; ".join(partes) + ". Ver /status (itens sem preço) e /api/health.")
    if enviado:
        try:
            atomic_write_text(p, json.dumps({"ultimo_alerta_ts": agora}))
        except OSError:
            pass
    return enviado


def verificar_backup_e_alertar(now: "float | None" = None,
                               path: "Path | str | None" = None) -> bool:
    """Alerta se algum grupo de backup (banco/notas/json) que JÁ teve
    pelo menos um backup está há mais de `_BACKUP_IDADE_LIMITE_H` sem
    renovar -- nunca antes do primeiro backup de um grupo (instalação
    nova, ou grupo desligado, não é motivo de alerta). Dedup de 24h,
    mesmo princípio dos outros alertas deste módulo."""
    webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
    if not webhook:
        return False
    agora = time.time() if now is None else now
    idades = db_backup.idade_dos_backups(now=agora)
    atrasados = {k: v for k, v in idades.items()
                if v is not None and v > _BACKUP_IDADE_LIMITE_H}
    if not atrasados:
        return False

    p = Path(path) if path is not None else _ESTADO_BACKUP_PATH
    estado = load_json_record(p, {})
    if not isinstance(estado, dict):
        estado = {}
    if agora - estado.get("ultimo_alerta_ts", 0) < _DEDUP_BACKUP_HORAS * 3600:
        return False

    partes = ", ".join(f"{chave} há {horas:.0f}h"
                       for chave, horas in sorted(atrasados.items()))
    enviado = discord_notify.enviar(
        webhook,
        f"⚠️ Lodout: backup sem renovar há mais tempo que o esperado — "
        f"{partes}. Ver /api/health -> backups.")
    if enviado:
        try:
            atomic_write_text(p, json.dumps({"ultimo_alerta_ts": agora}))
        except OSError:
            pass
    return enviado


def verificar_catalogo_e_alertar(now: "float | None" = None,
                                 path: "Path | str | None" = None) -> bool:
    """Alerta se o catálogo amplo está ligado (`LODOUT_CATALOGO=1`) mas
    não completa uma volta há mais de `_CATALOGO_IDADE_LIMITE_H` -- nunca
    antes da primeira volta completar (catálogo ligado agora mesmo não é
    atraso). Também alerta na hora quando a rodada termina com 3+ fatias
    puladas por 404, que não renovam `ultima_completa_ts`. Dedup de 24h,
    mesmo princípio dos outros alertas deste módulo."""
    webhook = ambiente("ADMIN_DISCORD_WEBHOOK", "")
    if not webhook or not catalogo.ligado():
        return False
    resumo = catalogo.resumo()
    agora = time.time() if now is None else now
    puladas = int(resumo.get("erros_404_fatias_rodada") or 0)
    fim_rodada = float(resumo.get("fim_ultima_rodada_ts") or 0)
    falha_404 = (resumo.get("motivo") == "incompleta_404"
                 and puladas >= _CATALOGO_404_FATIAS_ALERTA
                 and fim_rodada > 0)
    idade_h = 0.0
    if not falha_404:
        ultima = resumo.get("ultima_completa_ts")
        if not ultima:
            return False
        idade_h = (agora - float(ultima)) / 3600
        if idade_h <= _CATALOGO_IDADE_LIMITE_H:
            return False

    p = Path(path) if path is not None else _ESTADO_CATALOGO_PATH
    estado = load_json_record(p, {})
    if not isinstance(estado, dict):
        estado = {}
    ultimo_alerta = float(estado.get("ultimo_alerta_ts") or 0)
    if agora - ultimo_alerta < _DEDUP_CATALOGO_HORAS * 3600:
        return False
    # A mesma rodada já alertada não dispara de novo só porque o worker
    # conferiu outra vez no mesmo dia.
    if falha_404 and fim_rodada <= ultimo_alerta:
        return False

    if falha_404:
        texto = (
            f"⚠️ Lodout: catálogo amplo terminou uma rodada com "
            f"{puladas} categoria(s) sem acesso (404) e só "
            f"{resumo.get('itens_ultima')} itens. Isso não conta como "
            "volta completa. Ver /api/health -> catalogo.")
    else:
        motivo = resumo.get("motivo") or "desconhecido"
        bloqueios = resumo.get("bloqueios") or 0
        texto = (
            f"⚠️ Lodout: catálogo amplo sem completar uma volta há "
            f"{idade_h:.0f}h (motivo: {motivo}, {bloqueios} bloqueio(s)). "
            "Ver /api/health -> catalogo.")
    enviado = discord_notify.enviar(webhook, texto)
    if enviado:
        try:
            atomic_write_text(p, json.dumps({"ultimo_alerta_ts": agora}))
        except OSError:
            pass
    return enviado
