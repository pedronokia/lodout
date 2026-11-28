---
name: Lodout
description: Notas de 0 a 100 explicadas para skins de CS2, num caderno escuro e calmo.
colors:
  preto-marca: "#000000"
  branco-marca: "#ffffff"
  laranja-interface: "#f97316"
  laranja-acao: "rgba(249, 115, 22, 0.7)"
  laranja-pressionado: "#b8480a"
  azul-steam: "#66c0f4"
  verde-alta: "#39c266"
  amarelo-media: "#f2bb25"
  vermelho-queda: "#ff6e70"
  fundo-caderno: "#0F1012"
  folha: "#1e1e1e"
  folha-hover: "#252525"
  rebaixo: "#131313"
  moldura: "#080808"
  linha: "#4a4a4a"
  linha-forte: "#5a5a5a"
  texto: "#e8e8e8"
  texto-forte: "#ffffff"
  texto-apagado: "#b3b3b3"
typography:
  display:
    fontFamily: "Outfit, sans-serif"
    fontSize: "4rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Outfit, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Outfit, sans-serif"
    fontSize: "clamp(1.6rem, 4.2vw, 2.4rem)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  lead:
    fontFamily: "Geist, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 450
    lineHeight: 1.43
  body:
    fontFamily: "Geist, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 450
    lineHeight: 1.47
  small:
    fontFamily: "Geist, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 450
    lineHeight: 1.47
  label:
    fontFamily: "Geist, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.47
    letterSpacing: "0.06em"
  numero:
    fontFamily: "Geist, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.025em"
    fontFeature: "tnum"
rounded:
  xs: "8px"
  sm: "12px"
  md: "18px"
  lg: "28px"
  pill: "980px"
spacing:
  sp-1: "4px"
  sp-2: "8px"
  sp-3: "12px"
  sp-4: "16px"
  sp-5: "20px"
  sp-6: "24px"
  sp-7: "32px"
  sp-8: "40px"
  sp-9: "48px"
  sp-10: "56px"
  sp-11: "64px"
components:
  button-primary:
    backgroundColor: "{colors.laranja-acao}"
    textColor: "{colors.texto-forte}"
    typography: "{typography.small}"
    rounded: "{rounded.pill}"
    padding: "8px 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.laranja-pressionado}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.texto-apagado}"
    rounded: "{rounded.pill}"
    padding: "4px 10px"
  segmented:
    backgroundColor: "{colors.rebaixo}"
    rounded: "{rounded.sm}"
    padding: "3px"
  segmented-item:
    textColor: "{colors.texto-apagado}"
    typography: "{typography.small}"
    rounded: "{rounded.xs}"
    padding: "5px 13px"
    height: "34px"
  segmented-item-active:
    backgroundColor: "{colors.laranja-acao}"
    textColor: "{colors.texto-forte}"
  card:
    backgroundColor: "{colors.folha}"
    rounded: "{rounded.md}"
    padding: "16px 18px"
  card-hero:
    backgroundColor: "{colors.folha}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input:
    backgroundColor: "{colors.fundo-caderno}"
    textColor: "{colors.texto}"
    rounded: "{rounded.xs}"
    padding: "5px 8px"
  table-header:
    backgroundColor: "{colors.rebaixo}"
    textColor: "{colors.texto-apagado}"
    typography: "{typography.label}"
    padding: "12px 16px"
  copy-price:
    backgroundColor: "transparent"
    textColor: "{colors.texto-forte}"
    rounded: "{rounded.xs}"
    padding: "2px 4px"
---

# Design System: Lodout

## Overview

**Creative North Star: "O Caderno do Mercado"**

O Lodout é um caderno escuro e calmo aberto sobre o Mercado da Steam: cada página anota números observados e, ao lado de cada um, a conta de onde ele veio. Quem chega é iniciante e precisa decidir o que comprar e por quanto; o visual existe para que o número certo seja lido primeiro e a explicação esteja sempre a um olhar de distância, nunca para impressionar.

