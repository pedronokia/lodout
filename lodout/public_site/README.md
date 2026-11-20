# Lodout — site público

Site público com dados do Steam Market e áreas pessoais opcionais para
portfólio, trades e watchlist. A autenticação usa Steam OpenID; o site nunca
recebe a senha ou o cookie de sessão da Steam.

## Dois processos, sempre

- **`web`** — serve as páginas (`server.py`/`wsgi.py`). Só LÊ dado já
  guardado (cache de preço, `scan_store.json`, SQLite). Nunca fala com a
  Steam numa requisição de visitante.
- **`worker`** (`worker.py`) — o ÚNICO processo que fala com a Steam.
  Escaneia a cada `LODOUT_WORKER_INTERVAL_HORAS` (default 6h),
  respeitando o mesmo limite de ~20 req/min de sempre.

Se só o `web` estiver no ar, o dashboard mostra "nenhum scan salvo" pra
sempre — o `worker` é obrigatório, não opcional.

## Variáveis de ambiente

| Variável | Pra quê | Default |
|---|---|---|
| `LODOUT_DATA_DIR` | Onde fica `public_site.db`, `scan_store.json`, `public_site_secret.key`, etc. **Precisa de disco persistente** — se o volume não sobrevive a um redeploy, toda conta/portfólio/trade é perdida. | `data/` do repositório |
| `PORT` | Porta que o `web` escuta — a maioria dos provedores injeta essa variável sozinha. | `8000` |
| `LODOUT_WORKER_INTERVAL_HORAS` | Intervalo entre ciclos do `worker`. | `6` |
| `LODOUT_PUBLIC_SITE_SECURE_COOKIES` | `1` em produção (HTTPS) pra marcar o cookie de sessão como `Secure`. Deixe **vazio/ausente** testando local em `http://`, senão o navegador descarta o cookie e o login nunca "pega". | ausente |
| `LODOUT_ADMIN_PASSWORD` | Senha do `/admin/login` (12+ caracteres), convertida em hash na subida. Em produção vem do secret `ADMIN_PASSWORD` do GitHub pelo deploy. | ausente |
| `LODOUT_ADMIN_PASSWORD_HASH` | Alternativa: o hash pronto (gerar com `scripts/hash_admin_password.py`); tem prioridade sobre a senha. Sem nenhum dos dois, a rota sempre devolve 404. | ausente |
| `LODOUT_ADMIN_DISCORD_WEBHOOK` | Webhook do Discord do DONO (não do usuário) pra alertar quando o worker passar `LODOUT_WORKER_ALERT_HORAS` sem trazer item nenhum -- ver `worker_alert.py`. | ausente (sem alerta) |
| `LODOUT_WORKER_ALERT_HORAS` | Horas sem sucesso antes do alerta acima disparar. | `3` |

## Rodar local (sem Docker)

```bash
python scripts/dev_public_site.py          # web, http://127.0.0.1:5061
python -m lodout.public_site.worker      # worker, noutro terminal
```

## Rodar com Docker

```bash
docker compose -f docker-compose.public-site.yml up --build
```

Sobe `web` (porta 8000) e `worker`, compartilhando um volume Docker pro
`LODOUT_DATA_DIR`. Pra produção de verdade (hospedagem com domínio e
HTTPS), ver a seção abaixo.

## Proteção contra abuso

`rate_limit.py` limita tentativas por IP em `/login`/`/login/callback`
(10/min) e nos formulários de `/conta` (30/min) — hand-rolled, em
memória, sem dependência nova (mesmo espírito do disjuntor de rate
limit da Steam). **Limitação real:** o contador é por PROCESSO, não
compartilhado entre workers do gunicorn — com `--workers 2` o limite
efetivo dobra (2x10/min, 2x30/min). Suficiente contra um script ingênuo
martelando uma rota; não é proteção contra um ataque distribuído de
verdade. Se o tráfego justificar mais rigor, trocar por um backend
compartilhado (Redis via Flask-Limiter, por exemplo) é o próximo passo
natural — não implementado aqui de propósito, pra não trazer
dependência/infra nova sem necessidade comprovada.

## Hospedagem — o que importa antes de escolher

