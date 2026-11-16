"""Testes das rotas de conta (login/logout/portfólio) -- Flask test client.

`db._DB_PATH` é monkeypatchado (não `path=` explícito): as rotas de
`account.py` não recebem `path` do chamador, então o isolamento por teste
depende do módulo reler `_DB_PATH` em tempo de chamada -- exatamente o
que `db.connect` foi desenhado pra fazer (ver gotcha #17 do AGENTS.md:
isto só funciona porque `db.connect` resolve o default DENTRO da função,
não como valor de parâmetro congelado na definição).
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import time
import pytest

from lodout.public_site import db
from lodout.public_site.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "public_site.db")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _login(client, monkeypatch, steamid="76561198000000000",
          nome="Fulano", avatar="http://x/a.jpg"):
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: steamid)
    monkeypatch.setattr(
        "lodout.public_site.account.fetch_public_profile",
        lambda sid: {"name": nome, "avatar_url": avatar})
    return client.get(
        "/login/callback", query_string=_callback_query(_start_login(client)))


def _start_login(client):
    login_resp = client.get("/login")
    openid_params = parse_qs(urlsplit(login_resp.headers["Location"]).query)
    return openid_params["openid.return_to"][0]


def _callback_query(return_to):
    query = {
        key: values[0]
        for key, values in parse_qs(urlsplit(return_to).query).items()
    }
    query.update({"openid.mode": "id_res", "openid.return_to": return_to})
    return query


# ── login/logout ─────────────────────────────────────────────

def test_login_redireciona_pra_steam(client):
    resp = client.get("/login")
    assert resp.status_code == 302
    assert "steamcommunity.com/openid/login" in resp.headers["Location"]


def test_login_callback_invalido_volta_pro_dashboard(client, monkeypatch):
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: None)
    resp = client.get(
        "/login/callback", query_string=_callback_query(_start_login(client)))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_login_callback_sem_fluxo_iniciado_nao_autentica(client, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: chamadas.append(args) or "76561198000000000")

    resp = client.get("/login/callback?openid.mode=id_res")

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert chamadas == []
    with client.session_transaction() as sess:
        assert "steamid" not in sess


def test_login_callback_exige_return_to_da_sessao(client, monkeypatch):
    return_to = _start_login(client)
    chamadas = []
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: chamadas.append(args) or "76561198000000000")

    query = _callback_query(return_to)
    query["state"] = "estado-de-outra-sessao"
    resp = client.get("/login/callback", query_string=query)

    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert chamadas == []


def test_login_callback_so_aceita_o_return_to_uma_vez(client, monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: chamadas.append(args) or "76561198000000000")
    return_to = _start_login(client)
    query = _callback_query(return_to)

    primeiro = client.get("/login/callback", query_string=query)
    replay = client.get("/login/callback", query_string=query)

    assert primeiro.headers["Location"].endswith("/conta")
    assert replay.headers["Location"].endswith("/")
    assert len(chamadas) == 1


def test_login_callback_sucesso_cria_sessao_e_redireciona_pra_conta(
        client, monkeypatch):
    resp = _login(client, monkeypatch)
    assert resp.status_code == 302
    assert "/conta" in resp.headers["Location"]


def test_login_callback_cria_usuario_no_banco(client, monkeypatch):
    _login(client, monkeypatch, steamid="123", nome="Fulano")
    from lodout.public_site import user_store
    assert user_store.get_user("123")["persona_name"] == "Fulano"


def test_logout_limpa_sessao(client, monkeypatch):
    _login(client, monkeypatch)
    client.get("/logout")
    resp = client.get("/conta")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ── /conta exige login ───────────────────────────────────────

def test_conta_sem_login_redireciona(client):
    resp = client.get("/conta")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_conta_logado_mostra_pagina(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta")
    assert resp.status_code == 200
    assert "Fulano".encode() in resp.data


def test_conta_busca_usuario_uma_vez_so(client, monkeypatch):
    """`conta()` passava `usuario=user_store.get_user(steamid)` pro
    template, mas o context processor `_inject_usuario` (server.py) já
    busca o MESMO usuário pra todo template com sessão ativa -- dobrava
    a leitura SQLite (duas conexões abertas/fechadas) sem mudar nenhum
    valor. Corrigido pra deixar só o context processor buscar."""
    from lodout.public_site import user_store
    _login(client, monkeypatch)
    chamadas = []
    original = user_store.get_user

    def _contada(steamid, path=None):
        chamadas.append(steamid)
        return original(steamid, path=path)

    monkeypatch.setattr(user_store, "get_user", _contada)
    resp = client.get("/conta")
    assert resp.status_code == 200
    assert "Fulano".encode() in resp.data
    assert len(chamadas) == 1


def test_conta_vazia_mostra_empty_state(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta")
    assert "Nenhum item ainda".encode("utf-8") in resp.data


# ── CRUD de posicoes ─────────────────────────────────────────

def _csrf_token(client):
    html = client.get("/conta").data.decode("utf-8")
    import re
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1)


def test_adicionar_posicao(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    resp = client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline (Field-Tested)", "cost": "50.00",
        "quantity": "1", "csrf_token": token,
    })
    assert resp.status_code == 302
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Testada em Campo" in pagina  # localize_name
    assert 'class="tabela-candidatos tabela-cards-mobile tabela-conta"' in pagina
    assert 'data-label="Você pagou"' in pagina
    assert 'data-label="Lucro hoje"' in pagina


def test_posicao_mostra_icone_raridade_e_nota_do_scan_atual(
        client, monkeypatch):
    """achado 2026-11-07: o portfólio não mostrava ícone nem nota nenhum,
    só o nome em texto puro -- mesmo gap já corrigido na watchlist/
    trades (ver raridade.py e account._scan_lookup)."""
    monkeypatch.setattr(
        "lodout.scan_store.load_last_scan", lambda: {
            "ts": 0.0, "category": "Facas", "results": [
                {"name": "AK-47 | Redline (Field-Tested)", "score": 77,
                 "icon": "hash-ak", "name_color": "EB4B4B"},
            ]})
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline (Field-Tested)", "cost": "50.00",
        "quantity": "1", "csrf_token": token,
    })
    pagina = client.get("/conta").data.decode("utf-8")
    assert "icone-item-quadro-compacto" in pagina
    assert "icone-item-quadro-com-imagem" in pagina
    assert "raridade-covert" in pagina
    assert 'title="Nota do Lodout">nota 77</span>' in pagina


def test_adicionar_posicao_sem_csrf_falha(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.post("/conta/posicoes", data={
        "name": "X", "cost": "1", "quantity": "1",
    })
    assert resp.status_code == 403


def test_adicionar_posicao_sem_login_redireciona(client):
    resp = client.post("/conta/posicoes", data={"name": "X"})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_adicionar_posicao_rejeita_custo_nao_numerico(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    resp = client.post("/conta/posicoes", data={
        "name": "X", "cost": "abc", "quantity": "1",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    pagina = client.get(resp.headers["Location"]).data.decode("utf-8")
    assert "O custo precisa ser um número válido e igual ou maior que zero" in pagina
    assert "Nenhum item ainda" in pagina


def test_adicionar_posicao_rejeita_quantidade_zero(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    resp = client.post("/conta/posicoes", data={
        "name": "X", "cost": "10", "quantity": "0",
        "csrf_token": token,
    })
    assert resp.status_code == 302
    pagina = client.get(resp.headers["Location"]).data.decode("utf-8")
    assert "A quantidade precisa ser um número inteiro maior que zero" in pagina
    assert "Nenhum item ainda" in pagina


def test_editar_custo(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "X", "cost": "10", "quantity": "1", "csrf_token": token,
    })
    client.post("/conta/posicoes/X/custo", data={
        "cost": "99.90", "csrf_token": token,
    })
    pagina = client.get("/conta").data.decode("utf-8")
    assert "99,90" in pagina


def test_editar_custo_invalido_preserva_custo_atual(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "X", "cost": "10", "quantity": "1", "csrf_token": token,
    })
    resp = client.post("/conta/posicoes/X/custo", data={
        "cost": "-1", "csrf_token": token,
    })
    assert resp.status_code == 302
    pagina = client.get(resp.headers["Location"]).data.decode("utf-8")
    assert "O valor pago precisa ser um número igual ou maior que zero" in pagina
    assert "10,00" in pagina


def test_remover_posicao(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "X", "cost": "10", "quantity": "1", "csrf_token": token,
    })
    client.post("/conta/posicoes/X/remover", data={"csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Nenhum item ainda".encode("utf-8") in pagina.encode("utf-8")


def test_posicoes_isoladas_entre_contas(client, monkeypatch):
    _login(client, monkeypatch, steamid="111")
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "ItemDoUm", "cost": "1", "quantity": "1",
        "csrf_token": token,
    })
    client.get("/logout")
    _login(client, monkeypatch, steamid="222")
    pagina = client.get("/conta").data.decode("utf-8")
    assert "ItemDoUm" not in pagina


# ── excluir conta ────────────────────────────────────────────

def test_excluir_confirmar_sem_login_redireciona(client):
    resp = client.get("/conta/excluir")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_excluir_confirmar_mostra_pagina(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta/excluir")
    assert resp.status_code == 200
    assert "irreversível".encode("utf-8") in resp.data.lower()


def test_excluir_sem_csrf_falha(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.post("/conta/excluir", data={})
    assert resp.status_code == 403


def test_excluir_apaga_conta_e_desloga(client, monkeypatch):
    _login(client, monkeypatch, steamid="76561198000000000")
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "X", "cost": "1", "quantity": "1", "csrf_token": token,
    })
    resp = client.post("/conta/excluir", data={"csrf_token": token})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    # sessao foi limpa -- /conta volta a exigir login
    assert client.get("/conta").status_code == 302

    from lodout.public_site import user_store
    assert user_store.get_user("76561198000000000") is None


def test_excluir_nao_afeta_outra_conta(client, monkeypatch):
    _login(client, monkeypatch, steamid="111")
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "ItemDoUm", "cost": "1", "quantity": "1",
        "csrf_token": token,
    })
    client.get("/logout")

    _login(client, monkeypatch, steamid="222")
    token2 = _csrf_token(client)
    client.post("/conta/excluir", data={"csrf_token": token2})

    from lodout.public_site import user_portfolio
    assert [p["name"] for p in user_portfolio.load_positions("111")] == (
        ["ItemDoUm"])


# ── pagina de privacidade ────────────────────────────────────

def test_privacidade_acessivel_sem_login(client):
    resp = client.get("/privacidade")
    assert resp.status_code == 200
    assert "SteamID64".encode("utf-8") in resp.data


def test_privacidade_linkada_no_rodape(client):
    pagina = client.get("/").data.decode("utf-8")
    assert "/privacidade" in pagina


# ── Lote 10: exportar dados (LGPD) + limpeza de avatar na exclusão ──

def test_exportar_dados_sem_login_redireciona(client):
    resp = client.get("/conta/exportar")
    assert resp.status_code == 302


def test_exportar_dados_com_login_devolve_json(client, monkeypatch):
    _login(client, monkeypatch, steamid="76561198000000001")
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline", "cost": "100", "quantity": "2",
        "csrf_token": token,
    })
    resp = client.get("/conta/exportar")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["usuario"]["steamid"] == "76561198000000001"
    assert len(data["portfolio"]) == 1
    assert data["portfolio"][0]["name"] == "AK-47 | Redline"
    assert "attachment" in resp.headers.get("Content-Disposition", "")


def test_excluir_apaga_avatar_em_cache(client, monkeypatch, tmp_path):
    from lodout.public_site import profile_fetcher
    monkeypatch.setattr(profile_fetcher, "_PROFILES_PATH", tmp_path / "perfis.json")
    monkeypatch.setattr(profile_fetcher, "_AVATARS_DIR", tmp_path / "avatars")
    steamid = "76561198000000002"
    profile_fetcher._AVATARS_DIR.mkdir(parents=True, exist_ok=True)
    avatar_path = profile_fetcher._AVATARS_DIR / f"{steamid}.jpg"
    avatar_path.write_bytes(b"fake-jpeg")
    profile_fetcher._save_cache({steamid: {"name": "Fulano"}})

    _login(client, monkeypatch, steamid=steamid)
    token = _csrf_token(client)
    client.post("/conta/excluir", data={"csrf_token": token})

    assert not avatar_path.exists()
    assert steamid not in profile_fetcher._load_cache()


def test_conta_mostra_preco_para_empatar_e_para_a_meta(client, monkeypatch):
    # 2026-11-15: pagou R$ 100 -> vender por R$ 115,00 empata (taxa de
    # 15% da Steam) e por R$ 138,00 lucra 20% (meta padrão).
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline (Field-Tested)", "cost": "100",
        "quantity": "1", "csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    # Preços clicáveis: copiam o número para colar na Steam (2026-11-15).
    assert '<span data-campo="empate">R$ 115,00</span>' in pagina
    assert '<span data-campo="alvo">R$ 138,00</span>' in pagina
    assert 'aria-label="Copiar R$ 138,00, preço para lucrar 20% em AK-47 | Redline (Testada em Campo)"' in pagina
    assert "Lucrar 20%" in pagina

    resp = client.post("/conta/meta", data={"meta": "50", "csrf_token": token})
    assert resp.status_code == 302
    pagina = client.get("/conta").data.decode("utf-8")
    assert '<span data-campo="alvo">R$ 172,50</span>' in pagina
    assert '<option value="50" selected>50%</option>' in pagina


def test_meta_de_lucro_invalida_e_recusada(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline (Field-Tested)", "cost": "100",
        "quantity": "1", "csrf_token": token})
    for valor in ("0", "-5", "abc", "9999"):
        client.post("/conta/meta", data={"meta": valor, "csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Lucrar 20%" in pagina


def test_meta_de_lucro_exige_csrf(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.post("/conta/meta", data={"meta": "50"})
    assert resp.status_code in (400, 403)



def test_salvar_quanto_paguei_sem_recarregar_devolve_a_linha(client, monkeypatch):
    # conta-inventario.md, fase 3: o script da conta pede JSON e atualiza
    # só a linha; vírgula decimal (teclado brasileiro) também vale.
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "Caixa X", "cost": "", "quantity": "1", "csrf_token": token})
    resp = client.post("/conta/posicoes/Caixa X/custo",
                       data={"cost": "100,00", "csrf_token": token},
                       headers={"Accept": "application/json"})
    assert resp.status_code == 200
    dados = resp.get_json()
    assert dados["ok"] is True
    assert dados["empate_fmt"] == "R$ 115,00"
    assert dados["alvo_fmt"] == "R$ 138,00"
    # Os cartões do topo atualizam juntos (polimento, 2026-11-15).
    assert dados["totais"]["pago"] == "R$ 100,00"
    assert dados["totais"]["pago_sub"] == "em 1 de 1 item"
    assert dados["totais"]["aviso_sem_custo"] == ""

    resp = client.post("/conta/posicoes/Caixa X/custo",
                       data={"cost": "-1", "csrf_token": token},
                       headers={"Accept": "application/json"})
    assert resp.status_code == 400 and resp.get_json()["ok"] is False


def test_salvar_quanto_paguei_sem_csrf_e_recusado(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.post("/conta/posicoes/Caixa X/custo", data={"cost": "1"},
                       headers={"Accept": "application/json"})
    assert resp.status_code in (400, 403)


def test_conta_carrega_o_script_de_salvar_rapido(client, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/conta").data.decode("utf-8")
    assert 'src="/static/conta.js' in pagina


def test_conta_separa_o_desgaste_do_nome(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "AK-47 | Redline (Field-Tested)", "cost": "",
        "quantity": "1", "csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    assert ">AK-47 | Redline</a>" in pagina
    assert '<span class="item-exterior">Testada em Campo</span>' in pagina
    # Cartão "Sem valor pago" (no lugar da faixa amarela, crítica de 15/11).
    assert 'data-total="falta_texto">1 item<' in pagina
    assert "informe o valor pago para ver" in pagina
    # Revisão de 16/11: cartão de lucro sem o destaque laranja, campo
    # vazio pergunta "quanto?" em vez de "0,00" (parecia um valor pago).
    assert 'class="card card-nota-destaque"' not in pagina
    assert 'placeholder="quanto?"' in pagina
    assert 'placeholder="0,00"' not in pagina
    # Revisão de 16/11 (32/40): com itens, o celular esconde a frase do
    # topo (classe no cabeçalho); "cada" fica junto do preço.
    assert 'cabecalho-pagina cabecalho-conta-com-itens' in pagina
    # Falha ao salvar com login expirado: conta.js mostra "Entrar de novo".
    assert 'data-login-url="/login"' in pagina
    assert 'class="conta-identidade-frase">seus itens da Steam' in pagina


def test_liquido_diz_que_e_depois_da_taxa():
    from lodout.public_site import account
    tx = account._textos_totais({"positions": 2, "known_cost": 0, "unknown_cost": 2,
                                 "net_if_sold": 86.96, "market_value": 100.0})
    # "sem a taxa" dava para ler como "sem contar a taxa" (o bruto).
    assert tx["liquido_sub"] == "você recebe R$\u00a086,96 depois da taxa"


def test_adicionar_a_mao_aceita_virgula(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "Caixa Y", "cost": "35,10", "quantity": "1", "csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    assert 'value="35,10"' in pagina


def test_conta_mostra_lucro_em_porcentagem(client, monkeypatch):
    from lodout.public_site import account
    assert account._pct_curto(-88.4) == "\u221288%"
    assert account._pct_curto(12.5) == "+12%"
    assert account._pct_curto(0.2) == "0%"



def test_conta_item_a_mao_pega_imagem_do_catalogo_e_conta_vazia(client, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/conta").data.decode("utf-8")
    assert 'class="conta-vazia"' in pagina and "Privacidade" in pagina
    from lodout.public_site import catalogo
    conn = catalogo.conectar()
    catalogo.gravar(conn, "Rifles", [{"hash_name": "Caixa M", "price": 1.0, "listings": 5,
                                      "name_color": "4b69ff", "icon": "hash-m"}])
    conn.close()
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={"name": "Caixa M", "cost": "", "quantity": "1",
                                         "csrf_token": token})
    pagina = client.get("/conta").data.decode("utf-8")
    assert "hash-m" in pagina
    assert 'enterkeyhint="next"' in pagina


def test_apagar_valor_pago_e_baixar_planilha(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={
        "name": "=Caixa X", "cost": "10", "quantity": "2", "csrf_token": token})
    # Apagar: limpar=1 com o campo vazio tira o valor pago.
    r = client.post("/conta/posicoes/=Caixa X/custo",
                    data={"cost": "", "limpar": "1", "csrf_token": token},
                    headers={"Accept": "application/json"})
    assert r.get_json()["ok"] is True and r.get_json()["empate_fmt"] is None
    # Campo vazio sem limpar=1 não mexe em nada (comportamento de antes).
    client.post("/conta/posicoes/=Caixa X/custo",
                data={"cost": "12,50", "csrf_token": token})
    client.post("/conta/posicoes/=Caixa X/custo",
                data={"cost": "", "csrf_token": token})
    r = client.get("/conta/tabela.csv")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("text/csv")
    assert "attachment" in r.headers["Content-Disposition"]
    texto = r.data.decode("utf-8")
    assert texto.startswith("﻿Item;Nome na Steam;Quantidade")
    linha = texto.splitlines()[1].split(";")
    # Nome que começa com "=" não vira fórmula na planilha.
    assert linha[0] == "'=Caixa X"
    assert linha[2] == "2" and linha[4] == "12,50"
    # Venda sem prejuízo: 12,50 × 1,15 = 14,38 (aprox.)
    assert linha[9].startswith("14,3")


def test_planilha_exige_login(client):
    assert client.get("/conta/tabela.csv").status_code in (302, 401)


def test_ler_reais_aceita_formatos_brasileiros():
    from lodout.public_site import fmt
    assert fmt.ler_reais("35,10") == 35.10
    assert fmt.ler_reais("35.10") == 35.10
    assert fmt.ler_reais("R$ 1.234,56") == 1234.56
    assert fmt.ler_reais("R$ 12,00") == 12.0
    import pytest as _pt
    with _pt.raises(ValueError):
        fmt.ler_reais("abc")


def test_confira_valor_fora_do_comum():
    from lodout.public_site import account
    assert account._confira(3.0, 33.0) == "confira: bem abaixo do preço"
    assert account._confira(500.0, 33.0) == "confira: bem acima do preço"
    assert account._confira(30.0, 33.0) == ""
    assert account._confira(None, 33.0) == ""


def test_meta_de_lucro_responde_json(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    r = client.post("/conta/meta", data={"meta": "30", "csrf_token": token},
                    headers={"Accept": "application/json"})
    assert r.get_json() == {"ok": True, "meta": 30}


def test_atualizar_inventario_a_pedido_com_intervalo(client, monkeypatch):
    from lodout.public_site import inventario, user_store
    from lodout import steam_api
    disparos = []
    monkeypatch.setattr(inventario, "sincronizar_em_segundo_plano",
                        lambda sid: disparos.append(sid))
    _login(client, monkeypatch)
    token = _csrf_token(client)
    sid = "76561198000000000"
    disparos.clear()  # o próprio login já sincroniza
    # Atualizado há pouco: não busca de novo.
    user_store.save_user_json(sid, "inventario_sync", {"status": "ok", "ts": time.time()})
    client.post("/conta/inventario/atualizar", data={"csrf_token": token})
    assert disparos == []
    # Há mais de 5 min e sem pausa da Steam: busca.
    user_store.save_user_json(sid, "inventario_sync", {"status": "ok", "ts": time.time() - 600})
    client.post("/conta/inventario/atualizar", data={"csrf_token": token})
    assert disparos == [sid]
    # Steam pediu pausa: não busca.
    monkeypatch.setattr(steam_api, "em_cooldown", lambda familia: True)
    client.post("/conta/inventario/atualizar", data={"csrf_token": token})
    assert disparos == [sid]
    # Sem CSRF: recusado.
    assert client.post("/conta/inventario/atualizar").status_code in (400, 403)


def test_item_mostra_na_sua_conta_so_para_quem_tem(client, monkeypatch):
    from lodout.public_site import catalogo
    conn = catalogo.conectar()
    catalogo.gravar(conn, "Rifles", [{"hash_name": "Caixa N", "price": 10.0, "listings": 5,
                                      "name_color": "4b69ff", "icon": "hash-n"}])
    conn.close()
    # Sem login: sem o bloco.
    pagina = client.get("/item/Caixa N")
    assert pagina.status_code == 200 and "Na sua conta" not in pagina.data.decode("utf-8")
    _login(client, monkeypatch)
    token = _csrf_token(client)
    client.post("/conta/posicoes", data={"name": "Caixa N", "cost": "8", "quantity": "3",
                                         "csrf_token": token})
    r = client.get("/item/Caixa N")
    corpo = r.data.decode("utf-8")
    assert "Na sua conta" in corpo and "Você tem <strong>3</strong> unidades" in corpo
    assert "R$ 9,20" in corpo  # 8 × 1,15
    assert r.headers["Cache-Control"] == "private, no-store"


def test_mudanca_desde_a_visita_anterior():
    from lodout.public_site import account
    assert account._mudanca_desde_ultima_visita([{"ts": 1, "total": 100.0}]) is None
    m = account._mudanca_desde_ultima_visita([{"ts": 1, "total": 100.0}, {"ts": 2, "total": 103.2}])
    assert m["texto"] == "+R$ 3,20" and m["classe"] == "valor-positivo"
    m = account._mudanca_desde_ultima_visita([{"ts": 1, "total": 100.0}, {"ts": 2, "total": 90.0}])
    assert m["texto"] == "−R$ 10,00"
    # Visita com a conta vazia (R$ 0) não serve de base: era o "+ o valor
    # inteiro desde a última vez" do print de 15/11.
    assert account._mudanca_desde_ultima_visita([{"ts": 1, "total": 0.0}, {"ts": 2, "total": 197.43}]) is None


def test_lucro_diz_de_quantos_itens_e():
    # Crítica de 15/11 (P1): "−50%" era só de parte da carteira.
    from lodout.public_site import account
    t = {"positions": 17, "known_cost": 9, "unknown_cost": 8, "pnl": -55.46,
         "pnl_pct": -50.3, "market": 1118.11, "net_if_sold": 972.27,
         "cost_known": 130.49, "market_sem_custo": 1050.0}
    tx = account._textos_totais(t)
    assert tx["lucro_sub"] == "−50,3% · só dos 9 itens com valor pago"
    assert tx["falta_texto"] == "8 itens" and tx["falta_sub"] == "valem R$ 1.050,00 hoje"
    t.update(unknown_cost=0, known_cost=17, market_sem_custo=0)
    assert account._textos_totais(t)["lucro_sub"] == "−50,3% do que você pagou"
    assert account._textos_totais(t)["falta_texto"] == ""


def test_lista_longa_tem_ferramentas_e_botao_de_voltar_a_busca(client, monkeypatch):
    """Com 8+ itens a conta ganha busca/filtros e, no celular, o botão
    "Buscar" que volta até eles depois de rolar (revisão de 16/11)."""
    from lodout.public_site import user_portfolio
    _login(client, monkeypatch)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "data-ir-busca" not in pagina
    for i in range(8):
        user_portfolio.add_position("76561198000000000", f"Caixa {i}", 1.0)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "data-conta-ferramentas" in pagina
    assert 'data-ir-busca hidden' in pagina


def test_idade_dos_precos_visivel_na_lista():
    """Revisão de 16/11: a idade do preço só aparecia passando o mouse."""
    import time
    from lodout.public_site import account
    agora = time.time()
    assert account._idade_dos_precos([]) is None
    assert account._idade_dos_precos([agora - 7200, agora - 7300]) == "Preços coletados há 2 h."
    assert account._idade_dos_precos([agora - 7200, agora - 72000]) == "Preços coletados há até 20 h."
