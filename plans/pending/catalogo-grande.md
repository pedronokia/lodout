# Catálogo grande: todas as skins, caixas e cápsulas com o preço do dia

Pedido: 2026-11-14 (conversa). O site acompanha 183 itens com nota; o
Mercado da Steam tem dezenas de milhares. Quem vem da Steam precisa achar
qualquer skin no Lodout. Este plano é o **passo 1**: catálogo amplo com
preço do dia, **sem nota** para os itens novos. A expansão da nota
(histórico) é um plano separado, depois deste.

## Como funciona (resumo)

- O worker passa a fazer, uma vez por dia e nas horas em que fica parado,
  uma **varredura do catálogo** pela busca da Steam
  (`/market/search/render`, 100 itens por consulta). Cada item traz nome,
  menor preço, quantidade à venda, imagem, raridade e tipo.
- Os itens vão para um banco SQLite próprio (`data/catalogo.sqlite3`),
  separado da coleta com nota.
- O site passa a buscar e filtrar no catálogo inteiro. Itens sem nota
  aparecem marcados "sem nota ainda" e ganham uma página simples.

## Fases

### Fase 1: varredura do catálogo no worker (o risco primeiro)
Verificado quando: uma varredura completa grava ≥ 90% do `total_count`
da Steam no SQLite, com 0 bloqueio que dispare o disjuntor, e a coleta com
nota (6 h) e as rodadas do Top 20 seguem no horário.
Arquivos: `lodout/steam_api.py`, `lodout/public_site/catalogo.py` (novo),
`lodout/public_site/worker.py`, `tests/test_catalogo.py` (novo).

#### Passo 1.1: ler imagem, raridade e tipo da busca da Steam (S)
- `_parse_search_results` passa a devolver também `icon`, `name_color`
  e `tipo` (o `type` da `asset_description`, ex. "Covert Rifle").
- Teste com resposta gravada da Steam (sem rede).
- Verificação: `python -m pytest -q tests/test_steam_api.py`
- Bloqueado por: nada.

#### Passo 1.2: banco do catálogo (S)
- `catalogo.py`: cria `data/catalogo.sqlite3` (caminho resolvido na
  chamada, não no default), tabela `itens` (nome de mercado, nome PT,
  texto de busca normalizado, preço, à venda, categoria, raridade,
  exterior, versão, imagem, atualizado_em) e índices; grava em lote
  dentro de transação; consultas com filtro + paginação (LIMIT/OFFSET).
- Categoria derivada do `tipo` da Steam para as mesmas abas do site.
- Verificação: `python -m pytest -q tests/test_catalogo.py`
- Bloqueado por: 1.1.

#### Passo 1.3: varredura no tempo livre do worker (M)
- Fatiada por tipo (rifles, pistolas, SMGs, escopetas, metralhadoras,
  facas, luvas, caixas/cápsulas e adesivos — o mercado de CS2 inteiro), paginando de 100 em 100 com
  `RATE_LIMIT_DELAY_S` lido na hora e o disjuntor `search`.
- Roda só entre as rodadas do Top 20, nunca junto da coleta com nota;
  para no primeiro 429 e continua de onde parou na próxima janela
  (posição salva com `atomic_write_text`). Catálogo completo a cada 6 h
  (~300 consultas por rodada, dentro das ~5 h livres do worker).
- Liga/desliga por variável de ambiente `LODOUT_CATALOGO` (padrão
  desligado; ligado no deploy desta fase). Resumo no `/api/health`
  (itens, páginas, 429, duração).
- Verificação: `python -m pytest -q tests/test_public_site.py -k catalogo`
  + leitura do `/api/health` depois da primeira varredura em produção.
- Bloqueado por: 1.2.

**Checkpoint:** só seguir para a Fase 2 com a primeira varredura completa
medida em produção (tempo, 429, tamanho real das páginas).

