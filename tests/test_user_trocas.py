"""Testes de trocas entre jogadores (lodout/public_site/user_trocas.py)."""
from __future__ import annotations

import pytest

from lodout.public_site import user_store, user_trocas, user_vendidos


def test_load_vazio_e_valor_invalido(tmp_path):
    db = tmp_path / "u.db"
    sid = "76561198000000101"
    assert user_trocas.load(sid, path=db) == []
    user_store.save_user_json(sid, "trocas", {"nao": "lista"}, path=db)
    assert user_trocas.load(sid, path=db) == []


def test_total_soma_quantidade_por_valor():
    assert user_trocas.total([]) == 0.0
    assert user_trocas.total(None) == 0.0
    lado = [
        {"name": "AK-47 | Redline (Field-Tested)", "quantity": 2, "valor": 50.25},
        {"name": "Snakebite Case", "valor": 1.50},  # quantity padrão = 1
        {"name": "Sem valor", "quantity": 3, "valor": 0},
    ]
    assert user_trocas.total(lado) == pytest.approx(102.0)


def test_adicionar_e_remover_respeitam_limites(tmp_path):
    db = tmp_path / "u.db"
    sid = "76561198000000102"
    muitos = [{"name": f"Item {i}", "quantity": 1, "valor": 1.0} for i in range(15)]
    troca = user_trocas.adicionar(
        sid, deu=muitos, recebeu=muitos[:2], notas="x" * 500, ts=1234.5, path=db,
    )
    assert troca["ts"] == 1234.5
    assert len(troca["deu"]) == user_trocas.MAX_ITENS_POR_LADO
    assert len(troca["recebeu"]) == 2
    assert len(troca["notas"]) == 300

    # Adiciona segunda troca com ts automático e valida ordem/remoção.
    troca2 = user_trocas.adicionar(
        sid, deu=[{"name": "A", "quantity": 1, "valor": 10.0}],
        recebeu=[{"name": "B", "quantity": 1, "valor": 12.0}], path=db,
    )
    assert troca2["ts"] > 0
    assert len(user_trocas.load(sid, path=db)) == 2

    # Índices inválidos não alteram nada.
    assert user_trocas.remover(sid, -1, path=db) is None
    assert user_trocas.remover(sid, 99, path=db) is None
    assert len(user_trocas.load(sid, path=db)) == 2

    removida = user_trocas.remover(sid, 0, path=db)
    assert removida["ts"] == 1234.5
    restantes = user_trocas.load(sid, path=db)
    assert len(restantes) == 1 and restantes[0]["deu"][0]["name"] == "A"


def test_migrar_trades_antigos_move_para_vendidos_e_e_idempotente(tmp_path):
    db = tmp_path / "u.db"
    sid = "76561198000000103"
    # Sem registros antigos: 0 movidos.
    assert user_trocas.migrar_trades_antigos(sid, path=db) == 0

    antigos = [
        {"name": "AK-47 | Redline (Field-Tested)", "buy_price": 40.0, "sell_price": 55.0, "ts": 100.0},
        {"name": "Sem preco venda", "buy_price": 10.0},  # ignorado
        "lixo",  # ignorado
        {"name": "Snakebite Case", "buy_price": 1.0, "sell_price": 2.5, "ts": 200.0},
    ]
    user_store.save_user_json(sid, "trades", antigos, path=db)

    movidos = user_trocas.migrar_trades_antigos(sid, path=db)
    assert movidos == 2
    vendidos = user_vendidos.load(sid, path=db)
    assert [v["name"] for v in vendidos] == [
        "AK-47 | Redline (Field-Tested)",
        "Snakebite Case",
    ]
    assert all(v["source"] == "trades" for v in vendidos)
    assert user_store.load_user_json(sid, "trades", [], path=db) == []

    # Idempotência: chamar de novo não duplica nada.
    assert user_trocas.migrar_trades_antigos(sid, path=db) == 0
    assert len(user_vendidos.load(sid, path=db)) == 2