O clima é escuro, calmo e confiável. O fundo quase preto e as folhas cinza-escuras deixam o conteúdo em primeiro plano; a cor aparece pouco e sempre com significado: um único laranja para ação e marca, e verde, amarelo e vermelho só para dizer se uma nota ou um movimento é alto, médio ou de queda. Nada pisca sem motivo, e a idade dos dados fica à vista. A densidade é média: tabelas que viram cartões no celular, números grandes com tabulação alinhada e texto explicativo em medida de leitura.

A tipografia usa três famílias auto-hospedadas (escolha do usuário em 26/11): Outfit nos títulos, em peso 700, tracking -0,025em e entrelinha 1,15; Geist no corpo (450); nos preços, variações, desgastes e notas, a própria Geist com algarismos tabulares (revisão de 26/11, pedido do usuário: a Geist Mono nos números dava "cara de IA genérica" e vazava para textos como o nome da caixa); a Geist Mono ficou só para código. Nada vem do Google Fonts em runtime: o CSP de produção só aceita `self`. Os rótulos de dado são pequenos, em caixa alta e espaçados, como cabeçalhos de coluna de um caderno.

**Key Characteristics:**
- Fundo quase preto em camadas tonais (moldura, caderno, folha, rebaixo), com borda fina em vez de sombra.
- Um único laranja de ação e marca; verde/amarelo/vermelho reservados a significado.
- A nota como figurinha: anel colorido com o número no centro, sempre o mesmo em todo o site.
- Números tabulares e grandes onde a decisão acontece (preço, encomenda, nota).
- Explicação sempre ao lado do número, em português simples.

## Colors

Paleta neutra escura com um único laranja de voz e três cores de significado.

