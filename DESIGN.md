---
name: Lodout
description: Notas de 0 a 100 explicadas para skins de CS2, num caderno escuro e calmo.
colors:
  laranja-aspas: "#f97316"
  laranja-acao: "rgba(249, 115, 22, 0.7)"
  laranja-pressionado: "#b8480a"
  azul-steam: "#66c0f4"
  verde-alta: "#39c266"
  amarelo-media: "#f2bb25"
  vermelho-queda: "#ff6e70"
  fundo-caderno: "#161616"
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
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "4rem"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "-0.006em"
  headline:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.008em"
  title:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "clamp(1.6rem, 4.2vw, 2.4rem)"
    fontWeight: 700
    lineHeight: 1.08
    letterSpacing: "-0.03em"
  lead:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 450
    lineHeight: 1.43
  body:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 450
    lineHeight: 1.47
  small:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 450
    lineHeight: 1.47
  label:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 700
    lineHeight: 1.47
    letterSpacing: "0.06em"
  numero:
    fontFamily: "Inter Variable, Inter, -apple-system, system-ui, sans-serif"
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

A tipografia é uma só família (Inter variável) em pesos levemente acima do comum (450 no corpo), para que o texto claro sobre fundo escuro não afine. Os títulos são grandes e firmes; os rótulos de dado são pequenos, em caixa alta e espaçados, como cabeçalhos de coluna de um caderno.

**Key Characteristics:**
- Fundo quase preto em camadas tonais (moldura, caderno, folha, rebaixo), com borda fina em vez de sombra.
- Um único laranja de ação e marca; verde/amarelo/vermelho reservados a significado.
- A nota como figurinha: anel colorido com o número no centro, sempre o mesmo em todo o site.
- Números tabulares e grandes onde a decisão acontece (preço, encomenda, nota).
- Explicação sempre ao lado do número, em português simples.

## Colors

Paleta neutra escura com um único laranja de voz e três cores de significado.

