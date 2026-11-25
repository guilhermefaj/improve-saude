# Improve · Diagnóstico de Saúde Pública

Plugin para quem trabalha na gestão da saúde de um município. Funciona no Claude (Claude Code, Cowork e Claude.ai) e no Codex, e também pode ser enviado como skill ao ChatGPT. Você conta o problema do jeito que quiser, envia as planilhas que tiver, e o assistente:

1. lê os arquivos **sem expor dados pessoais** (só totais e contagens);
2. busca dados públicos do seu município: população (IBGE), gasto em saúde por área (Tesouro/Siconfi), rede de estabelecimentos (CNES) e dengue (InfoDengue);
3. cruza tudo com o que você contou;
4. entrega um PDF curto, em ordem de importância: o achado principal ganha uma página inteira, os dois seguintes ganham meia página, e os demais entram numa lista.

Todo número do documento vem de uma fonte identificada. Uma checagem automática recusa o documento se aparecer um número que não saiu dos dados.

## Onde funciona melhor

| Onde | Dados públicos | PDF |
|---|---|---|
| Claude Code, Cowork | sim | sim |
| Codex (CLI, app ou extensão de IDE) | sim, depois de liberar a internet | sim |
| Claude.ai, ChatGPT | em geral não: só seus arquivos e o que você contar | em geral sai o HTML, que você salva como PDF |

## Instalar

### Claude Code

```
/plugin marketplace add guilhermefaj/improve-saude
/plugin install improve-saude@improve-gestao-publica
```

### Cowork (aplicativo de desktop)

Adicione o marketplace `guilhermefaj/improve-saude` nas configurações de plugins e instale **improve-saude**.

### Codex

No terminal:

```
codex plugin marketplace add guilhermefaj/improve-saude
codex plugin add improve-saude@improve-gestao-publica
```

Ou, dentro do Codex, digite `/plugins` e instale **Improve · Saúde Pública**. Depois, abra uma conversa nova.

O Codex desliga a internet dos comandos por padrão. Quando a skill for buscar os dados públicos, aprove o pedido de acesso à rede. Para liberar de vez, acrescente ao `~/.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true
```

### Claude.ai (navegador)

1. Baixe este repositório e compacte a pasta `improve-saude/skills/diagnostico-saude` em um `.zip`.
2. Em Configurações > Capacidades, ative a execução de código e envie o `.zip` em Skills.

### ChatGPT

Skills existem nos planos Business, Enterprise, Edu e Healthcare, e o administrador do workspace precisa ativar o envio.

1. Compacte a pasta `improve-saude/skills/diagnostico-saude` em um `.zip`, como no Claude.ai.
2. No ChatGPT, abra **Skills**, escolha **Create** > **Upload from your computer** e envie o `.zip`.

No Claude.ai e no ChatGPT, o ambiente que roda os scripts costuma bloquear os sites do governo e não tem navegador para montar o PDF. A skill funciona, mas só com os arquivos que você enviar e com o que você contar; o documento avisa isso. Para cruzar com os dados públicos e receber o PDF pronto, use o Claude Code, o Cowork ou o Codex.

## Como usar

Comece contando o problema. Exemplos:

- "Sou da coordenação da atenção básica de Pouso Alegre (MG). A fila de especialidades não para de crescer e as UBS vivem cheias. Segue a planilha de atendimentos."
- "Preciso mostrar ao conselho de saúde para onde vai o dinheiro da saúde do município."
- "Como está a dengue aqui em comparação com o começo do ano?"

O assistente pergunta só o que faltar (município, seu cargo, para quem é o documento) e devolve `diagnostico.pdf` e `diagnostico.html` na pasta de trabalho.

## O que precisa ter na máquina

- **Python 3.9 ou mais novo.** Os scripts usam só a biblioteca padrão; não há nada para instalar.
- **Chrome, Edge ou Chromium** para gerar o PDF, na sua própria máquina: o documento não é enviado a nenhum servidor. Sem navegador, o HTML sai pronto e você salva como PDF pela impressão.

## Privacidade

- Só dados agregados por município, unidade ou mês. Nenhum dado de paciente ou de servidor entra no documento.
- Colunas com CPF, CNS, nome de pessoa, nascimento, endereço, telefone ou e-mail são detectadas e nunca têm valores exibidos, nem usadas para agrupar.
- Grupos com menos de 5 pessoas viram "Outros".
- Os arquivos ficam na sua máquina (Claude Code, Cowork e Codex) ou na sua conversa (Claude.ai e ChatGPT). As consultas às fontes públicas mandam só o código do município.

Detalhes em [lgpd.md](improve-saude/skills/diagnostico-saude/references/lgpd.md).

## Estrutura

```
.claude-plugin/marketplace.json        catálogo do Claude (marketplace "improve-gestao-publica")
.agents/plugins/marketplace.json       o mesmo catálogo para o Codex
improve-saude/
  .claude-plugin/plugin.json, icon.png
  .codex-plugin/plugin.json            manifesto do Codex
  skills/diagnostico-saude/
    SKILL.md                           o fluxo que o assistente segue (padrão Agent Skills)
    agents/openai.yaml                 nome e descrição da skill no Codex
    references/                        contrato dos arquivos, fontes, mapa de dores, LGPD
    scripts/                           coleta, leitura de arquivos, checagem, HTML e PDF
    assets/logo-improve.png
```

## Fontes

Os títulos usam a fonte Clash Display, carregada da Fontshare quando o documento é aberto, e o texto usa Inter (licença OFL), do Google Fonts. Sem internet, o documento cai para Arial.

Feito pela [Improve Business](https://improve.business). Fale com a gente: [contato@improve.business](mailto:contato@improve.business).

Código sob a [licença MIT](LICENSE). A marca e o logo da Improve Business não fazem parte da licença.
