"""Inventário da Steam na conta (plans/archive/conta-inventario.md, fase 2).

A conta mostra os itens do inventário público da pessoa sem ela precisar
digitar nada além de quanto pagou. Sincroniza:

- logo depois do login (ação da própria pessoa), em segundo plano, pra
  não deixar o login lento;
- uma vez por dia pelo worker, para quem entrou nos últimos 30 dias.

Abrir a página da conta NUNCA consulta a Steam (AGENTS.md).

O preço pago não vem da Steam -- só existe no histórico privado do
Mercado, que exigiria a chave de API ou a sessão da pessoa. O site nunca
pede isso; a pessoa digita.
"""
from __future__ import annotations

import logging
import threading
import time

from lodout import steam_api
from lodout.public_site import user_portfolio, user_store

_logger = logging.getLogger(__name__)

_KIND_ESTADO = "inventario_sync"
INTERVALO_S = 24 * 3600
DIAS_ATIVO = 30
# Pausa entre inventários de pessoas diferentes no worker: múltiplo de
# RATE_LIMIT_DELAY_S, lido na hora (mesma regra do catálogo).
_FATOR_PAUSA = 5.0

SOURCE_STEAM = "steam"


def diario_ligado() -> bool:
    """Sincronização diária pelo worker (LODOUT_INVENTARIO_DIARIO=1, só
    produção, como o catálogo). A do login vale sempre."""
    from lodout._ambiente import ambiente
    return (ambiente("INVENTARIO_DIARIO") or "").strip().lower() in ("1", "true", "sim")


def mesclar(posicoes: "list[dict]", itens: "list[dict]",
            agora: "float | None" = None) -> "tuple[list[dict], dict]":
    """Junta o inventário às posições da pessoa. Devolve (posições, resumo).

    - Item novo do inventário entra sem preço pago (a Steam não informa).
    - Item que já veio do inventário tem quantidade e imagem atualizadas;
      o preço pago digitado fica.
    - Item que veio do inventário e SAIU dele: anunciado no Mercado (a
      Steam tira do inventário público até vender) ou vendido/trocado --
      daqui não dá para saber qual. Com valor pago, fica na conta marcado
      `fora_desde` e a pessoa diz se vendeu ("Vendi, tirar da lista"); se
      o anúncio for cancelado e o item voltar, a marca some. Sem valor
      pago, sai (não perde nada e volta sozinho). Antes (15/11) saía
      sempre, e anunciar apagava o valor pago (relato de 16/11).
    - Item adicionado à mão continua como está. Se ele aparece no
      inventário (uma linha só desse nome), passa a ser acompanhado pelo
      inventário, mantendo o preço pago.
    """
    agora = time.time() if agora is None else agora
    inv: dict = {}
    for it in itens or []:
        nome = it.get("name") if isinstance(it, dict) else None
        if nome:
            inv[nome] = it
    manuais_por_nome: dict = {}
    for p in posicoes:
        if p.get("source") != SOURCE_STEAM:
            manuais_por_nome[p.get("name")] = manuais_por_nome.get(p.get("name"), 0) + 1

    # Lotes (2026-11-15): a pessoa pode ter separado as unidades de um
    # item por valor pago. Todas as posições do inventário com o mesmo
    # nome são tratadas juntas.
    lotes_steam: dict = {}
    for p in posicoes:
        if p.get("source") == SOURCE_STEAM:
            lotes_steam.setdefault(p.get("name"), []).append(p)

    saida: list[dict] = []
    steam_tratados: set = set()
    vistos: set = set()
    novos = atualizados = removidos = fora = 0
    for p in posicoes:
        nome = p.get("name")
        if p.get("source") == SOURCE_STEAM:
            if nome in steam_tratados:
                continue  # lote já tratado junto com o primeiro do nome
            steam_tratados.add(nome)
            vistos.add(nome)
            if nome in inv:
                saida.extend(_acertar_lotes(lotes_steam[nome], inv[nome], agora))
                atualizados += 1
            else:
                for lote in lotes_steam[nome]:
                    if lote.get("cost") is None:
                        removidos += 1
                    else:
                        saida.append({**lote, "fora_desde": lote.get("fora_desde") or agora})
                        fora += 1
            continue
        if (nome in inv and nome not in lotes_steam
                and manuais_por_nome.get(nome) == 1 and nome not in vistos):
            it = inv[nome]
            saida.append({**p, "source": SOURCE_STEAM,
                          "quantity": int(it.get("quantity") or 1),
                          "icon": it.get("icon") or p.get("icon")})
            vistos.add(nome)
            atualizados += 1
            continue
        if nome in inv and nome not in lotes_steam:
            vistos.add(nome)  # várias linhas à mão: a pessoa controla
        saida.append(p)
    for nome, it in inv.items():
        if nome in vistos:
            continue
        saida.append({"name": nome, "cost": None,
                      "quantity": int(it.get("quantity") or 1),
                      "added_ts": agora, "source": SOURCE_STEAM,
                      "icon": it.get("icon")})
        novos += 1
    return saida, {"novos": novos, "atualizados": atualizados,
                   "removidos": removidos, "fora": fora}


