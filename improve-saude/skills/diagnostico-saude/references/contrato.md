# Contrato do documento

O documento nasce de dois arquivos na pasta de trabalho da conversa. Os dois são JSON em UTF-8.

| Arquivo | Quem escreve | O que guarda |
|---|---|---|
| `evidencias.json` | **Só os scripts** (`fontes.py`, `arquivo.py`, `evidencias.py`) | Todos os números, cada um com fonte, período, link e origem |
| `documento.json` | **O agente** | O texto: insights em ordem de importância, citando números só como `{{id}}` |

Os resultados saem com o nome do município: `diagnostico-<municipio>.html` e `diagnostico-<municipio>.pdf`, mais a pasta `previa/` da revisão visual.

`renderizar.py` junta os dois e gera o HTML com a marca Improve. Antes disso, `checagem.py` recusa o documento se houver um número escrito à mão, um `{{id}}` que não existe ou um insight mal formado.

## evidencias.json

```json
{
  "versao": 1,
  "municipio": {"ibge": "3152501", "nome": "Pouso Alegre", "uf": "MG"},
  "itens": {
    "asps_pct": {
      "rotulo": "Receita própria aplicada em saúde",
      "valor": 19.28, "fmt": "19,3%", "unidade": "%",
      "periodo": "2024", "fonte": "Siconfi/Tesouro Nacional, RREO Anexo 14",
      "url": "https://apidatalake.tesouro.gov.br/...", "origem": "api",
      "registrado_em": "2026-11-25T10:00:00-03:00"
    }
  },
  "series": {
    "dengue_sem_2026": {
      "rotulo": "Casos de dengue por semana", "unidade": "casos", "fonte": "InfoDengue",
      "url": "...", "origem": "api",
      "pontos": [{"periodo": "SE 01", "valor": 12, "fmt": "12"}]
    }
  }
}
```

`origem` aceita quatro valores:

- `api`: o número veio de uma fonte pública.
- `arquivo`: veio de um total calculado a partir de um arquivo do gestor.
- `calculo`: é uma conta entre outras evidências. Nesse caso o item traz também `formula` e `depende_de`.
- `relato`: a pessoa disse o número na conversa. Sai no documento sublinhado com pontilhado e identificado como relato da secretaria.

Um item pode trazer `instavel` (texto): a taxa ou o percentual foi calculado sobre menos de 20 casos. O insight que usar esse item precisa dizer isso em `limites`, com as palavras "instável" ou "poucos casos", e a tabela final marca o número.

## documento.json

```json
{
  "titulo": "Pouso Alegre aplica mais que o mínimo em saúde, mas a atenção básica recebe a menor fatia",
  "subtitulo": "Diagnóstico para a coordenação da atenção primária",
  "para": {"cargo": "Coordenação da Atenção Primária", "orgao": "Secretaria Municipal de Saúde de Pouso Alegre"},
  "mensagem_principal": "A cidade aplicou {{asps_pct}} da receita própria em saúde, acima do mínimo de {{asps_minimo}}, mas só {{ab_part_pct}} da despesa liquidada foi para a atenção básica.",
  "contexto": {
    "dor": "Falta de profissionais nas UBS e pressão do prefeito por resultado.",
    "material_recebido": ["Planilha de atendimentos por UBS, jan a out de 2026 (agregada)"],
    "fontes_cruzadas": ["Siconfi/Tesouro", "CNES", "IBGE"]
  },
  "insights": [
    {
      "prioridade": 1,
      "tipo": "alerta",
      "titulo": "Atenção básica com a menor fatia da despesa",
      "destaque": "ab_part_pct",
      "achado": "Da despesa liquidada em saúde, {{ab_part_pct}} foi para a atenção básica.",
      "cruzamento": "Despesa por subfunção (Siconfi) com a rede de UBS (CNES)",
      "implicacao": "A falta de profissionais relatada pode ter raiz orçamentária, e não só de contratação.",
      "acoes": ["Levantar o custo de cada equipe de saúde da família em 2025"],
      "grafico": {"tipo": "barras", "itens": ["desp_ab_liq", "desp_hosp_liq", "desp_adm_liq"]},
      "evidencias": ["ab_part_pct", "desp_ab_liq", "desp_saude_liq"],
      "confianca": "alta",
      "limites": "A despesa por subfunção depende de como a contabilidade classifica cada gasto."
    }
  ],
  "hipoteses": ["A concentração na assistência hospitalar pode refletir o papel de polo regional do município."],
  "perguntas": ["Quanto da folha da atenção básica está lançada na administração geral?"],
  "proximos_passos": ["Comparar com três municípios do mesmo porte na macrorregião."],
  "convite": true
}
```

### Regras que a checagem impõe

- **Números só por `{{id}}`.** Todo `{{id}}` precisa existir em `itens` e é trocado pelo `fmt`. Fora dos marcadores, só passam:
  - contagens de 1 a 10 escritas sem unidade ("três UBS", "2 temas");
  - anos entre 1990 e 2040.
- **`prioridade`** começa em 1 e não se repete. O insight 1 ganha a página de destaque, o 2 e o 3 ganham meia página com gráfico, e os demais entram em lista compacta. Use de 1 a 6 insights.
- **Campos de referência.** `destaque`, `evidencias` e `grafico.itens` apontam para ids de `itens`. `grafico.serie` aponta para um id de `series`.
- **Gráfico** (opcional) tem três formas:
  - `{"tipo": "serie", "serie": "atend_mes"}`: linha ao longo do tempo;
  - `{"tipo": "barras", "serie": "faltas_ubs", "realce": "UBS Centro"}`: barras a partir de uma série por categoria (unidade, especialidade). `realce` é a categoria em laranja; sem ele, a maior. De 2 a 12 categorias;
  - `{"tipo": "barras", "itens": ["desp_ab_liq", "desp_hosp_liq"], "realce": "desp_ab_liq"}`: barras comparando itens da mesma unidade, de 2 a 8. A barra em laranja é a do `realce`; sem ele, a do `destaque` do insight, se estiver entre as barras; senão, a maior.
- **`ficticio`** (raiz, opcional): `true` põe a marca d'água "DADOS FICTÍCIOS · TESTE". Só para testes e demonstrações.
- **`tipo`** é um destes: `alerta`, `oportunidade`, `tendencia`, `comparacao`, `eficiencia`, `risco`.
- **`confianca`** é `alta`, `media` ou `baixa`. Use `baixa` quando o cruzamento depender de um arquivo do gestor sem data clara ou de uma amostra pequena.
- **Sem dado pessoal.** Nenhum campo de texto traz nome de paciente ou de servidor, CPF, CNS, endereço ou telefone. Em `para`, vão cargo e órgão, nunca o nome da pessoa.

### Tamanhos (para caber no layout)

| Campo | Limite |
|---|---|
| `titulo` | até 85 caracteres |
| `subtitulo` | até 70 caracteres |
| `mensagem_principal` | até 220 caracteres |
| `contexto.dor` | até 120 caracteres |
| `insights[].titulo` | até 70 caracteres |
| `achado` e `implicacao` do insight 1 | até 420 caracteres cada |
| `achado` e `implicacao` dos insights 2 e 3 (meia página) | até 240 e 290 caracteres |
| `acoes` | até 3 itens por insight |
| `hipoteses`, `perguntas`, `proximos_passos` | até 4 itens cada |

A checagem cobra esses limites antes de gerar o PDF. Eles valem para o caso comum; a capa e a página dos achados 2 e 3 ainda podem estourar se tudo vier no limite, e a revisão de layout diz quantos milímetros sobram.
