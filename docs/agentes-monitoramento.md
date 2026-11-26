# Agentes de monitoramento, diagnóstico e correção do scan

Runbook único para os três agentes que acompanham a coleta do Lodout.
Criado em 26/11/2026. Toda execução é **somente leitura na Steam**: nenhum
agente faz requisição direta de diagnóstico à Steam.

## Papéis

1. **Monitor** — automação `Lodout: monitor ponto-a-ponto do scan`, a cada
   10 min. Lê `https://lodout.com/api/health`, compara com o estado anterior
   e reporta nesta sessão: fatia, `start`, páginas, itens, 404, 429, retomada,
   Top 20 e fim de rodada. Detecta rodada nova por `catalogo.inicio_ts`;
   nunca trata estado herdado da rodada anterior como fim.
2. **Diagnóstico** — agente `general` disparado a cada 10 min (minuto 5).
   Só lê; nunca altera código, config, dados ou containers. Escreve
   `scratch/diagnosticos/<UTC>.md` quando há anomalia nova.
3. **Correção** — agente `general` disparado a cada 10 min (minuto 8).
   Só atua em casos da lista abaixo e no máximo 1 caso por execução.
   Escreve `scratch/correcoes/<mesmo nome>.md` com o resultado.
4. **Relatório** — automação no minuto 12 resume nesta sessão os arquivos
   novos de diagnóstico/correção.

## Fontes permitidas (todas locais ou do próprio site)

- `Invoke-RestMethod https://lodout.com/api/health` (e `/status` se útil).
- `ssh vm` para `docker ps`, `docker logs` e leitura de
  `/data/catalogo_estado.json`, `/data/scan_parcial.json`,
  `/data/scan_historico.json`. SQLite sempre em modo somente leitura.
- Código e testes em `C:\Users\pedro\Documents\galaseca`.

## Casos conhecidos (correção automática permitida)

| Caso | Arquivos normalmente envolvidos |
|---|---|
| 404 na busca por facetas do catálogo (retry, pulada, persistência do start) | `lodout/steam_api.py`, `lodout/public_site/catalogo.py`, testes |
| 429/disjuntor e pausa do worker | `lodout/steam_api.py`, `lodout/public_site/catalogo.py`, `lodout/public_site/worker.py`, testes |
| Checkpoint de coleta no meio do ciclo / restart | `lodout/scan_engine.py`, `lodout/public_site/worker.py`, testes |
| Retomada de fatias puladas (`retomar`/`fatias_puladas`) | `lodout/public_site/catalogo.py`, testes |

Correção automática = código + testes + changelog + `AGENTS.md` quando a
decisão muda, `git fetch origin main && git merge origin/main`, suíte completa
depois do merge, commit novo (nunca `amend`/force-push), `[restart-worker]`
na mensagem **somente** se o worker for afetado, acompanhar CI/deploy e
confirar `/api/health` no ar.

## Fora da lista — SEMPRE pedir aprovação

- Mudança de limites ou ritmo: `_MAX_404_MESMO_START`, `_ESPERA_APOS_404_S`,
  `_CATALOGO_FOLGA_S`, `steam_api.RATE_LIMIT_DELAY_S`,
  `LODOUT_ITENS_EXTRAS`, `LODOUT_TOP_RAPIDO_HORAS`, janelas e timeouts.
- Novas tags/facetas, alteração em `FATIAS`, exclusão ou reordenação de
  categorias do catálogo.
- Mudanças de relevância da busca do site (`/?q=`, `/api/sugestoes`,
  `texto_busca`, `nome_para_busca`, normalização, sinônimos, peso de
  resultados) — mesmo que pareçam pequenas.
- Config/deploy, segredos, dados persistidos, limpeza de `data/`, chamadas
  de rede à Steam, force-push/amend, reinício manual de container.
- Qualquer caso novo ou evidência insuficiente.

Nesses casos o agente de correção **não mexe em nada**: escreve
`scratch/correcoes/<nome>.md` com `resultado: pedir_aprovacao`, a pergunta
exata para o usuário e a proposta de mudança.

## Formato dos arquivos

Diagnóstico:

```markdown
---
classificacao: conhecido|novo
caso: 404_facias|429|ciclo_checkpoint|retomada|top20|outro
status: pendente|pedir_aprovacao
---
# Diagnóstico <UTC>
Evidências: ...
Causa provável: ...
Correção proposta: ...
```

Correção:

```markdown
---
resultado: aplicado|pedir_aprovacao|sem_acao
caso: <mesmo do diagnóstico>
---
# Correção <UTC>
Diagnóstico: <arquivo>
Mudanças: ...
Testes: ...
Commit/CI/deploy: ...
Verificação no ar: ...
```

Um diagnóstico com `status: pendente` só é considerado se ainda não existir
arquivo de correção com o mesmo nome. Nunca apague arquivos antigos: eles
são o histórico da investigação.
