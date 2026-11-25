# Mapa de dores

Ponto de partida para decidir o que buscar e o que cruzar. Não é lista fechada: se a dor não está aqui, pense em qual número mudaria a decisão da pessoa e procure a fonte mais próxima.

| Dor relatada | Arquivo que ajuda pedir | Fontes públicas | Cruzamentos que costumam render |
|---|---|---|---|
| Fila para especialista, demora para consulta | Fila por especialidade; agendamentos e faltas por unidade | `populacao`, `cnes` (policlínicas, clínicas, hospitais), `financas` | Fila por mil habitantes; faltas sobre agendamentos (agenda perdida); oferta especializada por habitante; parte da despesa que vai para atenção básica |
| Faltas de pacientes (absenteísmo) | Agendamentos, comparecimentos e faltas por unidade e mês | `populacao`, `cnes` | Taxa de faltas por unidade; faltas por equipe (relato do nº de equipes); meses com mais faltas |
| UBS cheia, falta de médico ou de equipe | Atendimentos por unidade e mês; nº de equipes (relato) | `populacao`, `cnes` (UBS, postos), `financas` | Habitantes por UBS; atendimentos por mil habitantes; despesa em atenção básica por habitante |
| Orçamento apertado, pressão do prefeito ou da Câmara | Execução orçamentária própria, se houver | `financas`, `populacao` | % da receita própria em saúde contra o mínimo de 15%; distribuição da despesa por área; despesa por habitante |
| Dengue, chikungunya, zika | Ações de campo (visitas, focos) por mês | `arbovirose`, `populacao` | Curva semanal contra temperatura; incidência por 100 mil; pico do ano contra a semana atual; ações de campo antes do pico |
| Urgência lotada, UPA ou pronto-socorro | Atendimentos de urgência por mês e classificação de risco | `cnes` (UPA, PS, hospitais), `populacao`, `financas` | Atendimentos de baixa gravidade na urgência contra oferta de UBS; habitantes por UPA |
| Saúde mental | Atendimentos do CAPS por mês | `cnes` (CAPS), `populacao` | Habitantes por CAPS; tendência mensal de atendimentos |
| Prestar contas ao conselho de saúde | O que ela já apresenta hoje | `financas`, `cnes`, `populacao` | Visão geral: % em saúde, despesa por área, rede, e o achado mais forte dos arquivos |

## Como transformar cruzamento em insight

Um cruzamento só vira insight quando passa nas três perguntas do passo 5 do SKILL.md. Exemplos:

- "Habitantes por UBS" sozinho é dado. Vira insight quando se liga à dor: "a UBS com mais faltas é a que atende mais moradores por equipe".
- "% em saúde acima do mínimo" sozinho é cumprimento de regra. Vira insight quando mostra para onde o dinheiro vai e o que isso tem a ver com a fila.
- Tendência de dengue em queda vira **oportunidade** ("janela para preparar o próximo verão"), não alerta.