### Fase 2: o site lê o catálogo
Verificado quando: buscar "dragon lore" ou filtrar Exterior/Raridade acha
itens fora dos 183, com resposta da home abaixo de 400 ms no servidor
(Server-Timing) com o catálogo inteiro.
Arquivos: `lodout/public_site/server.py`, `templates/index.html`,
`templates/item.html`, `static/style.css`, `tests/test_public_site.py`.

#### Passo 2.1: busca e filtros sobre o catálogo (M)
- Home sem busca/filtro: igual a hoje (itens com nota).
- Com busca ou filtro: resultados do catálogo inteiro, itens com nota
  primeiro (por nota), depois os sem nota (pelos mais negociados).
- Mesma regra de busca de hoje (inglês/português, sem acento, qualquer
  ordem), feita no SQLite.
- Bloqueado por: Fase 1.

#### Passo 2.2: cartão e página do item sem nota (M)
- Cartão: imagem, nome, preço, "sem nota ainda" no lugar do anel, link
  para a Steam. Mesma altura/alinhamento dos cartões com nota.
- `/item/<nome>` para item só do catálogo: preço do dia, à venda,
  raridade, link Steam e o aviso "este item ainda não tem nota".
- Bloqueado por: 2.1.

### Fase 3: textos e verificação final (S)
- Status: data e tamanho da última varredura do catálogo.
- Método/Glossário: o que é "sem nota ainda". Mudanças: entrada nova.
- Testes, axe (desktop e celular), baselines, publicação.
- Bloqueado por: Fase 2.

## Decision log
| Decisão | Escolha | Por quê |
| --- | --- | --- |
| Fonte do catálogo | `/market/search/render` (100 itens/consulta) | Já existe no código, com disjuntor; 1 consulta traz 100 itens |
| Onde guardar | SQLite separado em `data/` | 20 mil itens num JSON lido a cada visita deixaria a home lenta |
| Quando roda | Tempo livre do worker, 1x por dia, fatiado | Não disputa com a coleta da nota; o worker é o único que fala com a Steam |
| Nota | Inalterada nesta etapa | A nota foi calibrada nos itens atuais; expandir é outro plano |
| Adesivos | Dentro do catálogo (usuário, 2026-11-14) | Pela busca da Steam custam ~90 consultas (+50%), não o triplo; são itens que somem do mercado ao serem colados/raspados |
| Itens sem nota na home | Só aparecem com busca ou filtro (usuário) | A home continua sendo "as notas de hoje" |
| Frequência do catálogo | A cada 6 h (usuário) | Preço mais fresco; cabe nas janelas livres e para no primeiro 429 |

## Ainda não especificado
- Fase 1: tamanho real da página da Steam sem login (o código já registra
  que ela pode devolver menos que 100) — medido na primeira varredura.
- Fase 2: se a busca no SQLite precisar de índice de texto (FTS5) para
  ficar abaixo de 400 ms — decidido medindo com o catálogo real.
- Expansão da nota (histórico para mais itens): fora deste plano. Ideia
  do usuário para quando vier: começar pelos itens que somem do mercado
  (caixas que saem do drop pool, cápsulas, adesivos de campeonato); skin
  comum por último — a evidência do modelo já mostra reversão à média em
  skins e comportamento diferente em caixas.

## Sempre / Nunca
- Sempre: o worker é o único que consulta a Steam; respeitar
  `RATE_LIMIT_DELAY_S` e o disjuntor; parar no primeiro 429.
- Sempre: visitar o site não dispara consulta à Steam.
- Nunca: inventar nota para item sem histórico; prometer lucro.
- Nunca: apagar `data/`; o catálogo fica fora dos backups (é refeito).

## Progresso
| Fase | Status |
| --- | --- |
| 1. Varredura no worker | aguardando aprovação |
| 2. Site lê o catálogo | aguardando aprovação |
| 3. Textos e verificação | aguardando aprovação |