def _acertar_lotes(lotes: "list[dict]", it: dict, agora: float) -> "list[dict]":
    """Ajusta os lotes de um item à quantidade que o inventário tem hoje.

    - Um lote só no inventário: se a quantidade cresce (ou não há valor pago),
      acompanha o inventário; se parte das unidades com valor pago saiu
      (anunciou/vendeu), as que saíram viram um lote marcado `fora_desde`.
    - Um lote só fora do inventário: se voltou tudo, some a marca; se voltou
      só parte, o restante continua marcado `fora_desde`; se voltou tudo e
      entraram extras, os novos entram sem valor pago.
    - Vários lotes (a pessoa separou por valor pago):
      * chegaram unidades: primeiro voltam as que estavam fora do
        inventário (anúncio cancelado), com o valor pago; o resto entra no
        lote sem valor pago, ou num lote novo sem valor;
      * saíram unidades (anunciou, vendeu ou trocou): saem primeiro as sem
        valor pago, e depois as mais antigas. As que têm valor pago não
        somem: viram um lote marcado `fora_desde` (revisão 16/11).
    """
    from lodout.public_site import user_portfolio
    qtd_inv = int(it.get("quantity") or 1)
    icone = it.get("icon")
    lotes = [{**l, "icon": icone or l.get("icon")} for l in lotes]

    def qtd(l):
        return int(l.get("quantity") or 1)

    def sem_marca(l):
        l = dict(l)
        l.pop("fora_desde", None)
        l.pop("anunciado", None)
        l.pop("anuncio_preco", None)
        return l

    if len(lotes) == 1:
        l0 = lotes[0]
        q0 = qtd(l0)
        if not l0.get("fora_desde"):
            if qtd_inv >= q0 or l0.get("cost") is None:
                return [{**sem_marca(l0), "quantity": qtd_inv}]
            base = dict(l0)
            base.setdefault("lote", user_portfolio.novo_lote())
            return [
                {**base, "quantity": qtd_inv},
                {**base, "quantity": q0 - qtd_inv, "fora_desde": agora,
                 "lote": user_portfolio.novo_lote()},
            ]
        if qtd_inv == q0:
            return [{**sem_marca(l0), "quantity": q0}]
        if qtd_inv < q0:
            return [
                {**sem_marca(l0), "quantity": qtd_inv,
                 "lote": user_portfolio.novo_lote()},
                {**l0, "quantity": q0 - qtd_inv},
            ]
        if l0.get("cost") is None:
            return [{**sem_marca(l0), "quantity": qtd_inv}]
        volta = sem_marca(l0)
        volta.setdefault("lote", user_portfolio.novo_lote())
        return [
            {**volta, "quantity": q0},
            {"name": l0.get("name"), "cost": None,
             "quantity": qtd_inv - q0, "added_ts": agora,
             "source": SOURCE_STEAM, "icon": icone,
             "lote": user_portfolio.novo_lote()},
        ]
    dentro = [l for l in lotes if not l.get("fora_desde")]
    fora = [l for l in lotes if l.get("fora_desde")]
    total = sum(qtd(l) for l in dentro)
    if qtd_inv > total:
        falta = qtd_inv - total
        for l in sorted(fora, key=lambda l: (l.get("fora_desde") or 0)):
            if falta <= 0:
                break
            volta = min(qtd(l), falta)
            if volta == qtd(l):
                fora.remove(l)
                dentro.append(sem_marca(l))
            else:
                l["quantity"] = qtd(l) - volta
                dentro.append({**sem_marca(l), "quantity": volta,
                               "lote": user_portfolio.novo_lote()})
            falta -= volta
        if falta > 0:
            sem_valor = next((l for l in dentro if l.get("cost") is None), None)
            if sem_valor is not None:
                sem_valor["quantity"] = qtd(sem_valor) + falta
            else:
                dentro.append({"name": lotes[0].get("name"), "cost": None,
                               "quantity": falta, "added_ts": agora,
                               "source": SOURCE_STEAM, "icon": icone,
                               "lote": user_portfolio.novo_lote()})
    elif qtd_inv < total:
        sobra = total - qtd_inv
        ordem = sorted(range(len(dentro)), key=lambda i: (
            dentro[i].get("cost") is not None, dentro[i].get("added_ts") or 0, i))
        for i in ordem:
            if sobra <= 0:
                break
            q = qtd(dentro[i])
            tira = min(q, sobra)
            dentro[i]["quantity"] = q - tira
            sobra -= tira
            if dentro[i].get("cost") is not None:
                fora.append({**dentro[i], "quantity": tira, "fora_desde": agora,
                             "lote": user_portfolio.novo_lote()})
        dentro = [l for l in dentro if int(l.get("quantity") or 0) > 0]
    return dentro + fora