1. **Precisa de dois processos** (`web` + `worker`) — confirme que o plano/
   provedor escolhido cobre os dois (muitos free tier só dão UM processo
   web, sem worker em background).
2. **Precisa de disco persistente** pro `LODOUT_DATA_DIR` — sem isso,
   toda conta criada por login Steam, todo portfólio/trade/watchlist some
   no próximo deploy ou reinício. Container efêmero (sem volume) só serve
   pro `web` de um dashboard público puro, sem login nenhum.
3. **HTTPS correto importa pro login.** `server.py` já aplica `ProxyFix`
   (confia em `X-Forwarded-Proto` de um proxy reverso), mas o provedor
   precisa terminar HTTPS de verdade — login Steam (OpenID) exige que o
   `realm`/`return_to` enviado bata com o protocolo real.
4. **Nenhum hosting específico está configurado aqui de propósito** — o
   `Dockerfile.public-site` roda em qualquer host que aceite uma imagem
   Docker com volume persistente (VPS com Docker, Fly.io, Render com disco
   pago, etc.). Termos de free tier mudam com frequência: confirme no
   provedor escolhido, no momento do deploy, que os itens 1-2 acima estão
   cobertos — não assuma pelo que este arquivo diz hoje.

## Deploy numa VM (ex. Oracle Cloud "Always Free")

