# Fontes públicas

Todas abertas, sem chave nem login. Testadas em 24/11/2026. Os comandos ficam em `scripts/fontes.py`; cada um grava itens e séries em `evidencias.json` com fonte, período e link.

## O que já está automatizado

| Comando | Fonte | Itens gravados | Manhas |
|---|---|---|---|
| `municipio` | IBGE Localidades + MS (região de saúde) | `municipio` com código IBGE de 7 e 6 dígitos, microrregião, região imediata, região e macrorregião de saúde | Nome com acento ou sem acento funciona. Se houver mais de um, o script lista e sai com código 2. |
| `populacao` | IBGE, agregados v3, tabela 6579 (estimativa), variável 9324 | `pop` | Usa o ano mais recente publicado. |
| `financas --ano` | Tesouro/Siconfi: RREO Anexo 14 e DCA Anexo I-E | `asps_pct`, `asps_minimo`, `asps_valor`, `desp_saude_liq`, `desp_ab_liq`, `desp_hosp_liq`, `desp_farm_liq`, `desp_vigsan_liq`, `desp_vigepi_liq`, `desp_adm_liq`, mais os cálculos `ab_part_pct` e `desp_saude_hab` | O Anexo 12 do RREO vem vazio para municípios; por isso o % em saúde sai do Anexo 14. O script tenta do 6º ao 1º bimestre. A DCA do ano corrente só sai no ano seguinte: o script tenta o ano pedido e o anterior. |
| `cnes` | API Dados Abertos do MS, `cnes/estabelecimentos` | `cnes_total`, `cnes_sus_amb`, `cnes_hospitalar`, `cnes_tipo_XX` (01 postos, 02 UBS, 04 policlínicas, 05 hospitais gerais, 07 especializados, 15 mistas, 20 PS, 36 clínicas, 70 CAPS, 73 UPA) e o cálculo `hab_por_ubs` | `offset` é o **número da página** (20 itens por página), não o deslocamento. Municípios grandes levam alguns segundos. Inclui estabelecimentos privados; `cnes_sus_amb` filtra quem atende SUS. |
| `arbovirose --ano [--doenca]` | InfoDengue (Fiocruz/FGV) | série `{doenca}_sem_{ano}`, série `clima_temp_{ano}`, itens `{doenca}_casos_{ano}`, `{doenca}_nivel_atual`, `{doenca}_pico_{ano}`, `{doenca}_inc_{ano}` | A API devolve as semanas em ordem decrescente; o script reordena. O nível vai de 1 (verde) a 4 (vermelho). As semanas mais recentes ainda recebem notificações atrasadas. |

## Disponíveis, mas ainda não automatizadas

Use quando a dor pedir e a pessoa aceitar uma análise menos direta. Por enquanto, peça que ela baixe e envie o arquivo agregado.

- **Leitos e profissionais do CNES** (`assistencia-a-saude/cnes-leitos` e `cnes-profissionais`): exigem `nu_comp` (AAAAMM). Sem ele, a API devolve 2008. Os totais vieram inconsistentes no teste; conferir antes de automatizar.
- **Internações (SIH)**: `sih-procedimentos-hospitalares` filtra por `co_ibge` e `nu_ano`, mas leva cerca de 9 s por chamada.
- **Pares para comparação**: `macrorregiao-e-regiao-de-saude/municipio` lista os municípios da mesma região de saúde. Útil para comparar com vizinhos (rodando `financas` para cada um em outra pasta).

## Sem acesso automático

| Dado | Situação | O que sugerir |
|---|---|---|
| Cobertura vacinal oficial (%) | Só em painel (InfoMS) | A pessoa exporta a tabela do painel e envia |
| Produção da atenção básica (SISAB) e e-Gestor | Sistemas com sessão e login | A pessoa exporta o relatório e envia |
| SIOPS detalhado e repasses do FNS | Só formulários | Usar `financas`, que cobre o essencial |
| TabNet | Responde, mas cai com consultas automáticas | Montar a tabela no site e enviar o CSV |
| Microdados (vacina, SIM, SINASC, notificações) | Registros individuais, sem filtro por município | Fora do escopo da conversa |

## Rede bloqueada

`fontes.py` avisa com uma mensagem clara quando não alcança a fonte. O que fazer depende do ambiente:

- **Claude Code e Cowork:** a rede costuma estar liberada.
- **Codex:** o modo padrão desliga a rede dos comandos. Peça para rodar `fontes.py` com acesso à internet (a pessoa aprova na hora) ou explique como liberar de vez, no `~/.codex/config.toml`:

  ```toml
  [sandbox_workspace_write]
  network_access = true
  ```

- **Chat na nuvem (Claude.ai, ChatGPT):** o ambiente costuma bloquear sites do governo. Siga só com arquivos e relatos e diga isso no documento.
