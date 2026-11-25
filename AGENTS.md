# Lodout — contexto para agentes

Este repositório mantém **um único produto: o site público Lodout**.
Não recrie o app desktop nem a UI web paralela. O preview local do próprio
site (`scripts/dev_public_site.py`) e o worker de coleta continuam necessários.

## Stack e estrutura

- Python 3.12 (piso subiu de 3.9 em 2026-11-05 -- Pillow 11.3.0, última
  da série 11.x, tinha 73 CVEs sem patch retroativo; o fix exige
  Python >=3.10, e 3.12 já era testado na CI), Flask, SQLite e `httpx`;
  dependências em `requirements-public-site.txt`.
- `lodout/public_site/`: rotas, templates, CSS, JavaScript, autenticação,
  persistência, testes operacionais e worker do site.
- Alguns módulos de domínio em `lodout/` são dependências diretas do site
  ou do worker (Steam pública, catálogo, coleta, recomendações, sinais,
  aposentadorias e trades). Antes de remover um módulo, confira imports diretos
  e dinâmicos e rode os testes.
- `scripts/dev_public_site.py`: preview local. Produção usa
  `Dockerfile.public-site`, `docker-compose.public-site.yml`,
  `docker-compose.oracle.yml` e `.github/workflows/`.
- `tests/`: testes do site e dos módulos compartilhados que ele usa.

## Produto e segurança

- A fonte de dados do mercado é a Steam Community Market pública. Nunca peça,
  leia ou armazene senha, cookie de sessão ou chave privada da Steam.
- A autenticação opcional do site usa Steam OpenID; não automatize ações na
  conta Steam.
- Visitar páginas públicas não inicia scans. O processo `worker` é o único
  responsável pela coleta de preços e respeita os limites da Steam.