Escolhido por ser a única opção pesquisada em 2026 que entrega os três
requisitos acima sem comprometer nada: VM de verdade (sem container
"dormindo"), disco persistente incluso, sem limite de tempo.
`docker-compose.oracle.yml` soma HTTPS automático (Caddy + Let's Encrypt)
por cima do `docker-compose.public-site.yml`, sem alterar `web`/`worker`.

1. Crie a instância (shape Ampere `VM.Standard.A1.Flex`, Ubuntu), com IP
   público. Abra as portas **80 e 443** (TCP) tanto na *Security List*/NSG
   da VCN (painel da Oracle) quanto no firewall do SO (`iptables`/`ufw`
   dentro da VM) — a Oracle filtra nos dois lugares, e esquecer um deles é
   o erro mais comum. **Não abra a 8000** — ela só precisa ser alcançável
   de dentro da própria VM (o Caddy fala com `web:8000` pela rede interna
   do Docker).
2. Instale Docker + plugin Compose na VM (`curl -fsSL https://get.docker.com | sh`
   e `apt install docker-compose-plugin`, ou o pacote equivalente da
   distro).
3. Aponte um domínio pro IP público da VM (registro DNS tipo A). Sem
   domínio próprio, um serviço gratuito como DuckDNS resolve — Caddy só
   precisa de um nome que resolva de verdade, não de um domínio pago.
4. Copie o repositório pra VM (`git clone`) e rode:
   ```bash
   SITE_DOMAIN=seudominio.exemplo docker compose \
     -f docker-compose.public-site.yml -f docker-compose.oracle.yml \
     up --build -d
   ```
   Na primeira subida o Caddy pede o certificado Let's Encrypt sozinho —
   não precisa de `certbot` nem configuração manual de TLS.
5. Confirme em `https://seudominio.exemplo/healthz` → `{"ok": true}`.

## Backup

`db_backup.py` roda a cada ciclo do `worker` (chamado de dentro de
`run_once`) e faz um backup rotativo LOCAL de `public_site.db` e de
`notas_historico.sqlite3` (histórico de até 400 dias de notas) em
`DATA_DIR/backups/`, via `sqlite3.Connection.backup()` (seguro mesmo com
o `web` escrevendo ao mesmo tempo) -- no máximo 1 por dia, guarda os
últimos 7 de cada. O mesmo ciclo também zipa `scanner_last.json`/
`scan_historico.json`/`rankings.json` (os JSON globais do dashboard) em
`DATA_DIR/backups/json-*.zip`, mesma cadência. Isso protege contra
corrupção/bug de aplicação.

Para proteger também contra perda total da VM, `.github/workflows/backup-offsite.yml`
roda 1x/dia (04:30 UTC), empacota o backup mais recente de cada família,
cifra na própria VM com AES-256-CBC + PBKDF2 (`scripts/backup_offsite.py`)
e envia via HTTPS PUT. Fica inativo sem erro até você configurar dois
secrets no GitHub:
- `BACKUP_UPLOAD_URL`: URL de escrita (ex.: uma *Pre-Authenticated Request*
  com permissão só de escrita num bucket privado do Oracle Object Storage
  Always Free de 20 GB, terminando em `/o/`).
- `BACKUP_PASSPHRASE`: senha longa (12+ caracteres) usada para cifrar e
  decifrar o pacote.

Para restaurar um arquivo baixado do bucket:
```bash
BACKUP_PASSPHRASE='sua-senha' python scripts/backup_offsite.py decifrar lodout-backup-AAAAMMDD-HHMMSS.tar.gz.enc -o restaurar.tar.gz
tar -xzf restaurar.tar.gz
```

## Monitoramento externo (uptime)

`.github/workflows/health-check.yml` roda de hora em hora fora da VM via
`scripts/check_site_health.py`, conferindo `/readyz` (site + banco) e
`/api/health` (frescor do último scan do worker). Se detectar queda ou
atraso prolongado, falha o job e envia alerta pro `ADMIN_DISCORD_WEBHOOK`
(independente do `worker`, que não conseguiria avisar se estivesse morto).
Além disso, `/healthz` e `/readyz` podem ser monitorados em serviços
como [UptimeRobot](https://uptimerobot.com/) ou
[Better Uptime](https://betteruptime.com/) para checagens por minuto.

## Deploy automático (CI/CD)

`.github/workflows/deploy.yml` roda depois que `tests.yml` passa em push
pra `main` (e também pode ser disparado manualmente via `workflow_dispatch`
com opções pra reiniciar `worker`, recriar `caddy` ou forçar `--build`).
Só reconstrói a imagem Docker quando `Dockerfile.public-site`,
`requirements-public-site.txt`, `entrypoint.sh` ou `scripts/minify_static.py`
mudam (ou com `[rebuild]` no commit) — nos demais deploys usa o bind mount
`./lodout:/app/lodout:ro` e recria o `web` em segundos. Em seguida limpa
imagens/cache Docker com mais de 7 dias, valida `/readyz` + `scripts/smoke_test.py`
e, só então, atualiza o `worker` se `[restart-worker]` foi pedido.
Precisa de 3 secrets no repositório (Settings → Secrets and variables → Actions):
`ORACLE_HOST`, `ORACLE_SSH_KEY` (conteúdo do `.key` da VM), `SITE_DOMAIN`.

## Painel admin

`/admin` mostra buscas populares, últimos ciclos, backups, latência por
rota, erros agregados e progresso do scan -- sem precisar de SSH. Login
de verdade em `/admin/login` (usuário único, é o dono do site -- sem
"esqueci a senha"): senha com hash via `werkzeug.security` (PBKDF2/
scrypt, zero dependência nova), sessão, sem token na URL (que vazava em
log/referrer na versão anterior). Gere o hash com:

```bash
python scripts/hash_admin_password.py
```

e cole o resultado em `LODOUT_ADMIN_PASSWORD_HASH` (env var). Sem
ela definida, `/admin` e `/admin/login` sempre devolvem 404 -- nunca
abre "sem senha" por padrão.

## Segurança (headers)

O Caddyfile aplica HSTS, Content-Security-Policy (`script-src 'self'` --
por isso todo JS da página fica em `static/app.js`, nunca inline, e as
violações chegam em `/api/csp-report`), `X-Content-Type-Options` e
`Referrer-Policy`. O 429 do rate limit e o 500 de erro interno têm
página própria (`429.html`/`500.html`), e todo 500 fica registrado em
`DATA_DIR/errors.log` (rotativo, 1MB x 3).

## Liveness vs. readiness

`/healthz` responde `{"ok": true}` sempre que o processo `web` está de
pé -- não confere mais nada. `/readyz` confere se dá pra abrir o banco
de contas (quando existe) sem exceção; devolve 503 com o motivo se
falhar. Um orquestrador que decide "pode receber tráfego" deveria
checar `/readyz`, não `/healthz`.

## Painel admin: métricas além dos backups

Além de backups/erros/buscas populares, o `/admin` mostra latência
média por rota (`latencia.py` -- em memória, por worker do gunicorn,
zera num restart), erros agregados por tipo e um gráfico de erros por
dia (`erro_stats.py`), e o progresso do ciclo de scan em andamento
(`scan_progress.py` -- sem isso, só dava pra ver olhando `docker logs`
do worker).

## Cache de ícone

`icon_cache.py` serve o ícone do item pelo próprio domínio
(`/icone/<hash>.jpg`), com cache em disco -- a primeira visita busca do
CDN da Steam (`steamstatic.com`, infraestrutura pública estática, sem
rate limit documentado -- diferente do market/inventory, que é o
endpoint sensível de sempre) e cacheia; todas as próximas são leitura
local. Falha de rede nunca derruba a página: cai no redirect pro CDN
direto.

## Scripts de apoio

- `scripts/check_env_drift.py [--servico web|worker|caddy|todos]` --
  compara as env vars esperadas contra o ambiente atual. Rodar via SSH
  na VM (`python scripts/check_env_drift.py --servico web`).
- `scripts/check_tls_expiry.py <dominio> [dias_limite]` -- confere
  quantos dias faltam pro certificado TLS expirar (conecta de verdade
  na porta 443, sem dependência nova). `.github/workflows/tls-check.yml`
  roda isto 1x/dia contra `SITE_DOMAIN` (secret já existente do
  `deploy.yml`) e falha a Action se faltar pouco tempo.
- `scripts/minify_static.py` -- minificação leve (remove comentário/
  espaço ocioso) de `style.css`/`app.js`, chamada só dentro do
  `Dockerfile.public-site` no build da imagem; nunca roda sobre o
  código-fonte do repositório.
- `scripts/smoke_test.py <url>` -- confirma que as rotas principais
  respondem com o status esperado (incluindo `/readyz` e proteção de
  `/admin`). Roda automaticamente no `deploy.yml` após cada publicação
  e também pode ser chamado manualmente (`python scripts/smoke_test.py https://seudominio.com`).
- `scripts/check_broken_links.py <url> [--limite N]` -- varre o site
  implantado a partir de `/`, seguindo só links do mesmo domínio, e
  reporta qualquer link que devolva 4xx/5xx. Mesmo espírito do
  `smoke_test.py`, mas acha link morto que a lista fixa de rotas dele
  não cobre (ex. um `/item/<nome>` que sumiu do scan mais recente).
- `scripts/load_test.py <url> [--rota /x -n N -c C]` -- teste de carga
  leve contra uma rota só-leitura do site já implantado; mede latência
  (min/mediana/p95/max) e taxa de erro. Não serve pra achar o limite de
  ruptura do servidor -- só confirma que a rota aguenta alguns usuários
  simultâneos sem degradar.

## Rollback de um deploy ruim

Se um deploy subir código quebrado, o jeito mais rápido de reverter
(assumindo deploy manual, não automático via `deploy.yml`):

```bash
# na VM, dentro de ~/skinvault
git log --oneline -5             # acha o commit bom anterior
git checkout <sha-do-commit-bom> -- .
SITE_DOMAIN=seudominio sudo -E docker compose \
  -f docker-compose.public-site.yml -f docker-compose.oracle.yml \
  up --build -d web
```

Depois, resolver o problema localmente, commitar a correção e fazer o
deploy de novo pra voltar pro HEAD do `main` -- não deixar a VM presa
num commit antigo por muito tempo (os próximos deploys manuais vão
partir desse estado "quase bom", não do que está no GitHub, até alguém
notar). `scripts/smoke_test.py` depois do rollback confirma que voltou
a funcionar antes de seguir em frente.

## Logs do container

`docker-compose.public-site.yml`/`docker-compose.oracle.yml` configuram
o driver `json-file` do Docker com `max-size: 10m, max-file: 3` pros
serviços `web`/`worker`/`caddy` -- sem isso, o log de stdout/stderr do
container (onde vai o access log do gunicorn e os `print()` do worker)
cresce sem limite no disco da VM. Separado do `errors.log` da aplicação
(que já rotacionava em 1MB) -- aquele é só os 500 registrados pelo
Flask; este é a saída bruta do processo.
