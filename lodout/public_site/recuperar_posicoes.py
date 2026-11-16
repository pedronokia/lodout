"""Devolve valores pagos apagados pela sincronização do inventário.

Até 16/11, item que saía do inventário público da Steam era apagado da
conta junto com o valor pago -- e anunciar no Mercado também tira o item
de lá. Este comando procura nos backups diários do banco
(`data/backups/public_site-*.db`, guardados por 7 dias) os itens de uma
conta que tinham valor pago e hoje não têm, e os devolve.

Uso, no servidor (dentro do container `web`):

    python -m lodout.public_site.recuperar_posicoes STEAMID
    python -m lodout.public_site.recuperar_posicoes STEAMID --aplicar
    python -m lodout.public_site.recuperar_posicoes --todos [--aplicar]

`--todos` confere todas as contas que aparecem nos backups.

Sem `--aplicar`, só mostra o que faria. Com `--aplicar`, guarda antes uma
cópia das posições atuais em `data/backups/` e então grava.

- Item que não está mais na conta: volta com o valor pago, marcado como
  fora do inventário; se ele estiver no inventário (anúncio cancelado),
  a próxima sincronização tira a marca.
- Item que está na conta sem valor pago (voltou do anúncio sem o valor):
  recebe o valor do backup, se for uma linha só dos dois lados; senão,
  aparece na lista para conferir à mão.

Itens que a pessoa vendeu ("Vendi"), removeu de propósito ou dispensou
no quadro da conta ("Não quero de volta") ficam numa lista de ignorados
(`preferencias` -> `recuperar_ignorar`) e não voltam, nem por aqui.

Os backups são abertos só para leitura.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

from lodout import _paths
from lodout.public_site import user_portfolio, user_store


def _backups() -> "list[Path]":
    pasta = Path(_paths.DATA_DIR) / "backups"
    return sorted(pasta.glob("public_site-*.db"), reverse=True) if pasta.exists() else []


def _posicoes_do_backup(arquivo: Path, steamid: str) -> "list[dict]":
    conn = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
    try:
        linha = conn.execute(
            "SELECT payload FROM user_data WHERE steamid = ? AND kind = 'portfolio'",
            (steamid,)).fetchone()
    except sqlite3.Error:
        return []
    finally:
        conn.close()
    try:
        dados = json.loads(linha[0]) if linha else []
    except ValueError:
        return []
    return dados if isinstance(dados, list) else []


_CHAVE_IGNORAR = "recuperar_ignorar"


def ignorados(steamid: str) -> "set[str]":
    """Itens que não devem voltar: vendidos ("Vendi"), removidos de
    propósito ou dispensados no quadro (revisão 16/11: o quadro oferecia
    de volta um item que a pessoa tinha acabado de vender)."""
    prefs = user_store.load_user_json(steamid, "preferencias", {}) or {}
    lista = prefs.get(_CHAVE_IGNORAR) if isinstance(prefs, dict) else None
    return {n for n in lista if isinstance(n, str)} if isinstance(lista, list) else set()


def _gravar_ignorados(steamid: str, nomes: "set[str]") -> None:
    prefs = user_store.load_user_json(steamid, "preferencias", {}) or {}
    if not isinstance(prefs, dict):
        prefs = {}
    prefs[_CHAVE_IGNORAR] = sorted(nomes)
    user_store.save_user_json(steamid, "preferencias", prefs)
    _CACHE_PREVIA.pop(steamid, None)


def ignorar(steamid: str, nomes) -> None:
    novos = {n for n in nomes if n}
    atuais = ignorados(steamid)
    if not novos <= atuais:
        _gravar_ignorados(steamid, atuais | novos)


def deixar_de_ignorar(steamid: str, nome: str) -> None:
    atuais = ignorados(steamid)
    if nome in atuais:
        _gravar_ignorados(steamid, atuais - {nome})


def planejar(steamid: str, atuais: "list[dict]", backups: "list[Path]",
             agora: float, ignorar: "set[str] | frozenset" = frozenset()
             ) -> "tuple[list[dict], list[dict]]":
    """(posições novas, relatório). Para cada item, usa o backup mais
    recente em que ele tinha valor pago. Itens em `ignorar` ficam de fora."""
    com_valor_hoje = {p.get("name") for p in atuais if p.get("cost") is not None}
    por_nome_hoje: dict = {}
    for p in atuais:
        por_nome_hoje.setdefault(p.get("name"), []).append(p)
    resolvidos: set = set(ignorar)
    novas = [dict(p) for p in atuais]
    relatorio: list = []
    for arquivo in backups:
        lotes_backup: dict = {}
        for p in _posicoes_do_backup(arquivo, steamid):
            if isinstance(p, dict) and p.get("cost") is not None and p.get("name"):
                lotes_backup.setdefault(p["name"], []).append(p)
        for nome, lotes in lotes_backup.items():
            if nome in resolvidos or nome in com_valor_hoje:
                continue
            resolvidos.add(nome)
            hoje = por_nome_hoje.get(nome, [])
            base = {"item": nome, "backup": arquivo.name,
                    "valores": [(int(l.get("quantity") or 1), l["cost"]) for l in lotes]}
            if not hoje:
                for l in lotes:
                    novas.append({**l, "source": l.get("source") or "steam",
                                  "fora_desde": agora})
                relatorio.append({**base, "acao": "volta (fora do inventário)"})
            elif len(hoje) == 1 and len(lotes) == 1:
                for p in novas:
                    if p.get("name") == nome:
                        p["cost"] = lotes[0]["cost"]
                relatorio.append({**base, "acao": "recebe o valor pago"})
            else:
                relatorio.append({**base, "acao": "conferir à mão (lotes diferentes)"})
    return novas, relatorio


_CACHE_PREVIA: dict = {}
_PREVIA_TTL_S = 600


def previa(steamid: str, atuais: "list[dict]", agora: "float | None" = None) -> dict:
    """O que voltaria para esta conta, sem gravar nada: {"voltam": [...],
    "conferir": [...]}, cada um com item e valores [(qtd, custo)]. Usado
    pela página da conta para mostrar o quadro só a quem perdeu algo
    (revisão 16/11). Guarda o resultado 10 min por conta (os backups só
    mudam 1x por dia; a lista da pessoa entra na chave)."""
    agora = time.time() if agora is None else agora
    backups = _backups()
    fora = ignorados(steamid)
    chave = (json.dumps(atuais, sort_keys=True, ensure_ascii=False),
             tuple(b.name for b in backups), tuple(sorted(fora)))
    guardado = _CACHE_PREVIA.get(steamid)
    if guardado and guardado[1] == chave and agora - guardado[0] < _PREVIA_TTL_S:
        return guardado[2]
    _novas, relatorio = planejar(steamid, atuais, backups, agora, ignorar=fora)
    out = {"voltam": [r for r in relatorio if not r["acao"].startswith("conferir")],
           "conferir": [r for r in relatorio if r["acao"].startswith("conferir")]}
    _CACHE_PREVIA[steamid] = (agora, chave, out)
    return out


def _contas_nos_backups(backups: "list[Path]") -> "list[str]":
    contas: set = set()
    for arquivo in backups:
        conn = sqlite3.connect(f"file:{arquivo}?mode=ro", uri=True)
        try:
            contas.update(r[0] for r in conn.execute(
                "SELECT steamid FROM user_data WHERE kind = 'portfolio'"))
        except sqlite3.Error:
            pass
        finally:
            conn.close()
    return sorted(contas)


def _recuperar(steamid: str, backups: "list[Path]", aplicar: bool, agora: float) -> int:
    atuais = user_portfolio.load_positions(steamid)
    novas, relatorio = planejar(steamid, atuais, backups, agora,
                                ignorar=ignorados(steamid))
    if not relatorio:
        return 0
    print(f"\nConta {steamid}:")
    for r in relatorio:
        valores = ", ".join(f"{q}x R$ {c:.2f}".replace(".", ",") for q, c in r["valores"])
        print(f"- {r['item']}: {valores} -> {r['acao']} (de {r['backup']})")
    if aplicar:
        copia = Path(_paths.DATA_DIR) / "backups" / time.strftime(
            f"recuperacao-{steamid}-%Y%m%d-%H%M%S.json", time.gmtime(agora))
        _paths.atomic_write_text(copia, json.dumps(atuais, ensure_ascii=False))
        user_store.save_user_json(steamid, "portfolio", novas)
        print(f"  Gravado. Cópia do estado anterior: {copia}")
    return len(relatorio)


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("steamid", nargs="?")
    ap.add_argument("--todos", action="store_true",
                    help="confere todas as contas que aparecem nos backups")
    ap.add_argument("--aplicar", action="store_true",
                    help="grava (sem isto, só mostra o que faria)")
    args = ap.parse_args(argv)
    if bool(args.steamid) == bool(args.todos):
        ap.error("informe um STEAMID ou --todos")
    backups = _backups()
    if not backups:
        print("Nenhum backup em", Path(_paths.DATA_DIR) / "backups")
        return 1
    print(f"Backups lidos: {len(backups)} (mais novo: {backups[0].name})")
    contas = _contas_nos_backups(backups) if args.todos else [args.steamid]
    agora = time.time()
    achados = sum(_recuperar(sid, backups, args.aplicar, agora) for sid in contas)
    if not achados:
        print("Nada a recuperar: nenhum item com valor pago nos backups falta hoje.")
    elif not args.aplicar:
        print("\nNada foi gravado. Para gravar, rode de novo com --aplicar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
