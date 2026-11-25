# Gráficos que contam o achado

Use este guia quando for preencher `grafico` num insight. Ele segue as ideias de *Storytelling with Data*, de Cole Nussbaumer Knaflic: primeiro a mensagem, depois o gráfico, e só o que ajuda o leitor a entender.

## 1. Comece pela frase

Antes de escolher o tipo, escreva em uma frase o que o gráfico precisa provar. Essa frase vira o `titulo` do gráfico.

- Ruim: "Faltas por UBS". Diz o tema.
- Bom: "A UBS Centro lidera, mas todas as UBS perdem agenda". Diz a conclusão.

O título não leva número digitado: os números aparecem no próprio gráfico. Se a frase não fecha, o achado ainda não está claro, e um gráfico não vai resolver isso.

## 2. Escolha pelo que a frase compara

| A frase fala de… | Tipo | Exemplo |
|---|---|---|
| quem tem mais ou menos | `barras` | faltas por UBS, gasto por área |
| como mudou ao longo do tempo | `linha` (ou `serie`) | atendimentos por mês |
| como mudou, comparado a uma meta | `linha` com `referencia` | cobertura mensal diante da meta |
| de que partes é feito um todo | `composicao` | quem financia a saúde, SUS e plano |
| do valor cheio ao que sobrou | `cascata` | repasse integral, desconto, recebido |
| se está acima ou abaixo de um limite | `referencia` | gasto com pessoal e o limite da LRF |
| que fatia de 100% é uma coisa | `proporcao` | ocupação de leitos, cobertura |

Evite variar o tipo só para enfeitar. A variedade deve vir de mensagens diferentes. Não há pizza, rosca, 3D nem eixo duplo: eles distorcem a comparação.

## 3. Cor só no que importa

O renderizador pinta de laranja o que está em `realce` e deixa o resto em cinza. Aponte o `realce` para o elemento que a frase comenta:
- a barra da UBS citada no achado;
- o desconto na cascata;
- a parte que só usa o SUS.

Se tudo tem a mesma cor, o leitor não sabe para onde olhar. Sem `realce`, o laranja vai para o `destaque` do insight ou para o maior valor.

## 4. Rótulos diretos e curtos

O valor aparece em cima da barra ou ao lado da linha, sem legenda separada. Quando o rótulo da evidência for longo, use `rotulos` com até 30 caracteres: `{"aps_repasse_integral": "Valor integral"}`. Use o mesmo nome do texto: se o achado diz "UBS", o gráfico também diz "UBS".

## 5. Quando não fazer gráfico

- Um número sozinho já é o destaque do insight; não precisa de gráfico.
- Duas barras quase iguais, ou com 1 e 0, não mostram contraste.
- Os números não somam um todo: aí não cabe `composicao`.
- A cascata precisa fechar: início mais e menos os passos dá o fim. Se não fecha, falta um passo.

Deixar `grafico` de fora é melhor do que um gráfico que não prova nada.

## 6. Onde cada tipo cabe

- **Insights 1 a 3:** cabe qualquer tipo.
- **Lista compacta (prioridade 4 em diante):** só `composicao`, `referencia` ou `proporcao`. Eles saem em miniatura, numa linha.

A checagem confere as regras de cada tipo (unidades iguais, partes que somam 100%, cascata que fecha), e os campos estão no [contrato](contrato.md#gráficos).
