# Improve · Diagnóstico de Saúde Pública

Plugin do Claude para quem trabalha na gestão da saúde de um município. Você conta o problema do jeito que quiser, envia as planilhas que tiver, e o Claude:

1. lê os arquivos **sem expor dados pessoais** (só totais e contagens);
2. busca dados públicos do seu município: população (IBGE), gasto em saúde por área (Tesouro/Siconfi), rede de estabelecimentos (CNES) e dengue (InfoDengue);
3. cruza tudo com o que você contou;
4. entrega um PDF curto, em ordem de importância: o achado principal ganha uma página inteira, os dois seguintes ganham meia página, e os demais entram numa lista.

Todo número do documento vem de uma fonte identificada. Uma checagem automática recusa o documento se aparecer um número que não saiu dos dados. Antes da entrega, uma revisão de layout mede cada página e reprova palavra sozinha no fim de linha, título longo demais, página estourada e rótulo de gráfico cortado; depois disso, o Claude ainda olha o PDF página por página.

## Instalar

### Claude Code

```
/plugin marketplace add ENDERECO-DO-REPOSITORIO
/plugin install improve-saude@improve-gestao-publica
```

### Cowork (aplicativo de desktop)

Adicione o marketplace pelo endereço do repositório nas configurações de plugins e instale **improve-saude**.

### Claude.ai (navegador)

1. Compacte a pasta `improve-saude/skills/diagnostico-saude` em um `.zip`.
2. Em Configurações > Capacidades, ative a execução de código e envie o `.zip` em Skills.

No Claude.ai, o ambiente que roda os scripts costuma bloquear os sites do governo. A skill funciona, mas só com os arquivos que você enviar e com o que você contar; o documento avisa isso. Para cruzar com os dados públicos, use o Cowork ou o Claude Code.

## Como usar

Comece contando o problema. Exemplos:

- "Sou da coordenação da atenção básica de Pouso Alegre (MG). A fila de especialidades não para de crescer e as UBS vivem cheias. Segue a planilha de atendimentos."
- "Preciso mostrar ao conselho de saúde para onde vai o dinheiro da saúde do município."
- "Como está a dengue aqui em comparação com o começo do ano?"

O Claude pergunta só o que faltar (município, seu cargo, para quem é o documento) e devolve `diagnostico.pdf` e `diagnostico.html` na pasta de trabalho.

## O que precisa ter na máquina

- **Python 3.9 ou mais novo.** Os scripts usam só a biblioteca padrão; não há nada para instalar.
- **Chrome, Edge ou Chromium** para gerar o PDF, na sua própria máquina: o documento não é enviado a nenhum servidor. Sem navegador, o HTML sai pronto e você salva como PDF pela impressão.

## Privacidade

- Só dados agregados por município, unidade ou mês. Nenhum dado de paciente ou de servidor entra no documento.
- Colunas com CPF, CNS, nome de pessoa, nascimento, endereço, telefone ou e-mail são detectadas e nunca têm valores exibidos, nem usadas para agrupar.
- Grupos com menos de 5 pessoas viram "Outros".
- Os arquivos ficam na sua máquina (Claude Code e Cowork) ou na sua conversa (Claude.ai). As consultas às fontes públicas mandam só o código do município.

Detalhes em [lgpd.md](improve-saude/skills/diagnostico-saude/references/lgpd.md).

## Estrutura

```
.claude-plugin/marketplace.json        catálogo (marketplace "improve-gestao-publica")
improve-saude/
  .claude-plugin/plugin.json, icon.png
  skills/diagnostico-saude/
    SKILL.md                           o fluxo que o Claude segue
    references/                        contrato dos arquivos, fontes, mapa de dores, LGPD
    scripts/                           coleta, leitura de arquivos, checagem, HTML, PDF e revisão de layout
    assets/logo-improve.png
```

## Fontes

Os títulos usam a fonte Clash Display, carregada da Fontshare quando o documento é aberto, e o texto usa Inter (licença OFL), do Google Fonts. Sem internet, o documento cai para Arial.

Feito pela [Improve Business](https://improvebusiness.ai).