### Primary
- **Laranja Aspas** (#f97316): a cor da marca (as aspas do topo e do ícone do site), links de destaque, anel de foco e o trecho preenchido de barras e medidores. Nunca para texto corrido.
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
- **Fundo do Caderno** (#161616): fundo da página e de campos de texto.
- **Folha** (#1e1e1e): cartões, quadros e a tabela.
- **Folha em Foco** (#252525): hover de linhas e botões discretos; trilho de barras.
- **Rebaixo** (#131313): cabeçalho de tabela, fundo do seletor de período e do rodapé.
- **Linha** (#4a4a4a) e **Linha Forte** (#5a5a5a): bordas de cartões, divisórias e campos.
- **Texto** (#e8e8e8), **Texto Forte** (#ffffff) e **Texto Apagado** (#b3b3b3, 4,5:1 sobre #252525): corpo, títulos/números e legendas/rótulos.

### Named Rules
**The One Orange Rule.** O laranja é a única cor de ação. Se algo laranja não é clicável, não é a marca nem um medidor, troque a cor.

**The Meaning Colors Rule.** Verde, amarelo e vermelho só aparecem quando dizem alto/médio/baixo, subiu/caiu ou deu certo/errado. Nunca como decoração.

## Typography

**Display Font:** Inter Variable (com Inter, -apple-system, system-ui)
**Body Font:** Inter Variable
**Label/Mono Font:** Inter em caixa alta para rótulos; monoespaçada do sistema só para código e na API.

**Character:** uma família só, em pesos levemente encorpados sobre o escuro; a hierarquia vem de tamanho e peso, não de troca de fonte.

### Hierarchy
- **Display** (600, 4rem, 1.05): o título de página ("Ranking"), um por página.
- **Headline** (600, 2rem, 1.1): títulos de seção ("O que mudou no Top 20 desde ontem").
- **Title** (700, clamp(1.6rem, 4.2vw, 2.4rem), 1.08, -0.03em): nome do item na página do item.
- **Lead** (450, 1.3125rem): a frase-guia logo abaixo do título de página, em Texto Apagado.
- **Body** (450, 1.0625rem, 1.47): texto corrido e explicações, em até ~75 letras por linha.
- **Small** (450, 0.875rem): células de tabela, botões, metadados ("Última coleta completa há 2 h").
- **Label** (700, 0.75rem, 0.06em, caixa alta): rótulos de dado ("NOTA", "FREQUÊNCIA") e cabeçalhos de cartão.
- **Número** (700, 2rem, tabular): o valor em destaque onde se decide (encomenda sugerida, preço do item).

### Named Rules
**The Tabular Numbers Rule.** Todo preço, nota, porcentagem e contagem usa algarismos tabulares, para que colunas se alinhem e números que mudam não pulem.

**The Reading Measure Rule.** Explicação longa nunca passa de ~75 letras por linha; avisos pequenos, menos ainda.

## Layout

Coluna única centrada de até 980px de largura de conteúdo (texto puro em até 692px), com espaçamento em degraus de 4px (4, 8, 12, 16, 20, 24, 32, 40, 48, 56, 64). Grupos relacionados ficam a 8–12px; seções separam-se por 48px. Barra de controles (período, ações, legenda) numa linha acima da tabela, quebrando no celular.

No celular (até 640px), tabelas viram cartões: o nome e a figurinha da nota em cima, e os valores numa linha de rótulo + número embaixo; a navegação principal desce para uma barra fixa no rodapé com ícone e texto. Abaixo de 375px, o que não cabe desce para uma linha própria em vez de espremer.

## Elevation & Depth

O sistema é tonal: a profundidade vem de camadas de cinza (moldura → caderno → folha → rebaixo) e de bordas finas, com um toque de "vidro" (19/11): cartões em cinza levemente translúcido com borda clara e gradiente sutil, e o pódio do Ranking com fundo dourado/prata/bronze bem suave. O desfoque de fundo (backdrop-filter) fica só no que flutua por cima da página — topo, barra de baixo do celular, busca, dicas e avisos —, nunca em cartões ou selos repetidos (cada um é uma camada que o navegador recalcula ao rolar).

### Shadow Vocabulary
- **Sutil** (`box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04)`): cartões do celular.
- **Média** (`box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08)`): popovers e menus.
- **Alta** (`box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12)`): janelas de diálogo.

### Named Rules
**The Border-Not-Shadow Rule.** Um quadro se separa do fundo pela borda e pelo tom, nunca por borda e sombra larga juntas.

**The Glass Only Floats Rule.** Desfoque de fundo só no que flutua (topo, barra de baixo, busca, popovers, avisos). Em cartões e selos, fundo escuro quase sólido, que dá a mesma leitura sem custo ao rolar.

## Shapes

Cantos suaves e consistentes por escala: 8px em controles pequenos e campos, 12px em quadros de aviso e no seletor, 18px em cartões, 28px no quadro principal do item. Botões de ação, filtros e selos são pílulas. A nota é sempre um anel (círculo com progresso). Ícones de item ficam em quadrados de 40px com borda colorida pela raridade.

## Components

### Buttons
- **Shape:** pílula (980px).
- **Primary:** Laranja de Ação com texto branco, 44px de altura, 8px 20px; hover em Laranja Pressionado. Um por área de decisão ("Ver no Steam Market", "Devolver com o valor pago").
- **Hover / Focus:** transição de cor em 200ms (cubic-bezier(0.4, 0, 0.2, 1)); foco com anel Laranja Aspas de 2px.
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
- **Focus:** anel Laranja Aspas visível.
- **Error / Disabled:** mensagem em Vermelho Queda logo abaixo, dizendo o problema e como resolver.

### Navigation
- **Desktop:** barra Moldura (#080808) com a marca à esquerda, links centrais em texto translúcido e "Entrar com Steam" à direita. A página atual fica em texto forte com um traço Laranja Aspas de 2px embaixo (sem negrito, para os vizinhos não mudarem de lugar); nos links da conta, o atual fica em texto forte.
- **Celular:** barra fixa no rodapé com cinco itens (ícone + texto), o atual em laranja.

### Segmented Control (seletor de período)
Trilho Rebaixo com borda fina e cantos de 12px; cada opção é um texto apagado de 34px de altura, e a escolhida ganha o fundo Laranja de Ação com texto branco. Usado para período do Ranking, do gráfico e da nota.

### A Figurinha da Nota (signature)
A nota de 0 a 100 é sempre um anel: trilho cinza e arco de progresso na cor de significado (verde ≥ alto, amarelo médio, cinza baixo), com o número em peso 600 no centro. 40px nas listas, 28–32px em linhas compactas, 72px no item. Nunca aparece como número solto quando é a nota do Lodout.

### Preço Copiável (signature)
Valor em texto forte e tabular que, ao clique, copia o número sem "R$" e sem ponto de milhar; um ícone de copiar discreto fica sempre à vista, e a confirmação "copiado" aparece em um selo verde por 2s. Ao lado, o ícone da Steam abre o item no Mercado.

## Do's and Don'ts

### Do:
- **Do** usar o anel colorido sempre que mostrar a nota do Lodout, do mesmo jeito em todas as páginas.
- **Do** manter um único laranja (#f97316) como voz de ação e marca, e o laranja translúcido (rgba(249, 115, 22, 0.7)) como fundo de botão principal.
- **Do** separar quadros com borda fina (#4a4a4a) e tom (#1e1e1e sobre #161616).
- **Do** usar algarismos tabulares em preços, notas e porcentagens.
- **Do** transformar tabelas em cartões no celular, com rótulo em caixa alta acima de cada valor.
- **Do** mostrar a idade dos dados perto de qualquer número que dependa da coleta.

### Don't:
- **Don't** usar verde, amarelo ou vermelho como decoração; eles só dizem alto/médio/baixo ou certo/errado.
- **Don't** fazer algo piscar ou pulsar sem que um dado tenha mudado.
- **Don't** pôr etiqueta ou sobretítulo em cima de um título; informação extra vai abaixo dele.
- **Don't** juntar borda e sombra larga no mesmo quadro.
- **Don't** escrever explicação com mais de ~75 letras por linha.
- **Don't** usar fonte monoespaçada em preços e números (use a Inter com algarismos tabulares); monoespaçada só em código e teclas ("Ctrl K").
- **Don't** usar cores fora do sistema para texto (ex.: cinza-azulado #64748b, que reprova contraste); texto apagado é #b3b3b3.
- **Don't** escrever jargão ("pontuação algorítmica", "giro", "retorno líquido"): o público é iniciante, ver PRODUCT.md.
- **Don't** usar brilho colorido em volta de botões, ícones ou números (sombra laranja sem deslocamento); sombra é sempre escura e com deslocamento. O anel de foco (0 0 0 3px) é a única exceção.
- **Don't** usar texto em degradê; destaque vem do peso e do tamanho.
- **Don't** pôr faixa colorida grossa (mais de 1px) na lateral de quadros, avisos ou itens de lista.
- **Don't** pôr um cartão dentro de outro; dentro de um quadro, separe partes com um fio de 1px.