- Consultas de rede em telas do visitante só acontecem por ação explícita,
  fora do carregamento automático da página.
  O inventário da conta (`public_site/inventario.py`) sincroniza no login
  (a ação da pessoa), em segundo plano, e 1x por dia pelo worker
  (`LODOUT_INVENTARIO_DIARIO=1`); abrir `/conta` nunca consulta a Steam.
  O preço pago é sempre digitado pela pessoa: ele só existe no histórico
  privado do Mercado, e o site nunca pede chave de API nem sessão.
  Quem pagou valores diferentes pelo mesmo item separa as unidades em
  lotes (`user_portfolio.separar`/`juntar`, campo `lote`); a sincronização
  (`inventario._acertar_lotes`) trata os lotes do mesmo nome juntos. Mudou
  a mesclagem? O worker também sincroniza: publique com `[restart-worker]`,
  senão o worker antigo apaga os lotes extras.
  Anunciar no Mercado tira o item do inventário público até vender, então
  "sumiu" não prova venda (relato de 2026-11-16: a sincronização apagava o
  valor pago). Item com valor pago que some fica na conta com `fora_desde`;
  a pessoa marca "Está anunciado" (`anunciado`, fica até ela tirar) ou
  "Vendi" (sai da lista e vai para `user_vendidos`, mostrado no Histórico;
  "Meus trades" são as TROCAS entre jogadores, `user_trocas.py`, desde
  2026-11-17: deu x recebeu, valor de cada lado no dia; os registros
  antigos de compra e venda migram para `user_vendidos` com source
  "trades" e no Histórico só podem ser apagados, não "desfeitos"). Volta sem as marcas se
  reaparecer no inventário. Só o sem valor pago sai sozinho. Vendas e
  trocas da Steam não são públicas: o site não tem como saber sozinho. Valores apagados antes disso:
  `python -m lodout.public_site.recuperar_posicoes STEAMID|--todos
  [--aplicar]`, lendo os backups diários (7 dias), ou o quadro no topo
  de `/conta` (até 23/11). Item vendido, removido ou dispensado ("Não
  quero de volta") entra em `preferencias.recuperar_ignorar` e não volta;
  "desfazer venda" no Histórico devolve o lote e tira o nome dessa lista.
- O site descreve dados observados; não promete retorno nem faz previsão.
- Mantenha validação, CSRF, limites de tentativas e codificação de saída nas
  rotas que recebem dados.
- Não adicione segredos, arquivos `.env`, chaves, bancos locais ou dados
  pessoais ao Git.

## Dados locais e persistência

- `data/` é armazenamento local e pode conter banco de contas, chave de sessão,
  caches e logs. **Nunca o apague em uma limpeza de código**.
- Use `lodout._paths.atomic_write_text` / `atomic_write_bytes` para arquivos
  persistentes, não `Path.write_text` diretamente.
- Para registros JSON, use `load_json_record`; JSON malformado é colocado em
  quarentena em vez de ser tratado como registro vazio.
- Backups do site e do banco têm regras próprias em `public_site/db_backup.py`.
- Evite defaults de caminho capturados na definição de funções; resolva o
  caminho atual dentro da função para que testes possam isolá-lo.

## Steam e análise

- `steam_api.RATE_LIMIT_DELAY_S` é a fonte única dos intervalos. Consulte o
  valor no momento da chamada; não o copie para constantes ou defaults.
- Respeite o disjuntor de rate limit da Steam. Não faça requisições extras de
  diagnóstico nem retry imediato após 429.
- Uma listing page sem histórico pode ser throttle silencioso. Em varreduras,
  várias respostas vazias em sequência são suspeita de bloqueio, não prova de
  que cada item não tem histórico.
- Em `_find_query`, priorize nome exato, depois substring, e só então
  correspondência aproximada explicitamente permitida. Não retorne o primeiro
  resultado do laço.
- Datas da Steam sem ano referem-se ao ano corrente; normalize-as antes de
  gerar chaves persistentes.
- Percentuais internos usam escala de **0 a 100**. Não multiplique por 100
  uma segunda vez.
- Evidência histórica do modelo: momentum reverte à média em skins; a inversão
  não se aplica a caixas, cujo comportamento de longo prazo é diferente.
  O preço absoluto também foi um sinal forte. Não use resultados contaminados
  por lookahead nem transforme resultados passados em promessa de lucro.
- Registros de aposentadoria de caixas exigem fonte factual. Não invente data
  de saída do drop pool; consulte `retirements.py` e os dados persistidos.
- O catálogo amplo (`public_site/catalogo.py`, plano em
  `plans/archive/catalogo-grande.md`) varre a busca do Mercado no tempo livre
  do worker, com pausa de `RATE_LIMIT_DELAY_S` × `LODOUT_CATALOGO_FATOR_PAUSA`
  e parando no primeiro 429 (2 h sem tentar). A busca é a consulta mais
  vigiada da Steam: não acelere a varredura sem medir os bloqueios em
  `/api/health` → `catalogo`. Liga com `LODOUT_CATALOGO=1` (só produção).
  Medido em 15/11: a busca sem login devolve 10 itens por página (não 100);
  o mercado inteiro leva ~15 h, então a rodada completa é 1x por dia.
  **A busca ignora `currency=7`: `sell_price` vem em centavos de DÓLAR.**
  O banco do catálogo guarda dólar; toda leitura (`precos`, `consultar`,
  `item`, filtro de preço) converte com `catalogo.cambio()`, medida pela
  mediana reais (coleta) ÷ dólar (catálogo) dos itens nos dois. Não leia
  a coluna `preco` direto como reais.
- Itens a mais com nota (`public_site/itens_extras.py`, 2026-11-16; degrau 2 em
  2026-11-19; volta a 100 em 2026-11-25): os mais anunciados do catálogo (sem
  adesivos, a partir de R$ 1) somam-se aos alvos da coleta;
  `LODOUT_ITENS_EXTRAS` (padrão 200, máx. 400; em produção 100 desde 25/11:
  com 200, 4 dos últimos 5 ciclos ficaram incompletos e 3 tiveram pausas 429;
  com 350, metade das coletas parava por 429).
  Cada item custa ~50 s/dia que saem da volta do catálogo. Suba em degraus de +100 só
  com `/api/health` -> `ultimo_ciclo_worker.pausas_429` limpo por 2–3 dias;
  acima de ~500 a volta do catálogo passa de 1,5 dia. O rodízio (histórico
  1x/dia) foi medido e descartado: a nota muda demais com cópia velha.
- Cache de variantes SSR (2026-11-19, Pilar 1): cada página de listagem traz o
  SSR de até 10 variantes irmãs do mesmo skin (wears x Normal/StatTrak/Souvenir).
  O worker semeia `_PAGE_CACHE` em `steam_api` (TTL 2 h, limpo no início de cada
  ciclo); variantes irmãs do mesmo skin no ciclo são avaliadas diretamente do
  cache sem consultas HTTP adicionais à Steam e sem risco de 429.

### Evidência histórica do modelo

- O backtest de 2026-07-28 encontrou reversão à média em skins em todos os
  horizontes medidos. A inversão de momentum e multi-período melhorou o
  ranking de skins, mas piorou caixas a 365 dias; por isso a reversão não
  é aplicada a containers.
- O preço absoluto foi um sinal forte a 365 dias (IC −0,2635 no geral,
  −0,3036 em caixas e −0,0415 em skins). O ajuste de nível de preço fica
  restrito a containers porque os testes em skins não justificaram ativá-lo.
- No estudo de coortes, caixas recém-aposentadas tiveram retorno histórico
  maior que caixas ativas, mas a amostra era pequena e o efeito decaiu com o
  tempo. Sem data registrada, usar o status atual numa amostra histórica é
  lookahead; `case_status(..., as_of=...)` corrige apenas caixas com data.
- O contexto de topo deve evitar pontos horários isolados: uma compra atípica
  pode distorcer o máximo. Sinais descrevem essas medições passadas; não
  constituem previsão ou promessa de retorno.
- Os experimentos acima (e os de `signals.py`: vintage bonus V1-V6, pump
  risk V1-V3B etc.) foram calibrados e validados na MESMA amostra --
  achado de auditoria (backtesting-frameworks, 2026-11-05): risco de
  overfitting por tentativa repetida. Ao calibrar um fator NOVO, use
  `score_backtest.split_itens()` pra separar calibração de confirmação
  por item antes de decidir -- ver o docstring da função pra disciplina
  de uso (resultado de confirmação é o que se reporta, não se ajusta
  o fator depois de ver esse número).
- Backtest diário (2026-11-17): a nota quase não ordena o resultado
  (Spearman ~0,03), e a faixa 85-100 teve a pior mediana a 365 dias. O
  backtest só replaya os fatores de preço (sem livro de ofertas, que dá
  os +25/+20 de liquidez da nota ao vivo). `/api/health` -> `backtest`
  -> `horizontes` -> `fatores` traz cada fator "com x sem", em skins e
  caixas, com split por item (`backtest_diario._FATORES_SEED`): tire
  hipóteses da calibração, reporte a confirmação, e mostre ao usuário
  antes de mudar qualquer peso.
- Mudança de pesos de 2026-11-22 (com o ok do usuário, a partir do
  backtest diário, confirmação a 1 ano): o fator "mediana" ("Preço X%
  abaixo/acima do típico", até ±35) saiu da nota (`signals._MEDIANA_PESO
  = 0.0`) porque errou o sentido em skins e caixas; "multi_period"
  ("Subindo/Caindo em todos os períodos") ficou só em caixas e cápsulas
  (`_MULTI_PERIOD_EM_SKINS = False`). Os fatores do livro de ofertas
  (spread +25, book +20), que mais pesam no Top 20, não têm histórico:
  o teste "para a frente" (`backtest_diario.teste_para_frente`, em
  `/api/health` -> backtest -> para_frente) compara a nota que o site
  mostrou (notas_historico) com o preço 30 dias depois; primeiro
  resultado por volta de 17/12. Notas antes e depois de 22/11 usam
  réguas diferentes.

## Interface pública

- Preserve o tema existente e o vocabulário em português para usuários
  iniciantes. Explique termos e estados em vez de exibir códigos internos.
- Mantenha navegação por teclado, foco visível, rótulos acessíveis e layouts
  utilizáveis em celular e desktop.
- O CSP não permite estilos inline. Prefira classes e regras em `style.css`.
- As telas que exibem preços carregam primeiro os valores já guardados; não
  faça fetch automático ao abrir a página.
- Não há conexão SSE (a anotação antiga estava errada). O único sinal
  periódico é o `static/online.js` do rodapé ("N pessoas no site agora",
  2026-11-17): 1 POST por minuto por aba visível a `/api/online`, com um
  código aleatório do sessionStorage, sem cookie; `online.py` guarda só
  código e hora por 10 min. Não use esse código para rastrear ninguém.
- Ações destrutivas pedem confirmação antes de enviar a requisição.

### Arquitetura da informação (revisão 2026-11-14)

- Tese do site, numa frase: o Lodout analisa o mercado de skins de CS2
  com dados públicos da Steam; cada skin tem uma nota com o porquê, além de
  preços e encomendas, sem prometer lucro. Título da home (20/11): "Entenda
  o mercado de skins de Counter-Strike 2". No texto do site, sempre
  "Counter-Strike 2" por extenso, nunca "CS2" (pedido do usuário, 20/11). A escala da nota (0 a 100) NÃO aparece no
  texto do site, nem como "/100" (pedido do usuário, 20/11).
  Público: iniciantes em skins de CS2 (tom baixo-médio, termos explicados).
- Função de cada página: Home = ver as notas de hoje e achar um item;
  Item = entender a nota daquele item; Ranking = os melhores de forma
  CONSISTENTE (nota média em 7d/30d/90d/1 ano, `notas_historico.
  ranking_consistente`, desde 17/11; antes repetia a home na mesma ordem)
  e, embaixo, o que mudou no Top 20 desde ontem (4 blocos, 5 linhas
  cada + "Ver mais"; `static/copiar_preco.js` (Ranking e item) só copia a "Encomenda sugerida" = maior encomenda + R$ 0,01, `encomenda.sugestao`; a barra de meta fica só na conta); Método = a explicação completa da nota (única fonte; as outras
  páginas resumem e linkam); Glossário = termos pra iniciante; Status =
  transparência da coleta; Mudanças = o que mudou no site, na linguagem
  de quem usa (sem jargão técnico interno).
- Home SEM os cartões "Maiores mudanças de nota hoje" (pedido do usuário,
  21/11; não recolocar). O Ranking mantém o "O que mudou no Top 20 desde
  ontem" e o aviso de que a encomenda sugerida não é previsão de lucro;
  o Status mantém as listas de itens sem preço novo e em espera, o ritmo
  da coleta e a hora do Top 20 (confirmado pelo usuário em 22/11).
- A home tem `<h1>` descritivo (oculto) e `<h2>` por seção; a frase-guia
  da nota leva a "Como a nota é calculada" (Método) e ao Glossário. O
  "Por quê" do item também leva ao Método.
- Marca no texto visível é "Lodout"; minúsculo só em URLs e domínios.
- Histórico da nota (`public_site/notas_historico.py`, 2026-11-17): o
  worker grava a nota de TODOS os itens a cada coleta (`completo=1`);
  35 dias inteiros, depois 1 foto por dia, até 400 dias. As fotos do
  `rankings.json` (só Top 20) entram como `completo=0`: servem para a
  comparação do Ranking, nunca para o gráfico de um item.

## Testes e comandos

O pytest isola `DATA_DIR` e bloqueia chamadas de rede. Testes que simulam rede
devem substituir o ponto de acesso por mock. A suíte é:

```bash
python -m pip install -r requirements-public-site.txt pytest
python -m pytest -q
```

O CI mede a cobertura (`pytest-cov`, mínimo 90% de `lodout/`; estava em
92% em 2026-11-17) e roda a regressão visual (`tests/visual/`): home,
ranking e item, mais a `/conta` de uma conta de exemplo e as janelas
"Vendi" e "Está anunciado". Mudou o visual de propósito? Regere a base com
o workflow `tests` (input `atualizar_baselines`) e commite os PNGs.

Para validar a página no navegador, use o preview local e confira desktop,
celular, console e fluxo de teclado. O deploy automático atualiza `web` depois
que o workflow de testes passa. O `worker` não recarrega código sozinho: só
recebe o build novo com `[restart-worker]` na mensagem do commit. Ao subir ele
espera o próximo ciclo contado do último registrado, então reiniciar fora de um
scan não gera requisição à Steam. Reiniciar no meio de um scan não perde mais a
coleta: o worker grava um checkpoint (`data/scan_parcial.json`) a cada 5 itens e
no SIGTERM, e ao subir retoma do ponto se o checkpoint tiver menos de 3 h.

## Publicar no `main` (várias sessões ao mesmo tempo)

Mais de uma sessão publica no `main` no mesmo dia. Em 21/11, uma publicação
sem rodar os testes deixou dois testes quebrados e as imagens visuais
desatualizadas. Regras para toda sessão:

1. **Antes de publicar**, traga o `main` atual (`git fetch origin main` e
   merge) e rode a suíte inteira **depois do merge**:
   `python -m pytest -q`. Só publique com tudo passando.
2. **Mudou o visual?** Na mesma rodada, regere as imagens-base (workflow
   `tests` com `atualizar_baselines`), confira as diferenças e commite só os
   PNGs que mudaram **antes** de publicar no `main`.
3. **Arquivos gerados não se editam à mão.** `static/og-image.png` sai de
   `scripts/gerar_og_image.py`, e um teste compara os dois. Os PNGs e o ICO
   da marca saem de `scripts/gerar_assets_marca.py`; a fonte é
   `static/logo-lodout.svg` e `static/logo-L.svg` (não recompiler raster à mão).
4. **Teste falhou?** Não apague nem afrouxe o teste para passar. Se ele
   protege uma decisão registrada (DESIGN.md, PRODUCT.md, este arquivo) e a
   mudança nova a contraria, pare e pergunte ao usuário qual vale.
5. **Nada de force-push ou amend no `main`.** Corrija com um commit novo.
6. **Changelog:** acrescente itens na entrada do dia. Não reescreva os itens
   de outra sessão.
7. **Depois do push**, acompanhe os workflows `tests` e `deploy` até o fim e
   confira a página mudada no ar (lodout.com).
8. **`[restart-worker]` pode se perder.** O `tests` cancela a rodada anterior
   quando chega outro push no `main` (concurrency), e o `deploy` só olha a
   mensagem do último commit. Se outro push passou na frente do seu, rode o
   workflow `deploy` à mão com `restart_worker` marcado (aconteceu em 22/11).
