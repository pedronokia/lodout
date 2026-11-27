# Plano de aprimoramento das buscas — 26/11/2026

Plano priorizado gerado por análise somente leitura dos dois sistemas:

1. **Busca do Mercado/catálogo** — `lodout/steam_api.py`, `lodout/public_site/catalogo.py`, `lodout/discovery.py`.
2. **Busca do visitante** — `/?q=` e `/api/sugestoes` em `lodout/public_site/server.py`, `texto_busca`/`nome_para_busca` em `catalogo.py`.

Status atualizado pelo Agente de Aprimoramento em `scratch/aprimoramentos/aplicados/`.

Legenda de autorização (decisão do usuário em 26/11):

- **AUTORIZADO** — o Agente de Aprimoramento pode aplicar sozinho, com testes, commit, CI/deploy e verificação no ar.
- **LIBERADO EM 26/11** — itens de ritmo/limite/cobertura que antes eram vetados; o usuário autorizou “Vamos lá”. Continuam fora: `LODOUT_ITENS_EXTRAS`, o valor base de `steam_api.RATE_LIMIT_DELAY_S`, config/deploy, segredos, `data/` e chamadas diagnósticas à Steam.

## Achados

| # | Item | Evidência | Impacto | Correção | Autorização |
|---|---|---|---|---|---|
| 1 | `/api/sugestoes` não entende `OR` | `server.py:1017-1024` exige todas as palavras; home usa `split(" or ")` em `server.py:1699-1717` | `?q=redline or asiimov` sugere só pelo catálogo, não pelos itens com nota | **APLICADO** em 27/11: `_busca_bate` reusado no braço do scan | Aplicado |
| 2 | Ordem e teto de 8 escondem nome exato do catálogo | `server.py:1021-1043`; `catalogo.py:633-636` ordena por `a_venda` | 8 itens com nota impedem o nome exato do catálogo de aparecer | **APLICADO** em 27/11: fontes mescladas, dedupadas e ordenadas por exato/prefixo (`relevancia_busca` + `ordenar="relevancia"`) | Aplicado |
| 3 | Página curta (throttle silencioso) sem diagnóstico | `catalogo.py:504-510` só conta vazia; `:519-522` aceita qualquer `len` | Rodada pode fechar “completa” com cobertura parcial | **APLICADO** em 27/11: `paginas_curta`/`paginas_curta_rodada`/`paginas_curta_seguidas` em `resumo()` e pausa (`motivo="pagina_curta"`) após 3 seguidas | Aplicado |
| 4 | Corpo do 404 some no restart | `steam_api.py:637-642` só logava; `catalogo.py` agora grava `detalhe_404` | Depois do restart só a posição da falha sobrevivia | **APLICADO** em `f09db22`: `ultimo_404_busca()` + `detalhe_404` no estado | Aplicado |
| 5 | Sem backoff para 404/página curta | `catalogo.py:250`, `:528-529` | 3 tentativas em ~20 s no mesmo `start` | **APLICADO** em 27/11: `_pausa_entre_paginas` escalona até 4× em 404/página curta (sem mudar `RATE_LIMIT_DELAY_S`) + freio após 3 fatias seguidas com 404 em `start=0` (`freio_404_start0`) | Aplicado |
| 6 | Ordenação por nome assumida estável | `catalogo.py:246,444,514-526` | Itens pulados em silêncio se a ordem da Steam mudar | **APLICADO** em 27/11: `ordem_instavel`/`ordem_instavel_rodada` medidos pela sobreposição entre páginas consecutivas e expostos em `resumo()` | Aplicado |
| 7 | `search_market_all` trunca em silêncio | `steam_api.py:544,659-690`; `discovery.py:122-137` | `max_items=500` devolve ~400 com status `ok` e é cacheado como completo | **APLICADO** em 27/11: `SEARCH_TRUNCATED` + log em `search_market_all`, `_SEARCH_MAX_PAGES=50`, `discovery.py` não cacheia resultado truncado | Aplicado |
| 8 | Preço ausente vira item invisível | `steam_api.py:591-597,1363-1372`; `catalogo.py:192-197,612` | Item entra no scanner mas não aparece em busca/sugestões/contagens | **APLICADO** em 27/11: `_parse_usd` para `sell_price_text` em dólar (não usa `parse_brl`) e descarte de `price is None` em `discovery.py` | Aplicado |
| 9 | Sem total por fatia quando ela falha | `steam_api.py:642`; `catalogo.py:503`, `_retomar_legado` | Sem `fatias_puladas` antigo, não há como inferir o `start` de retomada | **APLICADO** em `f09db22`: `total` em `pulada` e preservação em `totais` | Aplicado |
| 10 | Sinônimo “faca” não cobre Karambit/Bayonet | `catalogo.py:76-83,89-90`; `localization.py:34-40` | “faca karambit” não encontra itens que não têm “Knife” no nome | **APLICADO** em 27/11: sinônimos por família em `SINONIMOS_BUSCA` + `_PALAVRA_CATEGORIA` para linhas já gravadas | Aplicado |
| 11 | Coringas de `LIKE` não escapados | `catalogo.py:596-600` | `?q=ak%` casa qualquer sufixo e empurra o nome exato fora do top 8 | **APLICADO** em 27/11: `_escapar_like` + `LIKE ... ESCAPE '\'` | Aplicado |
| 12 | Descoberta falha em silêncio / cache corrompido | `discovery.py:60-64,110-112,126-135,151-160` | Não dá para saber se foi 404, 429 ou cache inválido; JSON corrompido tratado como vazio | **APLICADO** em 27/11: logs estruturados em `discovery.py`/`steam_api.py`, `load_json_record` com quarentena, caminho resolvido dinamicamente e limpeza de expirados | Aplicado |

## Regras de aplicação

- Um item por execução; marcar aplicado em `scratch/aprimoramentos/aplicados/<slug>.md`.
- `git fetch origin main && git merge origin/main` e suíte completa **depois do merge**.
- Commit novo, nunca `amend`/force-push; `[restart-worker]` se `worker.py`, `scan_engine.py`, `steam_api.py` ou `catalogo.py` mudarem.
- Acompanhar `tests` e `deploy` até o fim e confirmar `/api/health` no ar.
- Nenhuma chamada diagnóstica à Steam; nenhuma mudança de `data/`, segredos, config/deploy, `LODOUT_ITENS_EXTRAS` ou do valor base de `RATE_LIMIT_DELAY_S`.
- Itens de ritmo/limite liberados em 26/11 devem ser aplicados com cautela: registrar em `/api/health` o efeito medido (pausas 429, páginas, cobertura) antes de ampliar novamente.
