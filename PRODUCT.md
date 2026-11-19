# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Iniciantes em skins de CS2 no Brasil (confirmado em 17/11). Querem decidir o
que comprar e por quanto (inclusive por encomenda na Steam) e acompanhar o
que já têm: a própria carteira, os itens anunciados e as vendas. Leem pelo
celular e pelo computador, em português.

## Product Purpose

O Lodout (lodout.com) mostra dados observados no Mercado da Steam (preços,
histórico, fila de encomendas) e dá a cada item uma nota de 0 a 100 com o
porquê. Ajuda o iniciante a decidir o que comprar e por quanto, e a enxergar
o lucro ou o prejuízo do que já tem, já descontando a taxa da Steam.
Sucesso: a pessoa entende a nota e a conta, decide sozinha e volta para
acompanhar. O site não prevê retornos nem promete lucro.

## Positioning

A nota explicada (escolha do usuário em 17/11): uma nota de 0 a 100 em que
cada fator e seus pontos aparecem na página do item, em português simples,
sem prometer lucro. O resto (a conta da taxa, a encomenda sugerida, a
carteira) serve a essa decisão explicada.

## Operating Context

- Um worker separado é o único que coleta da Steam, várias vezes por dia,
  respeitando os limites (pausa ao receber 429). Abrir uma página nunca
  consulta a Steam; toda página mostra a idade dos dados.
- Fluxo de compra: ver a nota e a encomenda sugerida (Ranking ou item),
  copiar o valor, abrir o item no Mercado da Steam e colar. Mudar o valor
  fica a critério da pessoa.
- Fluxo da conta: login opcional com a Steam (OpenID); o inventário público
  vira carteira com lotes, itens anunciados e vendidos, trocas e planilha.

## Capabilities and Constraints

- Nota de 0 a 100 para algumas centenas de itens, com fatores explicados; o
  Ranking ordena pela nota média no período (7 dias a 1 ano) e mostra o que
  mudou no Top 20 desde ontem.
- Busca no mercado inteiro (~33 mil itens, varredura diária) com preço
  recente dos itens ainda sem nota.
- Encomenda sugerida: R$ 0,01 acima da maior encomenda que já existe na
  Steam, copiável; a conta "para lucrar X%" é referência, não promessa.
- Regras fixas: português simples sem jargão; nunca prometer lucro; nunca
  pedir senha, cookie de sessão ou chave de API; o preço pago é sempre
  digitado pela pessoa; abrir página nunca consulta a Steam.
- Termos do site: "nota", "encomenda", "taxa da Steam", "Top 20",
  "Minha conta", "trocas" (o que deu × o que recebeu), "Itens vendidos".

## Brand Commitments

- Nome "Lodout" (maiúscula no texto; minúsculo só em URL e domínio).
- Marca: aspas laranja do topo da página, também usadas no ícone do site.
- Voz: português simples, tom de quem explica para iniciante; diz a idade
  dos dados e os limites da conta em vez de esconder.

## Evidence on Hand

- Dados reais: preços, histórico, fila de encomendas e notas coletados pelo
  worker; contador de visitas e de pessoas online; backtest diário da nota
  (resultado público em /api/health).
- Não há depoimentos, clientes, imprensa nem resultados de lucro de
  usuários: nunca inventar.

## Product Principles

1. Explicar antes de recomendar: todo número mostra de onde veio.
2. Honestidade sobre o incerto: idade dos dados à vista, sem previsão nem
   promessa de lucro, e avisar quando a conta dá prejuízo.
3. O site sugere, a pessoa decide: valores prontos para copiar, sempre
   editáveis.
4. Segurança da conta acima de conveniência: nada de senha, cookie ou chave.
5. Iniciante primeiro: termos explicados, celular tão bom quanto o
   computador.

## Accessibility & Inclusion

Prática atual, cobrada por testes: todo campo com nome acessível, foco de
teclado visível, links no meio do texto sublinhados (para quem não distingue
cores), respeito a "reduzir movimento" e alvos de toque confortáveis no
celular.