def estado(steamid: str) -> dict:
    est = user_store.load_user_json(steamid, _KIND_ESTADO, {})
    return est if isinstance(est, dict) else {}


def _gravar_estado(steamid: str, est: dict) -> None:
    user_store.save_user_json(steamid, _KIND_ESTADO, est)


def sincronizar(steamid: str) -> dict:
    """Busca o inventário público e mescla na conta. Devolve o estado.

    A mesclagem acontece sob `BEGIN IMMEDIATE` (evita perder custos
    digitados enquanto a Steam respondia) e aborta sem gravar se a conta
    existia ao iniciar e foi excluída (`/conta/excluir`) no meio da busca."""
    existia_antes = user_store.get_user(steamid) is not None
    status, itens = steam_api.fetch_inventory(steamid)
    est = estado(steamid)
    est.update({"status": status, "ts": time.time(), "em_andamento": False})
    if status == steam_api.INV_OK or status == steam_api.INV_EMPTY:
        lista_itens = itens if status == steam_api.INV_OK else []

        def _mesclar_atomico(posicoes):
            atual = list(posicoes) if isinstance(posicoes, list) else []
            novas, resumo = mesclar(atual, lista_itens)
            return True, novas, resumo

        gravou, resumo = user_store.update_user_json(
            steamid, "portfolio", list, _mesclar_atomico,
            require_user=existia_antes,
        )
        if existia_antes and not gravou:
            return est
        est["ultimo_ok_ts"] = est["ts"]
        est["resumo"] = resumo
    elif existia_antes and user_store.get_user(steamid) is None:
        return est
    _gravar_estado(steamid, est)
    return est


_em_andamento: set = set()
_trava = threading.Lock()


def sincronizar_em_segundo_plano(steamid: str) -> bool:
    """Dispara a sincronização numa thread (usado no login). False se já
    havia uma em andamento para essa pessoa."""
    with _trava:
        if steamid in _em_andamento:
            return False
        _em_andamento.add(steamid)

    def _rodar():
        try:
            sincronizar(steamid)
        except Exception:
            _logger.error("sincronização do inventário falhou", exc_info=True)
            try:
                est2 = estado(steamid)
                est2.update({"em_andamento": False, "status": steam_api.INV_ERROR,
                             "ts": time.time()})
                _gravar_estado(steamid, est2)
            except Exception:
                pass
        finally:
            with _trava:
                _em_andamento.discard(steamid)

    try:
        est = estado(steamid)
        est["em_andamento"] = True
        est["iniciado_ts"] = time.time()
        _gravar_estado(steamid, est)
        threading.Thread(target=_rodar, name=f"inventario-{steamid}",
                         daemon=True).start()
    except Exception:
        with _trava:
            _em_andamento.discard(steamid)
        raise
    return True


def sincronizar_pendentes(ate_ts: float, deve_parar=lambda: False) -> int:
    """Worker: sincroniza quem entrou nos últimos 30 dias e não foi
    sincronizado nas últimas 24 h. Para no primeiro bloqueio. Devolve
    quantos inventários foram lidos."""
    if steam_api.em_cooldown("inventory"):
        return 0
    agora = time.time()
    feitos = 0
    for steamid in user_store.usuarios_ativos(agora - DIAS_ATIVO * 86400):
        if deve_parar() or time.time() >= ate_ts:
            break
        ultimo = float(estado(steamid).get("ts") or 0)
        if agora - ultimo < INTERVALO_S:
            continue
        if feitos:
            time.sleep(steam_api.RATE_LIMIT_DELAY_S * _FATOR_PAUSA)
        est = sincronizar(steamid)
        feitos += 1
        if est.get("status") == steam_api.INV_RATE_LIMITED:
            _logger.warning("Inventários: bloqueio (429); para até a próxima janela")
            break
    return feitos
