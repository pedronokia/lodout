# Conta com inventário sincronizado e preço de venda para lucro

Pedido: 2026-11-15 (conversa). Quem entra no Lodout compra para revender.
Cenário: a pessoa entra com a Steam, o inventário aparece sozinho, ela
informa uma vez quanto pagou em cada item, e o site mostra por quanto
vender para empatar e para ter o lucro que ela quer.

## O que já existe (lido no código)
- Login oficial da Steam (OpenID) e página `/conta` com itens digitados à
  mão, custo opcional e "Lucro (sem taxa)" (`account.py`, `user_portfolio`).
- Leitura do inventário público (`steam_api.fetch_inventory`) e mescla que
  nunca apaga o que a pessoa digitou (`portfolio.merge_steam_inventory`,
  feita para a carteira global antiga — precisa da versão por pessoa).
- Conta de empate com a taxa (`portfolio.break_even_price`).

## Limite que não se cruza
O preço pago NÃO vem da Steam: fica só no histórico privado do Mercado,
que exige a chave de API ou a sessão da pessoa — o golpe mais comum do
CS2. O site nunca pede nem guarda isso (AGENTS.md). A pessoa digita.

## Fases

### Fase 1: lucro de verdade e preço de venda (S)
Verificado quando: na `/conta`, um item pago R$ 100 mostra empate R$ 115,00
e, com meta de 20%, venda por R$ 138,00; "Lucro (sem taxa)" vira lucro já
com a taxa.
- Arquivos: `account.py`, `templates/conta.html`, `static/style.css`,
  `tests/test_public_site.py`.
- Preço de venda para a meta: custo × 1,15 × (1 + meta).
- Bloqueado por: nada.

### Fase 2: inventário sincronizado sozinho (M)
Verificado quando: entrar com a Steam traz o inventário para a `/conta`
sem clicar em nada; inventário privado mostra como torná-lo público;
abrir a `/conta` nunca consulta a Steam.
- Versão por pessoa da mescla (`user_portfolio`): item novo entra sem
  custo; o custo digitado nunca é apagado enquanto o item estiver no
  inventário; item que saiu do inventário (vendido/trocado) sai da lista
  junto com o custo (decisão do usuário: "se vendeu, apaga os dados").
- Sincroniza no login (ação da pessoa) e 1x por dia pelo worker, só para
  quem entrou nos últimos 30 dias, com a pausa da Steam e parando no
  primeiro bloqueio. Nunca no simples abrir da página.
- Arquivos: `account.py`, `user_portfolio.py`, `worker.py`,
  `templates/conta.html`, testes.
- Bloqueado por: Fase 1.

### Fase 3: "quanto paguei" rápido (S)
Verificado quando: a lista do inventário tem um campo de preço pago em
cada item, salva sem recarregar a página toda e funciona no celular.
- Bloqueado por: Fase 2.

## Dependência conhecida
Hoje só ~180 itens têm preço do dia no site. Os outros do inventário
aparecem com "sem preço ainda" até a Fase 2 do catálogo grande, que traz
o preço do dia de todo o mercado.

## Decisões (usuário, 2026-11-15)
| Decisão | Escolha | Por quê |
| --- | --- | --- |
| Quando sincronizar | No login + 1x/dia pelo worker | Automático para a pessoa, sem consultar a Steam a cada visita |
| Meta de lucro | A pessoa escolhe; começa em 20%; sempre com a taxa da Steam | Cada um tem a sua meta; a taxa entra em toda conta |
| Item que saiu do inventário | Sai da lista e o custo é apagado | "Se vendeu, apaga os dados" |

## Sempre / Nunca
- Nunca: pedir, ler ou guardar senha, cookie, chave de API da Steam.
- Nunca: consultar a Steam só por abrir uma página.
- Sempre: o custo digitado é da pessoa — a sincronização só o apaga quando
  o item sai do inventário (vendido/trocado), como decidido.
- Sempre: tom de dado, não promessa ("para lucrar 20%, venda por…").

## Progresso
| Fase | Status |
| --- | --- |
| 1. Lucro com taxa e preço de venda | feita (2026-11-15) |
| 2. Inventário sincronizado | feita (2026-11-15) |
| 3. "Quanto paguei" rápido | aprovada |