### Primary
- **Preto da marca** (#000000): o fundo do bloco da logomarca. Só nela — o fundo das páginas é #0F1012 (26/11).
- **Branco da marca** (#ffffff): as letras da logomarca e a inicial do símbolo. Não é cor de interface.
- **Laranja da interface** (#f97316): links de destaque, anel de foco e o trecho preenchido de barras e medidores. Nunca para texto corrido.
- **Logomarca oficial "Escura Alto Contraste"** (26/11, escolha do usuário): "lodout" minúsculo em branco (Outfit 800), sobre bloco #1A1D24 chanfrado com contorno branco 45%, sem TM. O SVG exato está em `templates/partials/_logo_svg.html` e vai inline no topo (`_logo.html`, 32px; 28px no celular) e no rodapé (`_rodape_links.html`, 34px). O mesmo desenho vale para o cartão de compartilhamento: `logo-escura-og.png` sai do partial via `scripts/gerar_assets_marca.py` e é usado por `og_cards.py`. A marca antiga de 25/11 segue em `static/logo-lodout.svg` só como histórico. O cartão de compartilhamento segue com fundo #161616 (asset gerado na CI, fora da rampa da página), título em Outfit e dados em Geist (sem Geist Mono desde 27/11). Não há versão 3D da marca: relevo, sombra, brilho e extrusão são usos proibidos.
- **Ícones da aba e do app** (26/11): a mesma silhueta chanfrada sai de dois SVGs em `static/`. `favicon.svg` traz o monograma `l` em Outfit 800, bem centrado, e gera `favicon.ico` (16/32/48 px) e `favicon-16/32/48.png` com fundo transparente — é o que vale em abas e marcadores. `logo-escura-app.svg` traz `lodout` centralizado em um quadrado #080808 com margem de segurança, e gera `apple-touch-icon.png` (180 px), `icon-192.png` e `icon-512.png`. Todos os rasterizados vêm de `scripts/gerar_assets_marca.py`; nenhum PNG/ICO é editado à mão. No manifest, o ícone `any` usa a marca completa (`logo-escura-app.svg`) e os tamanhos fixos usam os PNGs gerados; no `<head>`, o monograma vale para abas e o PNG de 180 px para o iOS. Todos com `?v=` no manifest para furar o cache de 1 ano do `/static`. O CSP continua `default-src 'self'` e o service worker não foi alterado.
- **Laranja de Ação** (rgba(249, 115, 22, 0.7)): fundo do botão principal e do item escolhido no seletor de período; o laranja translúcido sobre o preto dá contraste com texto branco sem gritar.
- **Laranja Pressionado** (#b8480a): hover do botão principal.

### Secondary
- **Azul Steam** (#66c0f4): referências à própria Steam (ícone e links que levam ao Mercado), para separar o que é do Lodout do que é da Steam.

### Tertiary
- **Verde Alta** (#39c266): nota alta, item que entrou ou subiu, lucro, confirmação ("copiado").
- **Amarelo Média** (#f2bb25): nota média e avisos de atenção.
- **Vermelho Queda** (#ff6e70): nota baixa, item que caiu ou saiu, prejuízo e erros.

### Neutral
- **Moldura** (#080808): barra do topo e navegação do celular.
- **Fundo do Caderno** (#0F1012): fundo da página e de campos de texto (26/11).
- **Folha** (#1e1e1e): cartões, quadros e a tabela.
- **Folha em Foco** (#252525): hover de linhas e botões discretos; trilho de barras.
- **Rebaixo** (#131313): cabeçalho de tabela, fundo do seletor de período e do rodapé.
- **Linha** (#4a4a4a) e **Linha Forte** (#5a5a5a): bordas de cartões, divisórias e campos.
- **Texto** (#e8e8e8), **Texto Forte** (#ffffff) e **Texto Apagado** (#b3b3b3, 4,5:1 sobre #252525): corpo, títulos/números e legendas/rótulos.

### Named Rules
**The One Orange Rule.** O laranja é a única cor de ação. Se algo laranja não é clicável, não é um medidor, troque a cor — a marca oficial é alto contraste, sem laranja.

**The Meaning Colors Rule.** Verde, amarelo e vermelho só aparecem quando dizem alto/médio/baixo, subiu/caiu ou deu certo/errado. Nunca como decoração.

## Typography

**Display Font:** Outfit (600/700/800) — h1/h2/h3 e títulos de página.
**Body Font:** Geist (400/500/600/700) — texto corrido, rótulos e botões.
**Number Font:** Geist com `tnum` (token `--font-num`) — preços, variações, faixas de desgaste e notas. Nos anéis de nota, algarismos proporcionais (o "100" cabe no anel pequeno).
**Mono Font:** Geist Mono (500/600/700) — só código (API, exemplos).

**Character:** três famílias auto-hospedadas; a hierarquia vem de tamanho, peso e da troca controlada entre título, corpo e número.

### Hierarchy
- **Display** (Outfit 700, 4rem, 1.15, -0.025em): o título de página ("Ranking"), um por página.
- **Headline** (Outfit 700, 2rem, 1.15, -0.025em): títulos de seção ("O que mudou no Top 20 desde ontem").
- **Title** (Outfit 700, clamp(1.6rem, 4.2vw, 2.4rem), 1.15, -0.025em): nome do item na página do item.
- **Lead** (450, 1.3125rem): a frase-guia logo abaixo do título de página, em Texto Apagado.
- **Body** (450, 1.0625rem = 17px, 1.47): texto corrido e explicações, em até ~75 letras por linha.
- **Small** (450, 0.875rem): células de tabela, botões, metadados ("Última coleta completa há 2 h").
- **Label** (700, 0.75rem, 0.06em, caixa alta): rótulos de dado ("NOTA", "FREQUÊNCIA") e cabeçalhos de cartão.
- **Número** (Geist 700, 2rem, `tnum`): o valor em destaque onde se decide (encomenda sugerida, preço do item).

### Named Rules
**The Tabular Numbers Rule.** Todo preço, nota, porcentagem e contagem usa algarismos tabulares, para que colunas se alinhem e números que mudam não pulem.

**The Reading Measure Rule.** Explicação longa nunca passa de ~75 letras por linha; avisos pequenos, menos ainda.

**The Scale Rule** (27/11, com o usuário). Todo tamanho de letra sai de um degrau da escala, os tokens `--fs-*` em `style.css`: 12 (`2xs`), 13 (`xs`), 14 (`sm`), 17 (`base`), 18 (`lead`), 19 (`lg`), 21 (`copy`), 24 (`titulo`), 32 (`xl`), 48 (`2xl`) e 64px (`display`). Nenhum texto fica abaixo de 12px. O texto corrido (apresentação da página inicial, descrição sob o título das páginas, Método, FAQ, Glossário) é 17px. Os títulos fluidos usam `clamp()`, e valores em `em` acompanham o texto ao redor. Exceções registradas: número dentro de moldura fixa (anéis de nota, contadores redondos dos filtros), teclas (`kbd`), legendas da barra de baixo do celular, ícones desenhados com texto, o campo de valor do simulador (16px, abaixo disso o iOS dá zoom) e o preço da vitrine (16px, pedido do usuário). O teste `test_tamanhos_de_letra_seguem_a_escala` falha com qualquer tamanho fora disso; exceção nova entra na lista do teste e aqui, com o motivo.

## Layout

Coluna única centrada de até 980px de largura de conteúdo (texto puro em até 692px), com espaçamento em degraus de 4px (4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64). Grupos relacionados ficam a 8–12px; seções separam-se por 48px. Barra de controles (período, ações, legenda) numa linha acima da tabela, quebrando no celular.

No celular (até 640px), tabelas viram cartões: o nome e a figurinha da nota em cima, e os valores numa linha de rótulo + número embaixo; a navegação principal desce para uma barra fixa no rodapé com ícone e texto. Abaixo de 375px, o que não cabe desce para uma linha própria em vez de espremer.

## Elevation & Depth

O sistema é tonal com vidro: a profundidade vem de camadas de cinza (moldura → caderno → folha → rebaixo), bordas finas claras e um vidro escuro estilo Apple (cinza translúcido + desfoque leve) em cartões, abas, destaque do dia, FAQ, blocos do Ranking e cápsulas (decisão do usuário, 22/11, que substitui o "cinza sólido" de 21/11). O pódio do Ranking tem fundo dourado/prata/bronze bem suave. O vidro é escuro e discreto: o texto mantém contraste de pelo menos 4,5:1 e nada fica claro ou azulado.

### Shadow Vocabulary
- **Sutil** (`box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04)`): cartões do celular.
- **Média** (`box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08)`): popovers e menus.
- **Alta** (`box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12)`): janelas de diálogo.

### Named Rules
**The Border-Not-Shadow Rule.** Um quadro se separa do fundo pela borda e pelo tom, nunca por borda e sombra larga juntas.

**The Dark Glass Rule.** Vidro só escuro (cinza neutro translúcido, nunca azulado) e com desfoque leve. Em listas longas que rolam (linhas de tabela, itens repetidos às dezenas), prefira o fundo quase sólido: cada desfoque é uma camada que o celular recalcula ao rolar.

## Shapes

Cantos suaves e consistentes por escala: 8px em controles pequenos e campos, 12px em quadros de aviso e no seletor, 18px em cartões, 28px no quadro principal do item. Botões de ação, filtros e selos são pílulas. A nota é sempre um anel (círculo com progresso). Ícones de item ficam em quadrados de 40px com borda colorida pela raridade.

## Components

### Buttons
- **Shape:** pílula (980px).
- **Primary:** Laranja de Ação com texto branco, 44px de altura, 8px 20px; hover em Laranja Pressionado. Um por área de decisão ("Ver no Steam Market", "Devolver com o valor pago").
- **Hover / Focus:** transição de cor em 200ms (cubic-bezier(0.4, 0, 0.2, 1)); foco com anel laranja da interface de 2px.
- **Ghost:** texto apagado sem fundo, borda fina em pílula ("Cores da borda"); ações de texto sublinhadas para ações secundárias ("Ver mais", "apagar").

### Chips
- **Style:** selos em pílula com borda da cor de significado e texto claro ("NOVO", "fora do inventário desde 16/11", raridade).
- **State:** só informativos; não são filtros clicáveis.

### Cards / Containers
- **Corner Style:** 18px (cartões), 12px (quadros de aviso e conta), 28px (quadro do item).
- **Background:** Folha (#1e1e1e).
- **Shadow Strategy:** nenhuma em repouso (ver Elevation & Depth).
- **Border:** 1px Linha (#4a4a4a); quadros de alerta usam a borda na cor de significado.
- **Internal Padding:** 16–18px; 24px no quadro do item.

### Inputs / Fields
- **Style:** fundo do caderno, borda 1px Linha, cantos de 8px, texto em 1.0625rem para não dar zoom no celular.
- **Focus:** anel laranja da interface visível.
- **Error / Disabled:** mensagem em Vermelho Queda logo abaixo, dizendo o problema e como resolver.

### Navigation
- **Desktop:** barra Moldura (#080808) com a marca à esquerda, links centrais em texto translúcido e "Entrar com Steam" à direita. A página atual fica com o texto aceso: branco forte e um brilho leve, sem traço embaixo (pedido do usuário, 23/11) e sem negrito, para os vizinhos não mudarem de lugar; nos links da conta, o atual fica em texto forte.
- **Celular:** barra fixa no rodapé com cinco itens (ícone + texto), o atual em laranja.

### Segmented Control (seletor de período)
Trilho Rebaixo com borda fina e cantos de 12px; cada opção é um texto apagado de 34px de altura, e a escolhida ganha o fundo Laranja de Ação com texto branco. Usado para período do Ranking, do gráfico e da nota.

### A Figurinha da Nota (signature)
A nota de 0 a 100 é sempre um anel: trilho cinza e arco de progresso na cor de significado (verde ≥ alto, amarelo médio, cinza baixo), com o número em peso 600 no centro. 40px nas listas, 28–32px em linhas compactas, 72px no item. Nunca aparece como número solto quando é a nota do Lodout.

### Preço Copiável (signature)
Valor em texto forte e tabular que, ao clique, copia o número sem "R$" e sem ponto de milhar; um ícone de copiar discreto fica sempre à vista, e a confirmação "copiado" aparece em um selo verde por 2s. Ao lado, o ícone da Steam abre o item no Mercado.

### Ajustes de consistência (26/11)

Rodada de polimento aplicada só em `style.css` e nos templates, sem tocar em
dados, cálculo, workers, chamadas à Steam, CSP ou Caddyfile:

- **Fundo e superfícies:** `#0F1012` é o fundo da página; a folha segue em
  `#1e1e1e`, o hover em `#252525` e o rebaixo em `#131313`. Nenhum cinza
  avulso: cartões, tabelas e campos usam os mesmos tokens de borda (`#4a4a4a`),
  raio (`--radius-md` nos cartões, `--radius-xs` nos campos) e fundo.
- **Cartões de resumo (`/conta`):** os quatro cartões esticam para a mesma
  altura; o valor e as linhas de apoio ganham respiro lateral (`padding-inline`)
  e intervalo vertical igual no desktop e no celular.
- **Tabelas:** no inventário (Minha conta) o nome do item aparece inteiro,
  quebrando em mais linhas se precisar, e as colunas têm largura fixa no
  computador para a tabela não passar da borda dos outros quadros (pedido
  do usuário, 27/11: "o nome não pode ficar cortado"). No Ranking também
  (28/11): o nome inteiro, quebrando linha, porque o desgaste é o que separa
  itens do mesmo skin. No cartão do Ranking no celular, o anel do canto leva
  a legenda "hoje" e, sem nota na última coleta, aparece "sem nota hoje" em
  vez de um traço. As colunas de Custo, Valor,
  Lucro/Prejuízo e Venda usam Geist com `tabular-nums`, com
  o marcador "—" e as ações na mesma régua; valores compostos (R$ + %) não
  quebram no meio. No Ranking, a coluna ITEM tem largura fixa no computador.
- **Anéis de nota:** número centrado por `place-items: center`, `line-height: 1`
  e `text-align: center`, mono e tabular em desktop e celular.
- **Vitrine:** régua vertical de 8 px entre imagem, nome, motivo, preço e
  rodapé; nenhum filho acrescenta margem vertical a essa régua.
- **Filtros da conta:** busca, pílulas e ordenação alinhados na mesma faixa;
  só a pílula ativa recebe o laranja de ação.
- **Telas estreitas (390–640 px):** largura mínima zero e truncamento
  controlado em títulos, rótulos e contadores, sem rolagem horizontal.
- **Interação:** `:focus-visible` com contorno de 2 px em `#f97316` e
  deslocamento de 3 px; `:hover` discreto em botões, links, abas e linhas,
  sem mudar a cor dos números.
- **Rodapé:** três colunas com o mesmo intervalo, marca oficial chanfrada sem
  TM e notas de dados públicos em largura de leitura.

A imagem de compartilhamento (`og-image.png`) continua gerada na CI a partir
da marca oficial, com fundo `#161616`; ela não faz parte da rampa da página.

## Do's and Don'ts

### Do:
- **Do** usar o anel colorido sempre que mostrar a nota do Lodout, do mesmo jeito em todas as páginas.
- **Do** manter um único laranja (#f97316) como voz de ação, e o laranja translúcido (rgba(249, 115, 22, 0.7)) como fundo de botão principal; a marca é preto e branco.
- **Do** separar quadros com borda fina (#4a4a4a) e tom (#1e1e1e sobre #0F1012).
- **Do** usar algarismos tabulares em preços, notas e porcentagens.
- **Do** transformar tabelas em cartões no celular, com rótulo em caixa alta acima de cada valor.
- **Do** mostrar a idade dos dados perto de qualquer número que dependa da coleta.

### Don't:
- **Don't** usar verde, amarelo ou vermelho como decoração; eles só dizem alto/médio/baixo ou certo/errado.
- **Don't** fazer algo piscar ou pulsar sem que um dado tenha mudado.
- **Don't** pôr etiqueta ou sobretítulo em cima de um título; informação extra vai abaixo dele.
- **Don't** juntar borda e sombra larga no mesmo quadro.
- **Don't** escrever explicação com mais de ~75 letras por linha.
- **Don't** usar fonte monoespaçada em preços, notas ou textos de dado (dá cara de terminal/IA genérica); números usam Geist com algarismos tabulares (`--font-num`), e a Geist Mono fica só para código.
- **Don't** usar cores fora do sistema para texto (ex.: cinza-azulado #64748b, que reprova contraste); texto apagado é #b3b3b3.
- **Don't** escrever jargão ("pontuação algorítmica", "giro", "retorno líquido"): o público é iniciante, ver PRODUCT.md.
- **Don't** usar brilho colorido em volta de botões, ícones ou números (sombra laranja sem deslocamento); sombra é sempre escura e com deslocamento. O anel de foco (`outline` de 2px em `#f97316`, deslocado 3px) é a única exceção.
- **Don't** usar texto em degradê; destaque vem do peso e do tamanho.
- **Don't** pôr faixa colorida grossa (mais de 1px) na lateral de quadros, avisos ou itens de lista.
- **Don't** pôr um cartão dentro de outro; dentro de um quadro, separe partes com um fio de 1px.
- **Don't** justificar texto nem partir palavras com hífen automático; texto corrido é alinhado à esquerda.
- **Don't** usar fundo azulado (azul-marinho, ardósia) em quadros, cartões ou tabelas; superfícies são #0F1012, #1e1e1e, #252525 e #131313. O único azul é o do botão "Entrar com Steam", que é a cor da Steam. Selos, etiquetas e medidores também não usam azul: neutro (cinza claro) ou laranja.
