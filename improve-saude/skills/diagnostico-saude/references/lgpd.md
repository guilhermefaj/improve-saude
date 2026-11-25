# LGPD na prática desta skill

A skill trabalha com **dados agregados**: totais e contagens por município, unidade de saúde, área da despesa ou mês. Ela não trata dado de pessoa. Isso vale para os dados públicos e, principalmente, para os arquivos que o gestor envia.

## Arquivos enviados pelo gestor

1. **Sempre comece pelo perfil.** `arquivo.py perfil` esconde os valores das colunas com cara de dado pessoal. Não abra o arquivo de outro jeito para "dar uma olhada".
2. **Colunas tratadas como pessoais:** CPF, CNS ou cartão SUS, RG, prontuário, data de nascimento, endereço, telefone, e-mail, nome da mãe ou do pai, paciente, usuário, servidor, matrícula, NIS ou PIS, e "nome" quando não é de unidade, bairro ou serviço. Valores com formato de CPF, CNS, e-mail ou telefone também marcam a coluna.
3. **Nunca agrupe nem filtre por essas colunas.** O script recusa. Não renomeie a coluna nem copie o arquivo para contornar.
4. **Grupos pequenos somem.** Ao contar registros (`--contar`), ou quando o arquivo tem coluna pessoal, grupos com menos de 5 linhas viram "Outros", e um recorte com menos de 5 é recusado. Vale mesmo para arquivo sem CPF nem nome: um caso de tuberculose num bairro pequeno pode apontar a pessoa. Isso evita que alguém seja reconhecido por eliminação (ex.: "o único caso de neurologia da UBS X"). No texto, diga "menos de 5", nunca o número exato.
5. **Nada de linha individual no chat nem no documento.** Nem como exemplo. Se precisar ilustrar, use o total.
6. **Arquivo privado fica de fora.** Se a pessoa disser que um arquivo é privado, interno ou que não deve ser usado no cruzamento, não use. Se o arquivo for um cadastro de servidores (lotação, contato, avaliação individual) e a dor não pedir uma contagem dele, não use.

## Dados públicos

- **CNES** lista consultórios de pessoa física com o nome do profissional. A skill grava só contagens por tipo de estabelecimento.
- **Microdados** (doses de vacina, nascidos vivos, óbitos, notificações de dengue) são registros individuais, mesmo anonimizados. A skill não baixa nem mostra esses registros. O InfoDengue já entrega a contagem semanal por município.

## No documento

- Em `para`, vão cargo e órgão. Nunca o nome da pessoa.
- Nenhum texto cita paciente, servidor, profissional, CPF, CNS, endereço ou telefone. A checagem procura esses formatos e reprova.
- Não compare profissionais entre si. Compare unidades, áreas ou períodos.
- O rodapé do documento diz que nenhum dado pessoal foi usado e que o texto teve apoio de IA. Não remova.
