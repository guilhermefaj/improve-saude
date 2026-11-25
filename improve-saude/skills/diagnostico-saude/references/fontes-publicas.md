# Fontes públicas

Todas abertas, sem chave nem login. Testadas em 25/11/2026. Os comandos ficam em `scripts/fontes.py`; cada um grava itens e séries em `evidencias.json` com fonte, período e link.

## O que já está automatizado

| Comando | Fonte | Itens gravados | Manhas |
|---|---|---|---|
| `municipio` | IBGE Localidades + MS (região de saúde) | `municipio` com código IBGE de 7 e 6 dígitos, microrregião, região imediata, região e macrorregião de saúde | Nome com acento ou sem acento funciona. Se houver mais de um, o script lista e sai com código 2. |
| `populacao` | IBGE, agregados v3, tabela 6579 (estimativa), variável 9324 | `pop` | Usa o ano mais recente publicado. |
| `financas --ano` | Tesouro/Siconfi: RREO Anexos 14 e 03, RGF Anexo 01 e DCA Anexo I-E | `asps_pct`, `asps_minimo`, `asps_valor`, `desp_saude_liq`, `desp_ab_liq`, `desp_hosp_liq`, `desp_farm_liq`, `desp_vigsan_liq`, `desp_vigepi_liq`, `desp_adm_liq`, `pessoal_rcl_pct`, `pessoal_limite_prudencial`, `pessoal_limite_maximo`, `rcl`, `emendas_individuais`, `repasse_acs_ace`, mais os cálculos `ab_part_pct`, `desp_saude_hab` e `pessoal_folga_pp` | O Anexo 12 do RREO vem vazio para municípios; por isso o % em saúde sai do Anexo 14. O script tenta do 6º ao 1º bimestre. Municípios pequenos entregam o RREO e o RGF **simplificados** (o RGF por semestre); o script tenta as duas formas, mas o Anexo 14 simplificado não traz o bloco da saúde: nesse caso o % em saúde vem de `siops`. A DCA do ano corrente só sai no ano seguinte: o script tenta o ano pedido e o anterior. Emendas individuais somam todas as áreas, não só a saúde. |
| `aps` | Relatório Público da APS (Ministério da Saúde) | `aps_cobertura_pct`, `aps_esf`, `aps_eap`, `sb_cobertura_pct`, `sb_equipes`, `acs_cobertura_pct`, `acs_ativos`, `aps_repasse_mes`, `aps_repasse_integral`, `aps_desconto_mes`, o cálculo `aps_desconto_pct` e as classificações em texto `aps_class_vinculo`, `aps_class_qualidade`, `aps_class_emulti`, `aps_estrato_equidade` | API sem documentação oficial (a mesma do painel). Os dados chegam com uns três meses de atraso: a cobertura usa a competência mais recente com dado e o pagamento, a parcela mais recente paga. A cobertura pode passar de 100% em município pequeno (equipes acima da população); o script avisa, e o documento deve dizer "cobertura total". A API não diz o motivo do desconto: nunca invente, sugira conferir no e-Gestor. |
| `siops --ano` | SIOPS (Ministério da Saúde), indicadores municipais | `siops_asps_pct`, `siops_desp_hab`, `siops_desp_total`, `siops_pessoal_pct`, `siops_medicamentos_pct`, `siops_terceiros_pct`, `siops_investimento_pct`, `siops_transf_pct`, `siops_uniao_pct` | Tenta o ano completo, depois o 1º semestre, depois o ano anterior; só sai o que foi homologado. Mede a despesa de outro jeito que o Siconfi: não some nem compare os dois como a mesma conta. |
| `repasses --ano` | Fundo Nacional de Saúde, consulta consolidada por bloco | `fns_custeio`, `fns_desconto`, `fns_mac`, `fns_aps`, `fns_vigilancia`, `fns_farm`, `fns_gestao`, `fns_investimento`, `fns_total` e os cálculos `fns_mac_pct`, `fns_aps_pct`, `fns_desconto_pct`, `fns_hab` | Valores brutos, por ano de pagamento; o ano corrente sai como "até dd/mm". Pode levar alguns segundos. O valor do FNS não bate com a receita do Siconfi (competência e regime diferentes). |
| `contexto` | IBGE: Censo 2022 (agregados v3) e IBGE Cidades | `esgoto_adequado_pct`, `agua_rede_pct`, `lixo_coletado_pct`, `alfabetizacao_pct`, `indice_envelhecimento`, `idade_mediana`, `pop_censo`, `pop_0a4`, `pop_60mais`, `pop_60mais_pct`, `mort_infantil`, `obitos_infantis`, `intern_diarreia`, `idhm` e as séries `mort_infantil_serie` e `intern_diarreia_serie` | No IBGE Cidades, "-" quer dizer zero. Em município pequeno a mortalidade infantil vem marcada como instável (poucos óbitos): prefira citar o número de óbitos. O Censo é de 2022 e o IDHM, de 2010: diga o ano. Alguns sistemas respondem em Latin-1; `_comum.py` já trata. |
| `cnes` | API Dados Abertos do MS, `cnes/estabelecimentos` | `cnes_total`, `cnes_sus_amb`, `cnes_hospitalar`, `cnes_tipo_XX` (01 postos, 02 UBS, 04 policlínicas, 05 hospitais gerais, 07 especializados, 15 mistas, 20 PS, 36 clínicas, 70 CAPS, 73 UPA) e o cálculo `hab_por_ubs` | `offset` é o **número da página** (20 itens por página), não o deslocamento. Municípios grandes levam alguns segundos. Inclui estabelecimentos privados; `cnes_sus_amb` filtra quem atende SUS. |
| `arbovirose --ano [--doenca]` | InfoDengue (Fiocruz/FGV) | série `{doenca}_sem_{ano}`, série `clima_temp_{ano}`, itens `{doenca}_casos_{ano}`, `{doenca}_nivel_atual`, `{doenca}_pico_{ano}`, `{doenca}_inc_{ano}` | A API devolve as semanas em ordem decrescente; o script reordena. O nível vai de 1 (verde) a 4 (vermelho). As semanas mais recentes ainda recebem notificações atrasadas. |

