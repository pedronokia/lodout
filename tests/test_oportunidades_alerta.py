"""Testes para o módulo de alertas de oportunidades de mercado (Discord)."""
from unittest.mock import patch

from lodout.public_site import oportunidades_alerta


def test_extrair_oportunidades_vazio():
    assert oportunidades_alerta.extrair_oportunidades([]) == {}
    assert oportunidades_alerta.extrair_oportunidades([{}]) == {}


def test_extrair_oportunidades_seleciona_destaques():
    itens = [
        {"name": "Skin A", "score": 90, "price": 10.0, "variacao_pct": 2.0, "volume": 100},
        {"name": "Skin B", "score": 50, "price": 20.0, "variacao_pct": -15.5, "volume": 50},
        {"name": "Skin C", "score": 70, "price": 5.0, "variacao_pct": 0.0, "volume": 5000},
        {"name": "Dreams & Nightmares Case", "score": 82, "price": 8.0, "variacao_pct": 1.0, "volume": 800},
    ]
    res = oportunidades_alerta.extrair_oportunidades(itens)
    assert res["maior_nota"]["name"] == "Skin A"
    assert res["maior_queda"]["name"] == "Skin B"
    assert res["mais_negociado"]["name"] == "Skin C"
    assert res["destaque_container"]["name"] == "Dreams & Nightmares Case"
    assert res["total_analisado"] == 4


def test_montar_embed_estrutura_valida():
    oportunidades = {
        "maior_nota": {"name": "AK-47 | Redline (Field-Tested)", "score": 88, "price": 45.0, "name_fmt": "AK-47 | Redline (FT)"},
        "maior_queda": {"name": "AWP | Atheris (Field-Tested)", "score": 60, "price": 12.0, "variacao_pct": -12.4},
        "total_analisado": 380,
    }
    payload = oportunidades_alerta.montar_embed(oportunidades)
    assert "embeds" in payload
    embed = payload["embeds"][0]
    assert "Lodout" in embed["title"]
    assert len(embed["fields"]) == 2
    assert "380 itens" in embed["description"]


def test_verificar_e_enviar_sem_webhook():
    assert not oportunidades_alerta.verificar_e_enviar([], webhook_url=None)


def test_verificar_e_enviar_com_mock(tmp_path):
    itens = [
        {"name": "Skin Top", "score": 95, "price": 100.0, "variacao_pct": -10.0},
    ]
    dedup = tmp_path / "dedup.json"
    url = "https://discord.com/api/webhooks/123456/tokenABC"

    with patch("lodout.public_site.discord_notify.enviar_embed", return_value=True) as mock_send:
        # Primeiro envio com sucesso
        ok = oportunidades_alerta.verificar_e_enviar(itens, webhook_url=url, path_dedup=dedup)
        assert ok is True
        assert mock_send.call_count == 1
        assert dedup.exists()

        # Segundo envio antes do tempo mínimo é ignorado pelo dedup
        ok2 = oportunidades_alerta.verificar_e_enviar(itens, webhook_url=url, path_dedup=dedup)
        assert ok2 is False
        assert mock_send.call_count == 1

        # Forçado passa
        ok3 = oportunidades_alerta.verificar_e_enviar(itens, webhook_url=url, forcar=True, path_dedup=dedup)
        assert ok3 is True
        assert mock_send.call_count == 2
