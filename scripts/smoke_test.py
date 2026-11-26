"""Smoke test pós-deploy: confirma que as rotas principais do site
público respondem com o status esperado.

Não substitui a suíte de testes (que roda contra o código, sem rede) --
isto é contra o site de VERDADE, depois de um deploy, pra pegar erro de
config/infra que só aparece em produção (env var faltando, Caddy mal
configurado, etc.).

Uso:
    python scripts/smoke_test.py https://seudominio.com
"""
from __future__ import annotations

import sys
from urllib.parse import urlparse

import httpx

# (caminho, status esperado)
_ROTAS: list[tuple[str, int]] = [
    ("/healthz", 200),
    ("/readyz", 200),
    ("/", 200),
    ("/sobre", 200),
    ("/metodo", 200),
    ("/faq", 200),
    ("/glossario", 200),
    ("/como-usar", 200),
    ("/changelog", 200),
    ("/novidades", 200),
    ("/comparar", 200),
    ("/opensearch.xml", 200),
    ("/status", 200),
    ("/ranking", 200),
    ("/privacidade", 200),
    ("/api/recommendations", 200),
    ("/api/health", 200),
    ("/robots.txt", 200),
    ("/sitemap.xml", 200),
    ("/feed.xml", 200),
    ("/static/manifest.json", 200),
    ("/sw.js", 200),
    ("/pagina-que-nao-existe", 404),
]

# Rotas cujo corpo JSON precisa confirmar uma chave booleana verdadeira
# (evita falso positivo caso um proxy devolva HTML 200 no lugar da API).
_JSON_CHECKS: dict[str, str] = {
    "/healthz": "ok",
    "/readyz": "ready",
}


def _verificar_admin_protegido(client: httpx.Client, base: str) -> bool:
    """Confirma que `/admin` nunca abre sem sessão: devolve 404 (admin
    desligado) ou 302 redirecionando pra `/admin/login` (admin ligado)."""
    url = base + "/admin"
    try:
        resp = client.get(url, follow_redirects=False)
    except httpx.HTTPError as e:
        print(f"ERRO  /admin: {e}")
        return False

    if resp.status_code == 404:
        print("OK   /admin: 404 (desligado)")
        return True
    if resp.status_code in (301, 302, 303, 307, 308):
        destino = urlparse(resp.headers.get("location", "")).path
        if destino == "/admin/login":
            print(f"OK   /admin: {resp.status_code} -> /admin/login")
            return True
    print(f"FALHOU /admin: {resp.status_code} (esperado 404 ou redirect pra /admin/login)")
    return False


def verificar_site(base: str, client: "httpx.Client | None" = None) -> tuple[int, int]:
    """Executa o smoke test em `base` e retorna `(falhas, total)`."""
    base = base.rstrip("/")
    falhas = 0
    total = len(_ROTAS) + 1  # +1 para /admin

    def _rodar(c: httpx.Client) -> None:
        nonlocal falhas
        for caminho, esperado in _ROTAS:
            url = base + caminho
            try:
                resp = c.get(url, follow_redirects=True)
                ok = resp.status_code == esperado
                detalhe = ""
                if ok and caminho in _JSON_CHECKS:
                    chave = _JSON_CHECKS[caminho]
                    try:
                        dados = resp.json()
                    except ValueError:
                        dados = None
                    if not isinstance(dados, dict) or dados.get(chave) is not True:
                        ok = False
                        detalhe = f" (JSON sem {chave}=true)"
            except httpx.HTTPError as e:
                ok = False
                resp = None
                detalhe = ""
                print(f"ERRO  {caminho}: {e}")
            if resp is not None:
                marca = "OK  " if ok else "FALHOU"
                print(f"{marca} {caminho}: {resp.status_code} (esperado {esperado}){detalhe}")
            if not ok:
                falhas += 1

        if not _verificar_admin_protegido(c, base):
            falhas += 1

    if client is not None:
        _rodar(client)
    else:
        with httpx.Client(timeout=15.0) as c:
            _rodar(c)
    return falhas, total


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: python scripts/smoke_test.py https://seudominio.com")
        return 2
    falhas, total = verificar_site(argv[1])
    print(f"\n{total - falhas}/{total} rotas OK")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