## Disponíveis, mas ainda não automatizadas

Use quando a dor pedir e a pessoa aceitar uma análise menos direta. Por enquanto, peça que ela baixe e envie o arquivo agregado.

- **Leitos e profissionais do CNES** (`assistencia-a-saude/cnes-leitos` e `cnes-profissionais`): exigem `nu_comp` (AAAAMM). Sem ele, a API devolve 2008. A contagem total sai mais rápido com `limit=1` e paginação; conferir os totais antes de automatizar.
- **Internações (SIH)**: `sih-procedimentos-hospitalares` filtra por `co_ibge` e `nu_ano`, mas leva cerca de 9 s por chamada.
- **Pares para comparação**: `macrorregiao-e-regiao-de-saude/municipio` lista os municípios da mesma região de saúde. Útil para comparar com vizinhos (rodando `financas` para cada um em outra pasta).

## Sem acesso automático

| Dado | Situação | O que sugerir |
|---|---|---|
| Cobertura vacinal oficial (%) | Só em painel (InfoMS) | A pessoa exporta a tabela do painel e envia |
| Produção da atenção básica (SISAB) e motivo dos descontos no e-Gestor | Sistemas com sessão e login | A pessoa exporta o relatório e envia |
| SIOPS por subfunção e repasses do FNS por ação | Só formulários | Usar `siops` e `repasses`, que cobrem os totais |
| TabNet | Responde, mas cai com consultas automáticas | Montar a tabela no site e enviar o CSV |
| Microdados (vacina, SIM, SINASC, notificações) | Registros individuais, sem filtro por município | Fora do escopo da conversa |

## Como pedir a planilha certa

Quando a dor pede um dado sem acesso automático, diga à pessoa exatamente o que baixar. Os caminhos abaixo são os de costume; se a tela estiver diferente, peça que ela descreva o que vê.

- **TabNet (DATASUS)**, para produção ambulatorial (SIA), internações (SIH), nascidos vivos e óbitos: em tabnet.datasus.gov.br, escolha o tema e a abrangência, marque o município em "Seleções disponíveis", escolha "Município" ou "Estabelecimento" na linha e "Mês" ou "Ano" na coluna, e use "Copia como .CSV" depois de mostrar a tabela.
- **SISAB**, para produção e indicadores da atenção básica: em sisab.saude.gov.br, abra os relatórios públicos, filtre pelo município e pelo período e exporte em planilha.
- **Cobertura vacinal**: no painel de vacinação do Ministério da Saúde (InfoMS), filtre o município e exporte a tabela.

`arquivo.py` já descarta as linhas de total e as notas de rodapé dessas exportações e aceita tabelas com um mês por coluna (`--colunas`). Cite o sistema de origem como fonte no documento.

## Rede bloqueada

`fontes.py` avisa com uma mensagem clara quando não alcança a fonte. O que fazer depende do ambiente:

- **Claude Code e Cowork:** a rede costuma estar liberada.
- **Codex:** o modo padrão desliga a rede dos comandos. Peça para rodar `fontes.py` com acesso à internet (a pessoa aprova na hora) ou explique como liberar de vez, no `~/.codex/config.toml`:

  ```toml
  [sandbox_workspace_write]
  network_access = true
  ```

- **Chat na nuvem (Claude.ai, ChatGPT):** o ambiente costuma bloquear sites do governo. Siga só com arquivos e relatos e diga isso no documento.
