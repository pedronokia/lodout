"""Changelog público do site -- mantido manualmente, não gerado do git.

Cada entrada: {data, titulo, itens}. Mais recente primeiro. Existe
porque "Status" (scan_historico) mostra SE o site está saudável, mas não
O QUE mudou -- esta página é sobre produto, não operação.
"""
from __future__ import annotations

ENTRADAS = [
    # Reorganizado em 2026-11-16: os itens de 15 e 16/11 tinham ido todos
    # para 15/11 (60 itens, alguns já substituídos no mesmo dia). Cada
    # entrada descreve como as coisas ficaram, na linguagem de quem usa.
    {
        "data": "2026-11-17",
        "titulo": "Página inicial mais clara, textos revisados e ícone novo",
        "itens": [
            "A página inicial diz logo no topo o que é o Lodout (notas de 0 a 100 para skins de CS2, com o porquê de cada uma) e leva a “Como funciona”. O resumo do Top 20 ficou mais simples (“3 itens entraram no Top 20 desde ontem”) e o preço do destaque diz desde quando mudou.",
            "“Meus trades” agora guarda as suas trocas com outros jogadores: o que você deu, o que recebeu e quanto valia cada lado, com o saldo no dia da troca e com os preços de hoje. Vendas ficam em “Itens vendidos”, no Histórico; os registros de compra e venda que estavam em “Meus trades” foram para lá.",
            "Ao digitar o nome de um item (Watchlist, trocas e “Adicionar um item à mão”), aparecem sugestões em português ou inglês com o preço de hoje; não é mais preciso saber o nome exato do Mercado.",
            "Ranking novo: os itens que se mantêm com as melhores notas, pela nota média em 7 dias, 30 dias, 90 dias ou 1 ano (e não só pela nota de hoje, que muda bastante de uma coleta para outra). Embaixo, o que mudou no Top 20 desde ontem: quem entrou, saiu, subiu ou caiu, com “Ver mais” quando a lista é longa. Cada item do Ranking sugere um valor de encomenda: um centavo acima da maior encomenda que já existe na Steam, que é atendida primeiro. Um clique copia o valor para colar na Steam; mudar fica a seu critério.",
            "Em “Minha conta”, a meta de lucro virou uma barra de arrastar (de 1% a 100%): o preço de venda de cada item muda enquanto você arrasta.",
            "A página de cada item ganhou o histórico da nota (7 dias, 30 dias, 90 dias ou 1 ano), guardado a cada coleta a partir de hoje.",
            "O rodapé mostra quantas pessoas estão no site agora. A contagem usa só um código aleatório de cada aba aberta, sem cookie e sem ligação com a sua conta, apagado em minutos (detalhes em Privacidade).",
            "A página “Como funciona a nota” lista os fatores que mais pesam (inclusive a facilidade de comprar e vender), explica por que, nas skins, uma queda em todos os períodos soma pontos, e corrige que o nível do preço só conta para caixas e cápsulas.",
            "Abriu um item que não existe (nome digitado errado ou link antigo)? A página diz qual item não foi achado, sugere os de nome parecido e já deixa o nome na busca.",
            "O desgaste “Well-Worn” aparece com o nome da Steam em português, “Bem Desgastada” (era “Bastante Usada”). O Glossário ganhou “Taxa da Steam” e “Encomenda”.",
            "O ícone do site (na aba do navegador e ao instalar no celular) voltou a ser as aspas laranja do topo da página, desenhadas na grade de pixels para ficarem nítidas na aba.",
            "A página de Privacidade conta que o banco tem uma cópia de segurança por dia, guardada por 7 dias: depois de excluir a conta, os dados ainda ficam nessas cópias por até uma semana e então somem sozinhos.",
            "Filtrar o catálogo inteiro do Mercado (desgaste, preço) ficou de 4 a 6 vezes mais rápido.",
            "No celular, as listas pesam menos: os ícones pequenos (conta, watchlist, trades, ranking e “itens parecidos”) não baixam mais a versão grande da imagem, sem perder nitidez.",
            "No Ranking, “Comparado com o ranking salvo há 1 dia” virou “Comparado com o Top 20 de ontem”; no Status, “Visitas ao dashboard” virou “Visitas ao site”.",
            "Links no meio do texto (Glossário e Histórico) ficaram sublinhados, para quem não distingue bem as cores, e a lista do Glossário ficou mais fácil para leitores de tela.",
        ],
    },
    {
        "data": "2026-11-16",
        "titulo": "Mais itens com nota, conta mais rápida e login mais longo",
        "itens": [
            "Comprar por encomenda: a página de cada item mostra até quanto pagar numa encomenda da Steam para lucrar a sua meta (20% sem login) revendendo pelo preço de hoje, já com a taxa, e qual é a maior encomenda que já existe; os cartões do início e a watchlist mostram o “encomenda até”.",
            "Mais itens com nota: a coleta passou a avaliar também os cerca de 100 itens mais anunciados do Mercado que ainda não tinham nota (armas, facas, luvas, caixas e cápsulas, a partir de R$ 1). Se a Steam não reclamar, mais itens entram aos poucos.",
            "O login com a Steam dura 30 dias (ou até você clicar em “Sair”); antes acabava toda vez que o navegador era fechado. Em computador compartilhado, lembre de clicar em “Sair”.",
            "Conta mais rápida com inventário grande: com 500 itens, num celular intermediário, a página abre em cerca de 1 segundo (eram 5), e buscar e ordenar ficaram até 6 vezes mais rápidos.",
            "No cartão “Vale hoje”, a variação é “desde ontem” (ou “nos últimos N dias”), comparando com o valor de cerca de 24 horas atrás. “Lucro hoje” diz de quantos itens a conta é de verdade: item com valor pago mas sem preço hoje fica de fora.",
            "Preencher muitos valores pagos seguidos não esbarra mais no limite de segurança do site. Enquanto o inventário da Steam é atualizado, a página não se recarrega no meio da digitação e, se a busca demorar, oferece “Recarregar a página”.",
            "Na página de um item que você tem, “Na sua conta” mostra como você está hoje (“Se vender hoje: lucro de R$ 2,09 (+9%)”, já sem a taxa) e “Informar quanto pagou” abre a conta já nesse item, com o cursor no campo. A explicação da taxa ficou exata: 15% sobre o que você recebe, cerca de 13% do que o comprador paga.",
            "Watchlist e trades no mesmo padrão da conta: cada campo tem o nome em cima, os alertas falam português simples (os de vendas e anúncios ficam em “Mais opções”, explicados), o alvo escolhido ao adicionar aparece como alerta e o alerta no Discord ficou recolhido.",
            "Excluir a conta ficou separado dos links de baixar a planilha e a cópia dos dados. A página de excluir explica o que é apagado, diz que a sua conta e os seus itens na Steam não são afetados e sugere baixar uma cópia antes; depois, a página inicial confirma.",
            "A página de Privacidade foi corrigida: ela dizia que o Lodout nunca lia o seu inventário, mas a conta lê o seu inventário público da Steam (o mesmo que qualquer pessoa vê no seu perfil). Agora ela lista tudo o que é guardado e o que fica só no seu navegador. A FAQ ganhou “O Lodout vê o meu inventário da Steam?”.",
            "Se algo der errado do nosso lado, a página de erro oferece “Tentar de novo” (volta para onde você estava), sem termos técnicos; a página de “não existe” também deixou de falar em “dashboard”.",
            "Os avisos “Para revender sem prejuízo” (página do item) e de inventário privado (conta) trocaram a faixa grossa na lateral por uma borda fina, como os outros quadros.",
            "Depois de “Sair”, o botão Voltar do navegador não mostra mais a sua conta (útil em computador compartilhado). Uma aba aberta antes de você sair e entrar de novo agora avisa que ficou desatualizada e oferece “Recarregar a página”, em vez de dizer que o login expirou ou mostrar um erro em inglês.",
            "Com a internet lenta, digitar dois valores pagos seguidos (ou trocar duas vezes o “Quero lucrar”) podia guardar o primeiro, embora a tela mostrasse o segundo; agora vale sempre o último. Trocar o “Quero lucrar” numa conta grande também deixou de travar a página por alguns segundos.",
            "No cartão “Vale hoje”, a variação “desde ontem” agora avisa quando inclui itens que entraram ou saíram da sua conta (“contando itens que entraram”), para não parecer que o mercado subiu. E separar um item em lotes (“valores diferentes?”) não muda mais a contagem de itens nos cartões.",
            "Na lista da conta, os lotes do mesmo item ficam juntos em qualquer ordem, “Nome (A–Z)” põe “2” antes de “10”, e a busca acha o tipo do item em português (“cápsula”, “caixa”, “faca”, “luva”) mesmo quando a Steam só tem o nome em inglês.",
            "Corrigido: anunciar um item no Mercado da Steam fazia ele sumir da sua conta junto com o valor pago (a Steam tira do inventário público o que está anunciado). Agora o item com valor pago fica na conta e pergunta o que aconteceu: marque “Está anunciado” (ele fica até você tirar) ou “Vendi”, que abre uma janela para informar por quanto vendeu, já mostra quanto você recebe e o lucro e pede uma segunda confirmação (“Sim, vendi”) antes de mover o item; a venda vai para “Itens vendidos”, na página Histórico, com o lucro já sem a taxa. Se o anúncio for cancelado, o item volta ao normal sozinho.",
            "Ao marcar “Está anunciado”, a conta pergunta por quanto você anunciou (já vem o preço para lucrar a sua meta) e mostra o preço na etiqueta, na página do item e na planilha; o “Vendi” já vem com esse valor. Dá para mudar o preço depois. Item que você trocou ou deu (não vendeu) sai da lista pelo “remover”, que agora aparece em todo item fora do inventário.",
            "Até 23/11, quem teve itens apagados ao anunciar no Mercado pode recuperá-los com o valor pago pelo quadro que aparece no topo de “Minha conta” (só para quem perdeu algo): ele lista os itens e o valor pago de cada um antes de devolver, e depois destaca esses itens na lista para você marcar “Está anunciado” ou “Vendi”. Não quer algum de volta? “Não quero de volta” esconde o aviso. Item que você vendeu ou removeu não é oferecido de novo.",
            "Itens anunciados e vendidos em todas as telas: a página do item avisa quando ele está anunciado ou fora do inventário e mostra as suas vendas dele; a conta ganhou a aba “Fora do inventário” (o aviso “N itens não aparecem” leva até ela); a planilha baixada tem a coluna “Situação”; no Histórico, cada item vendido leva à página dele e “desfazer venda” devolve o item à conta, com o valor pago, se você marcou “Vendi” por engano; e a FAQ explica o que acontece ao anunciar um item.",
        ],
    },
    {
        "data": "2026-11-15",
        "titulo": "Sua conta mais fácil de ler e de preencher",
        "itens": [
            "A lista da conta mostra, para cada item, quanto você pagou, quanto vale hoje, o lucro se vender hoje e “Venda por”, do mais valioso para o menos valioso. No celular cada item é um cartão compacto que mostra só o que existe (sem valor pago: o nome, o campo e o preço).",
            "No topo, quatro cartões: “Vale hoje” (com quanto você recebe vendendo tudo, depois da taxa), “Você pagou” (com quanto já foi preenchido), “Lucro hoje” e “Sem valor pago”, com o botão “Preencher agora” que mostra só esses itens e põe o cursor no primeiro.",
            "Preencher o valor pago ficou como numa planilha: digite e aperte Enter para salvar e ir ao próximo item sem valor. Aceita “35,10” e “R$ 1.234,56”, dá para desfazer logo depois e, se salvar falhar (login expirado, internet), o valor fica no campo com um aviso ao lado.",
            "“Venda por” é o preço que o comprador paga: na tela de venda da Steam, cole em “O comprador paga” (não em “Você recebe”). Tocar no preço copia o número, e “Quero lucrar” muda os preços na hora.",
            "Pagou valores diferentes pelo mesmo item? “valores diferentes?” separa as unidades em lotes, cada um com o seu valor pago; “juntar lotes” volta a uma linha só, com o valor médio.",
            "Inventário grande: busca pelo nome, filtros (sem valor pago, no lucro, no prejuízo), ordem e o título da tabela fixo ao rolar. No celular, um botão “Buscar” volta até a busca quando você rola para cima.",
            "Correções importantes: preços de itens sem nota apareciam em dólar como se fossem reais (agora são convertidos pela cotação da própria Steam); ao preencher com Enter, a lista podia se reorganizar no meio da digitação; no celular, a busca e os filtros não escondiam nenhum item; e sair da conta agora limpa os avisos que ainda não tinham aparecido.",
            "Mais fácil de ler e de usar por qualquer pessoa: letras pequenas mais legíveis, a conta funciona pelo teclado, com leitor de tela, no alto contraste do Windows e com o texto do navegador maior; a idade dos preços aparece na tela e tocar em “confira” explica o aviso.",
            "A página de um item que você tem mostra “Na sua conta”: quantas unidades, quanto pagou e por quanto vender, lote por lote.",
            "Watchlist, trades e histórico com o mesmo acabamento: números alinhados, “remover” com confirmação, campos que aceitam vírgula; a watchlist mostra preço e imagem também dos itens sem nota.",
            "As raridades aparecem com os nomes da Steam em português (Nível Consumidor, Nível Industrial, Nível Militar, Restrito, Secreto e Oculto), e itens sem foto pegam a imagem do catálogo do Mercado.",
        ],
    },
    {
        "data": "2026-11-14",
        "titulo": "Cartões alinhados e páginas de item e ranking revistas",
        "itens": [
            "Na lista de itens, preço, estrela e rodapé ficam na mesma altura em todos os cartões de uma fileira — antes um selo a mais empurrava só o preço daquele cartão.",
            "A linha de status da página inicial diz quantos itens coletados ficam fora da lista por risco alto de alta artificial (era por isso que o total coletado e o da aba “Todas” não batiam).",
            "Paginação numa linha só, com “Anterior” e “Próxima”; abas de categoria numa linha, rolando de lado no celular.",
            "O botão “Só favoritos” ficou do tamanho da busca e ganhou a estrela dourada dos favoritos.",
            "Na página do item, o “Por quê” vem logo abaixo da nota, a imagem ficou maior e as ações (SteamDB, Copiar nome, Favoritar) ficam numa linha só.",
            "No ranking, “↑ +1” e “=” viraram “↑ 1 posição” e “mesma posição”.",
            "Itens não perdem mais a imagem quando a Steam devolve o preço por um caminho mais curto, sem a foto: o site reaproveita a da coleta anterior.",
            "A busca e os filtros agora procuram em todo o Mercado de CS2 (skins, facas, luvas, caixas, cápsulas e adesivos): primeiro os itens com nota, depois os outros com o preço do dia, marcados “sem nota ainda”. Cada um tem sua página com o preço e a conta da revenda.",
            "Na sua conta, itens do inventário fora dos acompanhados também ganham o preço do dia.",
            "A conta da revenda avisa que não dá para revender na hora: item comprado no Mercado só pode ser vendido depois da data que aparece nele, e item recebido por troca fica 7 dias protegido (regras oficiais da Steam).",
            "A página Status mostra o catálogo do Mercado: quantos itens, quando foi a última volta e se a Steam pediu pausa. O Glossário explica o que é “sem nota ainda”.",
            "Na conta, salvar quanto você pagou num item atualiza só aquela linha, sem recarregar a página; aceita vírgula (35,10) e os itens ainda sem valor ficam destacados.",
            "Sua conta traz os itens do seu inventário da Steam sozinha, a cada login e uma vez por dia: é só informar quanto pagou em cada um. Itens vendidos ou trocados saem da lista. O inventário precisa estar público na Steam.",
            "Na sua conta, cada item mostra por quanto vender para não ter prejuízo e para lucrar a meta que você escolher (começa em 20%), já com a taxa da Steam.",
            "Também na página do item: “Isso já aconteceu antes?” — em quantas vezes, no último ano, quem comprou o item e vendeu 30 dias, 90 dias ou 1 ano depois recuperou o que pagou, já com a taxa da Steam.",
            "Na página de cada item, a conta da revenda: por quanto o item precisa ser vendido para você receber de volta o que pagou, já que a Steam fica com cerca de 15% de cada venda.",
            "Em “Mais filtros”, os mesmos filtros do Mercado da Steam: Exterior (Nova de Fábrica, Testada em Campo…), Raridade (a cor da borda).",
            "A busca funciona como a do Mercado da Steam: aceita o nome em inglês (“Field-Tested”, “Snakebite Case”) ou em português, não liga para acento e aceita as palavras em qualquer ordem (“redline ak”).",
            "O fator “subindo/caindo em todos os períodos” da nota passa a olhar o preço médio de cada dia, e não uma venda solta. Antes, uma única venda fora do normal podia tirar ou dar 10 pontos a um item; na medição feita antes da troca, 27 de 172 itens mudavam, para os dois lados.",
        ],
    },
    {
        "data": "2026-11-14",
        "titulo": "Mais fácil de ler, de achar e de usar",
        "itens": [
            "A tendência de preço (subindo/caindo) agora compara 7 dias de verdade. Antes, por uma mudança no formato dos dados da Steam, olhava só as últimas horas — e a nota de um item podia subir ou cair até 25 pontos de uma coleta pra outra por uma oscilação pequena.",
            "Verde, vermelho e laranja do site ficaram mais claros: no fundo escuro, os tons antigos eram difíceis de ler em letra pequena.",
            "Na página do item, o painel de preço, nota e caixa cabe numa linha (o nome da caixa aparecia enorme e o preço quebrava em duas linhas) e o “Por quê” mostra os pontos de cada fator numa etiqueta ao lado do texto.",
            "Busca sem resultado diz o que foi buscado e como acertar; as abas de categoria passam a contar só o que a busca encontra.",
            "Ao tentar comparar mais de 3 itens, a barra de comparação avisa o limite (antes a caixinha só não marcava).",
            "A página inicial ganhou atalhos pra “Como a nota é calculada” e pro Glossário, e a home mostra 12 itens por página, fechando a grade.",
            "Ícones das skins preenchem o quadro em vez de aparecer em miniatura, e o cartão de “Maiores mudanças” inteiro leva ao item.",
        ],
    },
    {
        "data": "2026-11-14",
        "titulo": "Top 20 com preço mais fresco",
        "itens": [
            "Os 20 primeiros do ranking passam a ter o preço atualizado a cada 2 horas, entre as coletas completas de 6 em 6 horas. A página Status mostra quando foi a última atualização.",
            "Ao compartilhar o link de um item (Discord, WhatsApp, X…), aparece um cartão com o ícone, a nota, o preço e a cor da raridade. As demais páginas ganharam a imagem padrão do Lodout.",
        ],
    },
    {
        "data": "2026-11-13",
        "titulo": "Acessibilidade e acabamento (auditoria de interface)",
        "itens": [
            "Navegando com Tab, o item em foco não fica mais escondido atrás do cabeçalho ou da barra de baixo do celular.",
            "Leitores de tela passam a ouvir “Copiado” e quantos itens estão selecionados pra comparar.",
            "Barra do navegador no celular e tela de abertura do app instalado agora são escuras, como o site.",
            "Campos de formulário que só mudavam a borda ganharam o mesmo destaque laranja dos demais ao receber foco.",
            "Nomes de itens não são mais “traduzidos” pelo tradutor automático do navegador.",
            "Toque mais limpo no celular, sem o flash cinza nos botões.",
            "No celular, abas, seletores, paginação e links pequenos ganharam área de toque de ~40px sem mudar o desenho.",
            "Botões dão uma leve encolhida ao serem apertados; títulos e parágrafos não terminam mais com uma palavra sozinha na última linha.",
        ],
    },
    {
        "data": "2026-11-13",
        "titulo": "Novo nome e endereço: Lodout",
        "itens": [
            "O site agora se chama Lodout e passa a ficar em lodout.com.",
            "O endereço antigo (galaseca.com) continua funcionando e vai passar a levar direto pro novo.",
            "Favoritos, notas e comparações salvos no navegador ficam guardados por endereço: quem estava usando o endereço antigo começa do zero no novo.",
        ],
    },
    {
        "data": "2026-11-13",
        "titulo": "Ranking por período, novidades do jogo e preços mais confiáveis",
        "itens": [
            "Ranking: escolha comparar com a coleta anterior, 24 horas, 7 dias ou 30 dias. Setas, variação de nota e o resumo usam a mesma comparação.",
            "Ranking: lista de quem saiu do Top 20 no período escolhido.",
            "Página do item: presença no Top 20 dia a dia nos últimos 30 dias, com a melhor posição.",
            "Página do item: outras versões da mesma skin (desgaste, StatTrak™, Souvenir), com preço mediano e vendas em 24 horas.",
            "Nova página Novidades: mudanças nos arquivos do CS2 (drop semanal, Armory, caixas novas) e os anúncios oficiais da Valve.",
            "Caixa que sai do Armory passa a ser marcada como aposentada sozinha, com a data da mudança nos arquivos do jogo; caixas e cápsulas novas entram na lista acompanhada sem precisar de ajuste manual.",
            "Coleta de preços: quando a Steam pede uma pausa, a coleta espera e continua, em vez de pular itens. O item que estava sendo buscado na hora é tentado de novo no fim.",
            "Coleta de preços: item que mesmo assim fica sem preço continua no site com o preço anterior, com um aviso, em vez de sumir por 6 horas.",
            "Coleta de preços: se a Steam pausou muito numa coleta, a seguinte anda mais devagar e volta ao normal sozinha. Itens que ficam dias sem ninguém vendendo passam a ser tentados uma vez por dia.",
            "Coleta de preços: quando a Steam devolve páginas vazias em sequência (um bloqueio disfarçado), a coleta pausa e tenta de novo, em vez de calcular a nota sem o histórico.",
            "Coleta de preços: se o site for atualizado no meio de uma coleta, ela continua de onde parou. Se a Steam estiver fora do ar, a coleta para cedo e tenta de novo em 1 hora, em vez de 6.",
            "Status: barra de progresso da coleta em andamento e quantos itens vieram com preço novo na última.",
            "Início: item com o preço da coleta anterior ganha um selo no card e na lista, com a hora em que o preço foi coletado.",
        ],
    },
    {
        "data": "2026-11-12",
        "titulo": "Tema escuro",
        "itens": [
            "Site inteiro no tema escuro: fundo quase preto #0a0a0a, texto #e5e5e5, texto secundário #9ca3af e bordas #3f3f46.",
            "Tiles elevadas em #171717 e caixas de destaque no preto #0a0a0a, mantendo o laranja da casa nos botões e foco.",
        ],
    },
    {
        "data": "2026-11-12",
        "titulo": "Cores do site com o laranja da marca",
        "itens": [
            "Cores do site ajustadas à nova identidade, com o laranja como cor principal:",
            "Fundo branco puro #ffffff, texto #1F1F1F (Ink), texto secundário #626262 (Ink 70%), bordas #D2D2D2 (Ink 20%).",
            "Rodapé, cartas e caixas de destaque no mesmo esquema monocromático.",
        ],
    },
    {
        "data": "2026-11-12",
        "titulo": "Polimentos de consistência visual nas páginas de erro, admin e conta",
        "itens": [
            "Páginas 404, 429 e 500 ganharam cabeçalho de página (título + descrição), card com CTA e o rodapé padrão com grupos de links.",
            "Painel admin e login de admin ganharam descrição no cabeçalho, card ao redor do formulário e rodapé padrão.",
            "Os botões de ação dessas páginas ganharam o mesmo formato arredondado e laranja do resto do site.",
            "Minha watchlist envolve os formulários 'Adicionar item' e 'Alerta no Discord' em cards, igual às demais páginas de conta.",
            "Minha histórico envolve gráfico e tabela em card dentro de .resumo-cards, igual ao resto das páginas de conta.",
            "Excluir conta ganha descrição no cabeçalho e envolve o aviso em .resumo-cards.",
            "Sobre ganha descrição mais completa no cabeçalho da página.",
            "Formulários 'Adicionar item' (Minha conta) e 'Registrar trade' (Meus trades) envolvidos em .resumo-cards > .card, igual aos demais formulários de conta (watchlist, admin login).",
        ],
    },
    {
        "data": "2026-11-12",
        "titulo": "Correções de acessibilidade (teclado e leitor de tela)",
        "itens": [
            "Removido tabindex='-1' dos termos do glossário: todos agora são alcançáveis com a tecla Tab (violação de WCAG 2.1.1 corrigida).",
            "Páginas 404, 429 e 500 passam a ter um único <h1> (o título da página); o logo deixa de ser h1 nessas páginas.",
            "O menu das páginas da sua conta (Trades, Watchlist, Histórico) passa a ser anunciado pelo leitor de tela como “Minhas páginas”.",
            "Quando um campo do login de admin ou do alerta da watchlist tem erro, o leitor de tela avisa na hora e indica qual campo precisa de correção.",
        ],
    },
    {
        "data": "2026-11-12",
        "titulo": "Páginas abrem mais rápido",
        "itens": [
            "A letra do site começa a carregar junto com a página, em vez de esperar o resto: o texto aparece mais cedo.",
            "As imagens das skins que vêm direto da Steam começam a carregar mais cedo.",
        ],
    },
    {
        "data": "2026-11-11",
        "titulo": "Páginas de erro e de conta no mesmo padrão do site",
        "itens": [
            "Páginas 404, 429 e 500 ganharam cabeçalho de página (título + descrição), card com CTA e o rodapé padrão com grupos de links.",
            "Painel admin e login de admin ganharam descrição no cabeçalho, card ao redor do formulário e rodapé padrão.",
            "Os botões de ação dessas páginas ganharam o mesmo formato arredondado e laranja do resto do site.",
            "Minha watchlist envolve os formulários 'Adicionar item' e 'Alerta no Discord' em cards, igual às demais páginas de conta.",
        ],
    },
    {
        "data": "2026-11-11",
        "titulo": "Texto, botões e rodapé redesenhados",
        "itens": [
            "O texto ficou maior e mais espaçado, com títulos bem maiores que o corpo do texto",
            "Os botões viraram pílulas coloridas e os links de texto perderam a caixa em volta",
            "Os cards e as caixas de destaque ganharam o raio de 18px, fio "
            "de 1px e nenhuma sombra -- o bloco do topo da home virou um "
            "painel quase preto com o número da nota em branco",
            "O rodapé virou um bloco cinza de ponta a ponta, com letra menor",
            "As abas de categoria, o seletor Vitrine/Lista, os campos de "
            "filtro e a barra do celular foram todos refeitos no mesmo "
            "vocabulário visual",
        ],
    },
    {
        "data": "2026-11-11",
        "titulo": "A marca virou aspas e o nome ganhou forma de nome",
        "itens": [
            "O cabeçalho agora mostra só as aspas da marca, que acendem ao passar o mouse",
            "O nome do site nos títulos das páginas passou a ser "
            "“Galaseca”, com G maiúsculo -- o resto do texto continua "
            "“galaseca”",
            "O ícone da aba do navegador e o do celular (instalar na tela "
            "de início) passaram a ser as mesmas aspas da barra, sem a "
            "vela vermelha da marca antiga",
        ],
    },
    {
        "data": "2026-11-11",
        "titulo": "Categorias só com nome e contagem",
        "itens": [
            "Os desenhos que ficavam na frente do nome de cada categoria "
            "saíram: a barra de filtros ficou só com o nome e a quantidade "
            "de itens, mais limpa e sem repetir a mesma figura em várias "
            "abas",
            "O seletor Vitrine/Lista também ficou só com as palavras, sem "
            "os desenhos de grade e de lista",
        ],
    },
    {
        "data": "2026-11-11",
        "titulo": "Cabeçalho mais fino",
        "itens": [
            "A barra do topo ficou mais fina e o conteúdo começa mais cedo na tela",
            "A barra ganhou fundo escuro, com o menu em texto claro",
            "Os links do menu ficam juntos, com o mesmo respiro entre "
            "eles, em vez de se espalharem até as pontas da barra",
            "A marca virou um símbolo redondo com aspas, no lugar do "
            "nome escrito: a barra fica leve e sobra espaço para o menu",
            "O botão de entrar virou um item discreto da barra, sem a "
            "pílula azul; o símbolo da Steam continua ao lado do texto",
            "No celular, a barra de baixo acompanha a do topo no mesmo "
            "fundo escuro, para as duas parecerem o mesmo sistema",
            "A página aberta não ganha mais um risco embaixo do nome no "
            "menu -- quem usa leitor de tela continua sabendo em qual "
            "página está",
            "A frase de apoio ao lado do botão de entrar saiu da barra; "
            "o que o login desbloqueia continua explicado no FAQ",
        ],
    },
    {
        "data": "2026-11-10",
        "titulo": "Nova identidade visual: tema claro e tranquilo",
        "itens": [
            "A paleta de cores foi refeita: fundo branco e cinza-claro, "
            "com azul só em links e botões, no lugar da mistura de azul, "
            "verde-limão e várias cores de raridade competindo entre si",
            "Cantos recortados, brilho ao redor da raridade, listra "
            "diagonal e a inclinação 3D dos cards ao passar o mouse "
            "saíram -- a hierarquia agora vem do tamanho, peso e espaço, "
            "não de efeitos",
            "Home, item, ranking, comparar, status e as páginas de "
            "leitura (método, FAQ, glossário) passaram a falar a mesma "
            "língua visual",
            "O rodapé se organizou em três grupos de links e o botão de "
            "entrar com a Steam ganhou o ícone da marca",
        ],
    },
    {
        "data": "2026-11-08",
        "titulo": "Gráficos com tooltip e portfólio com mais destaque",
        "itens": [
            "Ícones de itens em resolução mais nítida nas telas de alta "
            "densidade, em vez da mesma imagem pequena esticada",
            "Comparar: o ícone do item voltou ao mesmo tamanho grande "
            "usado no resto do site",
            "Minha conta e Meus trades: o card de lucro ganhou o mesmo "
            "destaque visual que a Nota já tinha na página do item",
            "Meu histórico: o gráfico de valor da carteira agora mostra "
            "data e valor exato ao passar o mouse, com a cor indicando "
            "se subiu ou caiu",
            "A home voltou a mostrar quantos itens novos entraram no "
            "Top 20 desde a última comparação",
            "Status: o gráfico de visitas por dia também ganhou essa "
            "informação ao passar o mouse",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Novo nome e endereço: GalaSeca",
        "itens": [
            "O site agora se chama GalaSeca e fica em galaseca.com",
            "Facas e luvas entraram na coleta (o nome usado na Steam não "
            "batia e esses itens voltavam vazios)",
            "O Ranking passou a mostrar as 20 maiores notas de toda a coleta",
            "No celular, cada item vira um cartão com os rótulos de cada dado",
            "\"Só favoritos\" avisa quando o favorito está em outra página "
            "da lista, com link pra ele",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Tabela mais clara e ações organizadas",
        "itens": [
            "Texto e espaçamento das linhas ficaram mais confortáveis de ler",
            "A tabela destaca um motivo por item; os demais fatores continuam "
            "disponíveis ao expandir a explicação",
            "Favoritar e comparar ficam visíveis; as outras ações foram "
            "agrupadas em um menu",
            "O espaço da miniatura fica reservado mesmo quando a imagem "
            "ainda não está disponível",
            "A etiqueta de caixa descontinuada ficou mais discreta",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Miniaturas das skins e nomes mais fáceis de ler",
        "itens": [
            "A tabela volta a mostrar as imagens das skins assim que a coleta as recebe da página pública da Steam",
            "O nome do item não fica mais espremido entre os controles; "
            "ações e links ganharam uma linha própria",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Mais clareza na página de recomendações",
        "itens": [
            "O estado dos dados deixa mais claro quando a coleta está atrasada",
            "Filtros ativos podem ser removidos separadamente sem perder os demais",
            "Preços ficam alinhados e a tendência também aparece por escrito",
            "A nota e o risco ganharam explicações visíveis",
            "O cabeçalho da tabela acompanha a rolagem em telas grandes",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Filtros mais compactos no celular",
        "itens": [
            "Nota mínima e preço máximo agora aparecem lado a lado "
            "em telas pequenas",
            "Uma indicação mostra que a tabela pode ser deslizada "
            "para ver as outras colunas",
            "A paginação informa quantos itens estão visíveis e o total "
            "encontrado nos filtros",
        ],
    },
    {
        "data": "2026-10-29",
        "titulo": "Formulários e documentação mais claros",
        "itens": [
            "Formulários de carteira, trades e watchlist agora avisam "
            "quando os dados informados são inválidos",
            "Regras já salvas continuam preservadas quando uma nova "
            "regra é inválida",
            "Login Steam agora confirma que o retorno pertence à sessão "
            "que iniciou o acesso",
            "Documentação da API atualizada com o limite de consultas "
            "e um exemplo fiel à resposta atual",
            "Tabela mais larga em telas grandes; a coluna 'Por quê' "
            "resume os dois primeiros fatores e permite abrir o restante",
        ],
    },
    {
        "data": "2026-10-27",
        "titulo": "Tabela mais leve e o login explicado",
        "itens": [
            "Página principal mostra 10 itens por vez em vez de 20 -- "
            "rola menos pra achar o botão \"Ver mais\"",
            "A nota pessoal por item some atrás de um ícone até você "
            "clicar nele, em vez de ocupar espaço em toda linha",
            "O selo de \"mudou desde sua última visita\" agora tem uma "
            "forma diferente do ▲/▼ de preço, pra não confundir os dois",
            "\"Entrar com Steam\" ganhou uma frase explicando o que você "
            "ganha ao logar (portfólio, trades e watchlist)",
            "Mais acessível pra quem usa leitor de tela nos formulários "
            "de conta, trades, watchlist e login do painel interno",
        ],
    },
    {
        "data": "2026-10-26",
        "titulo": "Página de cada item, login, app no celular e uma correção na coleta",
        "itens": [
            "Página de detalhe por item, comparador lado a lado, "
            "favoritos, buscas salvas, exportar CSV",
            "Dá pra instalar o site como app no celular, e o painel interno passou a pedir senha de verdade",
            "Corrigido um erro que travava a coleta inteira quando um item não tinha preço médio",
            "Perguntas frequentes, exportar os seus próprios dados, e mais de 50 ajustes de acessibilidade, busca no Google e segurança",
        ],
    },
    {
        "data": "2026-10-25",
        "titulo": "Ajustes de bastidores",
        "itens": [
            "Copiar nome do item com um clique, agrupar por categoria, "
            "atalho de teclado \"/\" pra buscar",
            "Expandir qualquer linha pra ver o cálculo completo da nota, "
            "não só os 3 motivos principais",
            "Páginas mais leves e rápidas de carregar, mapa do site pro Google e uma página própria pra link quebrado",
            "Esta página de mudanças e a documentação da API pública (pra quem quer usar os dados em outro programa)",
        ],
    },
    {
        "data": "2026-10-24",
        "titulo": "Visual novo e correção no limite de consultas à Steam",
        "itens": [
            "Visual novo (paleta azul escuro, inspirada na Steam)",
            "Busca por nome, ordenar clicando na coluna, filtros "
            "(categoria/nota/preço), paginação",
            "Ícone de cada item, nome linkado pro Steam Market, "
            "selo pra caixa descontinuada",
            "Página /status com histórico de scans (inclusive os que "
            "falharam) e contador de visitas",
            "Corrigido um erro em que a coleta seguia consultando a Steam por ~26 min mesmo depois de bloqueada, em vez de parar cedo",
        ],
    },
    {
        "data": "2026-10-23",
        "titulo": "Site público no ar",
        "itens": [
            "O site foi ao ar num servidor gratuito da Oracle, com conexão segura (HTTPS) automática",
            "Login com Steam, portfólio/trades/watchlist/histórico "
            "pessoais, proteção contra abuso",
            "Página de privacidade e exclusão de conta",
        ],
    },
]
