# Mapa de dores

Ponto de partida para decidir o que buscar e o que cruzar. Não é lista fechada: se a dor não está aqui, pense em qual número mudaria a decisão da pessoa e procure a fonte mais próxima.

| Dor relatada | Arquivo que ajuda pedir | Fontes públicas | Cruzamentos que costumam render |
|---|---|---|---|
| Fila para especialista, demora para consulta | Fila por especialidade; agendamentos e faltas por unidade | `populacao`, `cnes` (policlínicas, clínicas, hospitais), `leitos`, `planos`, `financas`, `repasses` | Fila por mil moradores que dependem só do SUS; faltas sobre agendamentos (agenda perdida); oferta especializada por habitante; quanto do repasse federal vai para média e alta complexidade |
| Faltas de pacientes (absenteísmo) | Agendamentos, comparecimentos e faltas por unidade e mês | `populacao`, `cnes`, `aps` | Taxa de faltas por unidade; faltas por equipe (equipes da `aps` ou relato); meses com mais faltas |
| UBS cheia, falta de médico ou de equipe | Atendimentos por unidade e mês | `aps`, `cnes` (UBS, postos), `financas`, `populacao` | Cobertura da atenção primária e de ACS; habitantes por UBS; folga de pessoal até o limite prudencial (há margem para contratar?) |
| Perda de recurso federal, financiamento da atenção primária | Nada obrigatório | `aps`, `repasses` | Desconto no repasse da APS e no custeio federal; classificação de vínculo e qualidade das equipes; o que recuperar o desconto pagaria |
| Orçamento apertado, pressão do prefeito ou da Câmara | Execução orçamentária própria, se houver | `financas`, `financiamento`, `siops`, `repasses`, `populacao` | % da receita própria em saúde contra o mínimo de 15%; quanto da despesa o município, a União e o Estado financiam; gasto por habitante; peso de pessoal e de terceiros; despesa com pessoal sobre a RCL; saldo de anos anteriores usado |
| Dengue, chikungunya, zika | Ações de campo (visitas, focos) por mês | `arbovirose`, `populacao`, `contexto` | Curva semanal contra temperatura; incidência por 100 mil; pico do ano contra a semana atual; lixo e esgoto do Censo; ações de campo antes do pico |
| Urgência lotada, UPA ou pronto-socorro | Atendimentos de urgência por mês e classificação de risco | `cnes` (UPA, PS, hospitais), `aps`, `leitos`, `planos`, `populacao` | Atendimentos de baixa gravidade na urgência contra cobertura da atenção primária; habitantes por UPA; leitos SUS e de UTI por habitante |
| Falta de leito, regulação, internação | Pedidos de internação ou de UTI pendentes, tempo de espera | `leitos`, `planos`, `populacao`, `repasses` | Leitos SUS e de UTI por mil moradores que dependem só do SUS; peso dos filantrópicos na oferta SUS; repasse de média e alta complexidade |
| População envelhecendo, doenças crônicas | Atendimentos de hipertensão e diabetes, se houver | `contexto`, `aps`, `siops` | Índice de envelhecimento e % com 60 anos ou mais contra cobertura da APS e gasto com medicamentos |
| Saúde materno-infantil | Pré-natal, partos, vacinação infantil | `contexto`, `aps` | Mortalidade infantil (série; em município pequeno, use o número de óbitos), crianças com menos de 1 ano e de 0 a 4 anos, cobertura da APS |
| Metas da atenção primária (preventivo, mamografia, vacinação) | Exames e doses feitos no período | `contexto`, `aps` | Feito sobre o público-alvo do Ministério da Saúde: mulheres de 25 a 64 anos (preventivo), de 50 a 69 (mamografia), crianças com menos de 1 ano |
| Saneamento e doenças de veiculação hídrica | Notificações de diarreia, se houver | `contexto`, `agua` | Esgoto, água e lixo do Censo contra internações por diarreia; análises da água com coliformes e E. coli |
| Saúde mental | Atendimentos do CAPS por mês | `cnes` (CAPS), `populacao` | Habitantes por CAPS; tendência mensal de atendimentos |
| Prestar contas ao conselho de saúde | O que ela já apresenta hoje | `financas`, `financiamento`, `siops`, `repasses`, `aps`, `cnes`, `populacao` | Visão geral: % em saúde, gasto por habitante, de onde vem o dinheiro, cobertura da atenção primária, e o achado mais forte dos arquivos |

## Como transformar cruzamento em insight

Um cruzamento só vira insight quando passa nas três perguntas do passo 5 do SKILL.md. Exemplos:

- "Habitantes por UBS" sozinho é dado. Vira insight quando se liga à dor: "a UBS com mais faltas é a que atende mais moradores por equipe".
- "% em saúde acima do mínimo" sozinho é cumprimento de regra. Vira insight quando mostra para onde o dinheiro vai e o que isso tem a ver com a fila.
- "Desconto no repasse da APS" vira insight quando se traduz em capacidade: quanto isso dá por ano e o que pagaria (com o cálculo registrado em `evidencias.py`).
- "Cobertura da APS de 77%" vira insight quando se liga à urgência lotada ou à fila: quem não tem equipe de referência procura a UPA.
- "Leitos SUS por mil habitantes" muda de sentido com `planos`: dividido pelos moradores que dependem só do SUS, mostra a oferta real para quem não tem alternativa.
- Tendência de dengue em queda vira **oportunidade** ("janela para preparar o próximo verão"), não alerta.
