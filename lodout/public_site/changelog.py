"""Changelog público do site -- mantido manualmente, não gerado do git.

Cada entrada: {data, titulo, itens}. Mais recente primeiro. Existe
porque "Status" (scan_historico) mostra SE o site está saudável, mas não
O QUE mudou -- esta página é sobre produto, não operação.
"""
from __future__ import annotations

ENTRADAS = [
    {
        "data": "2026-11-15",
        "titulo": "Sua conta mais fácil de ler",
        "itens": [
            "A lista da sua conta tem 5 colunas que cabem na tela: o item, quanto você pagou, quanto vale hoje, o lucro se vender hoje e “Venda por” (sem prejuízo e com a sua meta de lucro).",
            "Os itens aparecem do mais valioso para o menos valioso.",
            "Prejuízo aparece como “−R$ 98,76”, e os números dos cartões do topo cabem numa linha.",
            "Um aviso no topo diz quantos itens estão sem o valor pago; adicionar um item à mão fica recolhido, já que o inventário vem sozinho.",
            "Remover um item pede confirmação antes.",
            "O valor pago salva sozinho: digite e aperte Enter ou saia do campo. Sem o botão “salvar”, a lista cabe na tela sem rolar de lado, também em tablet.",
            "Item sem o valor pago mostra “informe quanto pagou” em “Venda por”, em vez de traços.",
            "Acabamento da conta: nome do item em destaque com o desgaste embaixo, valores alinhados à direita, “R$” dentro do campo do valor pago e cada cartão do topo com uma linha de contexto (quantos itens, em quantos você informou o valor, quanto o lucro representa do que você pagou).",
            "Ao salvar um valor pago, os cartões do topo e o aviso de itens sem valor atualizam na hora. A meta de lucro aplica ao escolher, sem o botão “aplicar”.",
            "Os números que mudam ao salvar acendem de leve e voltam ao normal, para você ver o que mudou (sem animação para quem pediu menos movimento no sistema). O “remover” ficou mais fácil de clicar.",
            "Remover um item abre uma janela própria de confirmação, com o botão vermelho e o foco em “Cancelar”. Os textos de apoio da lista ficaram maiores.",
            "Se você digitou um valor pago e tentar sair da página antes de salvar, o navegador avisa. Adicionar um item à mão também aceita vírgula (35,10).",
            "Itens que entram na coleta sem foto agora pegam a imagem do catálogo do Mercado (no ranking, um AK-47 | Safari Mesh aparecia sem imagem).",
            "Na página do item, a tabela “Outras versões” alinha preços e vendas à direita, para comparar de linha em linha.",
            "Na conta, preencher o valor pago ficou como numa planilha: digite e aperte Enter para salvar e ir direto ao próximo item sem valor. Os valores ficam alinhados pelos centavos, a tabela tem a mesma largura dos cartões e, no celular, cada item ocupa menos espaço.",
            "Watchlist, trades e histórico com o mesmo acabamento da conta: números alinhados à direita, “remover” discreto com janela de confirmação, campos de valor que aceitam vírgula e títulos dos quadros no lugar certo.",
            "A watchlist mostra o preço de hoje e a imagem também dos itens que o Lodout não acompanha (antes aparecia “—”). Nos trades, a imagem também vem do catálogo do Mercado.",
            "O histórico da carteira fica em ordem de data, com o gráfico num quadro só.",
            "As raridades aparecem com os mesmos nomes da Steam em português: Nível Consumidor, Nível Industrial, Nível Militar, Restrito, Secreto e Oculto (antes em inglês: Classified, Covert…). O Glossário traz também os nomes em inglês.",
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
