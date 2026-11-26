# Fontes públicas

Todas abertas, sem chave nem login. Testadas em 25/11/2026. Os comandos ficam em `scripts/fontes.py`; cada um grava itens e séries em `evidencias.json` com fonte, período e link.

## O que já está automatizado

| Comando | Fonte | Itens gravados | Manhas |
|---|---|---|---|
| `municipio` | IBGE Localidades + MS (região de saúde) | `municipio` com código IBGE de 7 e 6 dígitos, microrregião, região imediata, região e macrorregião de saúde | Nome com acento ou sem acento funciona. Se houver mais de um, o script lista e sai com código 2. |
| `populacao` | IBGE, agregados v3, tabela 6579 (estimativa), variável 9324 | `pop` | Usa o ano mais recente publicado. |
| `financas --ano` | Tesouro/Siconfi: RREO Anexos 14 e 03, RGF Anexo 01 e DCA Anexo I-E | `asps_pct`, `asps_minimo`, `asps_valor`, `desp_saude_liq`, `desp_ab_liq`, `desp_hosp_liq`, `desp_farm_liq`, `desp_vigsan_liq`, `desp_vigepi_liq`, `desp_adm_liq`, `pessoal_rcl_pct`, `pessoal_limite_prudencial`, `pessoal_limite_maximo`, `rcl`, `emendas_individuais`, `repasse_acs_ace`, `rp_inscritos`, `rp_pagos`, `rp_cancelados`, `rp_saldo`, `rp_np_cancelados`, mais os cálculos `ab_part_pct`, `desp_saude_hab`, `pessoal_folga_pp` e `rp_cancelados_pct` | O Anexo 12 do RREO vem vazio para municípios; por isso o % em saúde sai do Anexo 14. O script tenta do 6º ao 1º bimestre. Municípios pequenos entregam o RREO e o RGF **simplificados** (o RGF por semestre); o script tenta as duas formas, mas o Anexo 14 simplificado não traz o bloco da saúde: nesse caso o % em saúde vem de `siops`. A DCA do ano corrente só sai no ano seguinte: o script tenta o ano pedido e o anterior. Emendas individuais e restos a pagar somam todas as áreas, não só a saúde: o RREO dos municípios não separa os restos a pagar por função. |
| `aps` | Relatório Público da APS (Ministério da Saúde) | `aps_cobertura_pct`, `aps_esf`, `aps_eap`, `sb_cobertura_pct`, `sb_equipes`, `acs_cobertura_pct`, `acs_ativos`, `aps_repasse_mes`, `aps_repasse_integral`, `aps_desconto_mes`, o cálculo `aps_desconto_pct` e as classificações em texto `aps_class_vinculo`, `aps_class_qualidade`, `aps_class_emulti`, `aps_estrato_equidade` | API sem documentação oficial (a mesma do painel). Os dados chegam com uns três meses de atraso: a cobertura usa a competência mais recente com dado e o pagamento, a parcela mais recente paga. A cobertura pode passar de 100% em município pequeno (equipes acima da população); o script avisa, e o documento deve dizer "cobertura total". A API não diz o motivo do desconto: nunca invente, sugira conferir no e-Gestor. |
| `siops --ano` | SIOPS (Ministério da Saúde), indicadores municipais | `siops_asps_pct`, `siops_desp_hab`, `siops_desp_total`, `siops_pessoal_pct`, `siops_medicamentos_pct`, `siops_terceiros_pct`, `siops_investimento_pct`, `siops_transf_pct`, `siops_uniao_pct` | Tenta o ano completo, depois o 1º semestre, depois o ano anterior; só sai o que foi homologado. Mede a despesa de outro jeito que o Siconfi: não some nem compare os dois como a mesma conta. |
| `repasses --ano` | Fundo Nacional de Saúde, consulta consolidada por bloco | `fns_custeio`, `fns_desconto`, `fns_mac`, `fns_aps`, `fns_vigilancia`, `fns_farm`, `fns_gestao`, `fns_investimento`, `fns_total` e os cálculos `fns_mac_pct`, `fns_aps_pct`, `fns_desconto_pct`, `fns_hab` | Valores brutos, por ano de pagamento; o ano corrente sai como "até dd/mm". Pode levar alguns segundos. O valor do FNS não bate com a receita do Siconfi (competência e regime diferentes). |
| `contexto` | IBGE: Censo 2022 (agregados v3), IBGE Cidades e PIB dos Municípios; Ministério da Saúde: população residente (SVSA) | `pop_svsa`, `pop_menor1`, `pop_60mais_svsa`, `pop_60mais_svsa_pct`, `pop_mulheres_25a64`, `pop_mulheres_50a69`, `pib`, `pib_per_capita`, `esgoto_adequado_pct`, `agua_rede_pct`, `lixo_coletado_pct`, `alfabetizacao_pct`, `indice_envelhecimento`, `idade_mediana`, `pop_censo`, `pop_0a4`, `pop_60mais`, `pop_60mais_pct`, `mort_infantil`, `obitos_infantis`, `intern_diarreia`, `idhm` e as séries `mort_infantil_serie` e `intern_diarreia_serie` | No IBGE Cidades, "-" quer dizer zero. Em município pequeno a mortalidade infantil vem marcada como instável (poucos óbitos): prefira citar o número de óbitos. O Censo é de 2022 e o IDHM, de 2010: diga o ano. Alguns sistemas respondem em Latin-1; `_comum.py` já trata. A população do Ministério da Saúde (SVSA) vai até 2025, por idade simples e sexo, e é o único endpoint dessa API com código IBGE de 7 dígitos. O PIB mais recente tem uns 2 anos de atraso; o PIB por habitante é o oficial do IBGE Cidades, porque não há estimativa de população para 2022 e 2023. |
| `agua --ano` | Ministério da Saúde, Sisagua (vigilância, parâmetros básicos) | `agua_analises`, `agua_coliformes_analises`, `agua_coliformes_presente`, `agua_ecoli_analises`, `agua_ecoli_presente` e os cálculos `agua_coliformes_pct`, `agua_ecoli_pct` | Uma linha por análise (dado ambiental). `offset` é o número da página de 1.000 linhas. Coliformes totais sozinhos não indicam contaminação fecal; E. coli indica. Com menos de 20 análises, o percentual sai como instável. O ano corrente sai como "até" o último mês com análise. |
| `cnes` | API Dados Abertos do MS, `cnes/estabelecimentos` | `cnes_total`, `cnes_sus_amb`, `cnes_hospitalar`, `cnes_tipo_XX` (01 postos, 02 UBS, 04 policlínicas, 05 hospitais gerais, 07 especializados, 15 mistas, 20 PS, 36 clínicas, 70 CAPS, 73 UPA) e o cálculo `hab_por_ubs` | `offset` é o **número da página** (20 itens por página), não o deslocamento. Municípios grandes levam alguns segundos. Inclui estabelecimentos privados; `cnes_sus_amb` filtra quem atende SUS. |
| `arbovirose --ano [--doenca]` | InfoDengue (Fiocruz/FGV) | série `{doenca}_sem_{ano}`, série `clima_temp_{ano}`, itens `{doenca}_casos_{ano}`, `{doenca}_nivel_atual`, `{doenca}_pico_{ano}`, `{doenca}_inc_{ano}` | A API devolve as semanas em ordem decrescente; o script reordena. O nível vai de 1 (verde) a 4 (vermelho). As semanas mais recentes ainda recebem notificações atrasadas. |
| `leitos` | CNES, API de dados abertos do MS (`assistencia-a-saude/cnes-leitos`) | `leitos_total`, `leitos_sus`, `leitos_uti`, `leitos_uti_sus`, `leitos_estab`, `leitos_obst_sus`, `leitos_ped_sus`, `leitos_sus_filantropicos`, os cálculos `leitos_sus_pct`, `leitos_sus_filantropicos_pct`, `leitos_sus_mil_hab`, `leitos_uti_sus_10mil_hab` e a série por categoria `leitos_sus_tipo` | A API devolve **uma linha por chamada**, seja qual for o `limit`; o script busca linha a linha, em paralelo. Capitais levam cerca de 1 minuto. A competência mais recente tem uns 4 meses de atraso. UTI = leitos com "UTI" no nome (UCI fica de fora). Município sem hospital sai com aviso. Polo regional atende vizinhos: o script avisa quando passa de 3 leitos SUS por mil habitantes. |
| `planos` | ANS, taxa de cobertura de planos (CSV de dados abertos) | `ans_benef`, `ans_benef_60mais` e os cálculos `ans_cobertura_pct`, `sus_exclusivo_pct`, `pop_sus_exclusivo` | Arquivo único de cerca de 21 MB com todos os municípios, guardado por 7 dias na pasta temporária. Traz só o ano; os beneficiários são os da data de atualização do arquivo, usada como período. A população do arquivo vem zerada: a cobertura usa a estimativa do IBGE (rode `populacao` antes). Beneficiário conta no município de residência; se passar de 100%, o script avisa. |
| `financiamento --ano` | Siconfi, MSC orçamentária (matriz de saldos contábeis) | `fin_saude_liq`, `fin_municipio`, `fin_uniao`, `fin_estado`, `fin_outras` com seus percentuais (`fin_*_pct`), `fin_anos_anteriores`, `fin_emendas_especiais` e a série por categoria `fin_origem` | Despesa liquidada (contas 6221303 e 6221304) na função 10. A origem sai da fonte de recursos padronizada pela STN: 500 e 501 município; 600 a 605, 631 e 706 União; 621, 632 e 710 Estado; o resto (659, convênios de outras entidades, operações de crédito) em "outras". O 1º dígito 2 indica saldo de anos anteriores. Para o ano corrente, usa o último mês entregue. O total difere um pouco da DCA e do SIOPS. |

## Disponíveis, mas ainda não automatizadas

Use quando a dor pedir e a pessoa aceitar uma análise menos direta. Por enquanto, peça que ela baixe e envie o arquivo agregado.

- **Profissionais do CNES** (`assistencia-a-saude/cnes-profissionais`): mesma API dos leitos, uma linha por chamada, mas são milhares de linhas por mês (6 mil em Pouso Alegre). Inviável na conversa.
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
- **Codex:** o modo padrão desliga a rede dos comandos. Rode `fontes.py` de novo pedindo a liberação (permissão elevada); a pessoa aprova na hora, sem configurar nada. Só se ela quiser liberar de vez, mostre o ajuste no `~/.codex/config.toml`:

  ```toml
  [sandbox_workspace_write]
  network_access = true
  ```

- **Chat na nuvem (Claude.ai, ChatGPT):** o ambiente costuma bloquear sites do governo. Siga só com arquivos e relatos e diga isso no documento.
