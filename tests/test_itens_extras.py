"""Itens a mais com nota, escolhidos do catálogo (2026-11-16)."""
from __future__ import annotations

from lodout.public_site import catalogo, itens_extras


def _catalogo(itens):
    conn = catalogo.conectar()
    for fatia, lista in itens.items():
        catalogo.gravar(conn, fatia, lista)
    conn.close()


def _item(nome, preco, listings):
    return {"hash_name": nome, "price": preco, "listings": listings,
            "name_color": "4b69ff", "icon": "x"}


def test_escolhe_os_mais_anunciados_sem_adesivo_sem_os_que_ja_estao(monkeypatch):
    itens_extras._caminho().unlink(missing_ok=True)
    monkeypatch.setenv("LODOUT_ITENS_EXTRAS", "2")
    _catalogo({
        "Rifles": [_item("AK-47 | Muito (Field-Tested)", 5.0, 900),
                   _item("AK-47 | Ja Esta (Field-Tested)", 5.0, 950),
                   _item("AK-47 | Barato (Field-Tested)", 0.5, 990),
                   _item("AK-47 | Pouco (Field-Tested)", 5.0, 10)],
        "Pistolas": [_item("Glock-18 | Medio (Field-Tested)", 3.0, 500)],
        "Adesivos": [_item("Sticker | Popular", 9.0, 5000)],
    })
    r = itens_extras.alvos({"AK-47 | Ja Esta (Field-Tested)"}, agora=1000.0)
    nomes = [n for lista in r.values() for n in lista]
    # Os 2 mais anunciados que sobram: sem adesivo, sem o barato (< R$ 1
    # com a cotação fixa 1,0 dos testes) e sem o que já está na coleta.
    assert nomes == ["AK-47 | Muito (Field-Tested)", "Glock-18 | Medio (Field-Tested)"]
    assert set(r) == {"Rifles", "Pistolas"}


def test_lista_dura_um_dia_e_mantem_quem_ja_estava(monkeypatch):
    itens_extras._caminho().unlink(missing_ok=True)
    monkeypatch.setenv("LODOUT_ITENS_EXTRAS", "1")
    _catalogo({"Rifles": [_item("A | Um (Field-Tested)", 5.0, 900),
                          _item("A | Dois (Field-Tested)", 5.0, 800)]})
    assert itens_extras.alvos(set(), agora=1000.0) == {"Rifles": ["A | Um (Field-Tested)"]}
    # No dia seguinte "Dois" passou "Um", mas "Um" segue entre os 2n
    # mais anunciados: fica (continuidade da nota).
    _catalogo({"Rifles": [_item("A | Um (Field-Tested)", 5.0, 700),
                          _item("A | Dois (Field-Tested)", 5.0, 990)]})
    assert itens_extras.alvos(set(), agora=1000.0 + 25 * 3600) == {"Rifles": ["A | Um (Field-Tested)"]}


def test_desligado_ou_sem_catalogo(monkeypatch):
    itens_extras._caminho().unlink(missing_ok=True)
    monkeypatch.setenv("LODOUT_ITENS_EXTRAS", "0")
    assert itens_extras.alvos(set()) == {}


def test_baratos_no_topo_nao_tomam_o_lugar_dos_que_valem(monkeypatch):
    """1º ciclo real (16/11): os mais anunciados são quase todos de
    centavos; com o piso aplicado depois do corte, vieram 46 de 100."""
    itens_extras._caminho().unlink(missing_ok=True)
    monkeypatch.setenv("LODOUT_ITENS_EXTRAS", "3")
    baratos = [_item(f"P250 | Barato {i} (Battle-Scarred)", 0.05, 9000 - i)
               for i in range(100)]
    caros = [_item(f"AK-47 | Caro {i} (Field-Tested)", 5.0, 100 - i)
             for i in range(3)]
    _catalogo({"Rifles": caros, "Pistolas": baratos})
    r = itens_extras.alvos(set(), agora=1000.0)
    assert r == {"Rifles": [f"AK-47 | Caro {i} (Field-Tested)" for i in range(3)]}


def test_lista_salva_com_criterio_antigo_e_refeita(monkeypatch):
    import json
    from lodout import _paths
    monkeypatch.setenv("LODOUT_ITENS_EXTRAS", "1")
    _paths.atomic_write_text(itens_extras._caminho(), json.dumps(
        {"ts": 1000.0, "quantidade": 1,
         "itens": [{"nome": "Velho | Sem Criterio", "categoria": "Rifles"}]}))
    _catalogo({"Rifles": [_item("A | Novo (Field-Tested)", 5.0, 900)]})
    assert itens_extras.alvos(set(), agora=1100.0) == {"Rifles": ["A | Novo (Field-Tested)"]}
