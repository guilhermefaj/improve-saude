"""Lê um arquivo enviado pelo gestor (CSV ou XLSX) sem expor dados pessoais.

  python arquivo.py perfil ARQUIVO [--aba NOME]
      Mostra colunas, tipos e exemplos. Colunas com cara de dado pessoal
      (CPF, CNS, nome de pessoa, nascimento, endereço, telefone, e-mail)
      são marcadas e NUNCA têm valores exibidos.

  python arquivo.py agregar ARQUIVO --id ID --rotulo "..." [--aba NOME]
        [--soma COLUNA | --contar | --colunas "Jan,Fev,Mar" | --colunas "Jan..Dez"]
        [--por COLUNA] [--filtro COLUNA=VALOR ...] [--ano AAAA]
        [--unidade TEXTO] [--periodo TEXTO] [--casas N] [--minimo 5]
      Grava em evidencias.json um total (sem --por) ou uma série (com --por).
      --colunas soma cada coluna indicada e faz uma série com elas (tabelas com
      um mês por coluna); com --ano, "Jan", "Fev"... viram 2026-01, 2026-02...
      Não aceita agrupar ou filtrar por coluna pessoal. Ao contar registros, ou
      se o arquivo tem dado pessoal, grupos com menos de --minimo linhas viram
      "Outros" e um recorte com menos de --minimo linhas é recusado.

Linhas de total, subtotal e notas de rodapé ("Fonte:", "Notas:"), comuns nas
exportações do TabNet e do e-Gestor, são descartadas para não somar em dobro.

Só biblioteca padrão: o XLSX é lido direto do zip, sem openpyxl.
"""
import argparse
import csv
import io
import os
import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import _comum as c

# ------------------------------------------------------------------ leitura
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def _col_idx(ref):
    letras = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letras:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def ler_xlsx(caminho, aba=None):
    with zipfile.ZipFile(caminho) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        abas = [(s.get("name"), s.get(f"{{{_NS['r']}}}id")) for s in wb.find("m:sheets", _NS)]
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        alvo = {r.get("Id"): r.get("Target") for r in rels}
        nomes = [n for n, _ in abas]
        if aba and aba not in nomes:
            sys.exit(f"Aba '{aba}' não existe. Abas: {', '.join(nomes)}")
        nome, rid = next((x for x in abas if x[0] == aba), abas[0])
        caminho_aba = alvo[rid].lstrip("/")
        caminho_aba = caminho_aba if caminho_aba.startswith("xl/") else "xl/" + caminho_aba
        root = ET.fromstring(z.read(caminho_aba))
        linhas = []
        for row in root.iter(f"{{{_NS['m']}}}row"):
            vals = {}
            for cel in row.findall("m:c", _NS):
                t = cel.get("t")
                v = cel.find("m:v", _NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in cel.iter(f"{{{_NS['m']}}}t"))
                else:
                    val = v.text if v is not None else ""
                vals[_col_idx(cel.get("r"))] = val
            if vals:
                linhas.append([vals.get(i, "") for i in range(max(vals) + 1)])
        return nome, nomes, linhas


def ler_csv(caminho):
    bruto = open(caminho, "rb").read()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t|")
    except csv.Error:
        dialeto = csv.excel
        dialeto.delimiter = ";" if texto[:2000].count(";") > texto[:2000].count(",") else ","
    return list(csv.reader(io.StringIO(texto), dialeto))


_RODAPE = re.compile(r"^((sub)?\s*total\b|total geral|(fonte|fontes|nota|notas|obs|observacao|observacoes|legenda|elaboracao)\s*[:.]|"
                     r"\*|dados sujeitos)")
_OFICIAL = re.compile(r"datasus|tabnet|sia/sus|sih/sus|sinan|sinasc|\bsim\b|sisab|e-?gestor|siops|cnes|ministerio da saude")
# preenchidos a cada leitura: o que foi descartado e o que vinha antes do cabeçalho
DESCARTADAS, PREAMBULO = [], []


def ler(caminho, aba=None):
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm"):
        nome_aba, abas, linhas = ler_xlsx(caminho, aba)
    elif ext in (".csv", ".txt"):
        nome_aba, abas, linhas = None, [], ler_csv(caminho)
    elif ext == ".xls":
        sys.exit("Formato .xls antigo: peça ao gestor para salvar como .xlsx ou .csv.")
    else:
        sys.exit(f"Formato não suportado: {ext}. Use CSV ou XLSX. PDFs e textos: leia e resuma sem copiar dados pessoais.")
    linhas = [l for l in linhas if any(str(x).strip() for x in l)]
    if not linhas:
        sys.exit("Arquivo vazio.")
    # cabeçalho = primeira linha com pelo menos metade das células preenchidas
    i = 0
    for i, l in enumerate(linhas[:15]):
        if sum(1 for x in l if str(x).strip()) >= max(2, len(l) // 2):
            cab, dados = l, linhas[i + 1:]
            break
    else:
        i, cab, dados = 0, linhas[0], linhas[1:]
    PREAMBULO[:] = [" ".join(str(x).strip() for x in l if str(x).strip()) for l in linhas[:i]]
    cab = [str(h).strip() or f"coluna_{j + 1}" for j, h in enumerate(cab)]
    dados = [l + [""] * (len(cab) - len(l)) for l in dados]
    DESCARTADAS.clear()
    limpas = []
    for l in dados:
        primeira = next((str(x).strip() for x in l if str(x).strip()), "")
        if _RODAPE.match(_norm(primeira)):
            DESCARTADAS.append(primeira[:60])
        else:
            limpas.append(l)
    return nome_aba, abas, cab, [l[:len(cab)] for l in limpas]


def parece_oficial():
    """True se o preâmbulo ou o rodapé citam DATASUS, TabNet, e-Gestor etc."""
    return bool(_OFICIAL.search(_norm(" ".join(PREAMBULO + DESCARTADAS))))


# ------------------------------------------------------------------ LGPD
def _norm(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


_CAB_PESSOAL = re.compile(r"\b(cpf|cns|cartao.?sus|cartao.?nacional|rg|prontuario|nascimento|dt.?nasc|data.?nasc|"
                          r"endereco|logradouro|rua|telefone|celular|fone|whats|e.?mail|mae|pai|responsavel|paciente|"
                          r"usuario|cidadao|servidor|matricula|nis|pis)\b")
_CAB_NOME = re.compile(r"\bnome\b")
_NOME_INSTITUCIONAL = re.compile(r"(unidade|ubs|estabelecimento|municipio|bairro|procedimento|medicamento|vacina|"
                                 r"equipe|setor|cargo|servico|programa|regiao|distrito|doenca|cid|especialidade|exame)")
_VAL_PESSOAL = [
    ("CPF", re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")),
    ("CNS", re.compile(r"^[1-2789]\d{14}$")),
    ("e-mail", re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)),
    ("telefone", re.compile(r"^\(?\d{2}\)?\s?9?\d{4}-?\d{4}$")),
]


def coluna_pessoal(nome, valores):
    n = _norm(nome)
    if _CAB_PESSOAL.search(n):
        return f"nome da coluna ('{nome}')"
    if _CAB_NOME.search(n) and not _NOME_INSTITUCIONAL.search(n):
        return f"nome da coluna ('{nome}')"
    amostra = [str(v).strip() for v in valores if str(v).strip()][:200]
    for rot, rx in _VAL_PESSOAL:
        if amostra and sum(1 for v in amostra if rx.match(v)) >= max(1, len(amostra) // 5):
            return f"valores com formato de {rot}"
    return None


# ------------------------------------------------------------------ tipos
def numero(v):
    s = str(v).strip().replace("R$", "").replace("%", "").replace(" ", "")
    if not s:
        return None
    if re.match(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$", s) or re.match(r"^-?\d+,\d+$", s):
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def data(v):
    s = str(v).strip()
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%m/%Y", "%Y-%m", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    x = numero(s)  # data serial do Excel
    if x and 20000 < x < 60000 and float(x).is_integer():
        return datetime(1899, 12, 30) + timedelta(days=int(x))
    return None


def tipo_coluna(valores):
    vs = [v for v in valores if str(v).strip()]
    if not vs:
        return "vazia"
    if sum(1 for v in vs if numero(v) is not None) >= 0.9 * len(vs):
        if sum(1 for v in vs if data(v)) >= 0.9 * len(vs) and all(float(numero(v)).is_integer() for v in vs[:50]):
            return "data"
        return "número"
    if sum(1 for v in vs if data(v)) >= 0.9 * len(vs):
        return "data"
    return "categoria" if len(set(vs)) <= max(30, len(vs) // 10) else "texto"


_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _mes(rotulo):
    """'Jan', 'janeiro', 'JAN/26' -> 1..12; outra coisa -> None."""
    n = _norm(rotulo).strip()
    mt = re.match(r"^([a-z]{3})[a-z]*\.?(?:[/\- ]?(\d{2,4}))?$", n)
    return _MESES.get(mt.group(1)) if mt else None


def _colunas(pedido, cab):
    """'Jan,Fev,Mar' ou 'Jan..Dez' (na ordem do cabeçalho) -> lista de colunas."""
    if ".." in pedido:
        ini, fim = (x.strip() for x in pedido.split("..", 1))
        for x in (ini, fim):
            if x not in cab:
                sys.exit(f"Coluna '{x}' não existe. Colunas: {', '.join(cab)}")
        i, j = cab.index(ini), cab.index(fim)
        return cab[min(i, j):max(i, j) + 1]
    cols = [x.strip() for x in pedido.split(",") if x.strip()]
    faltam = [x for x in cols if x not in cab]
    if faltam:
        sys.exit(f"Coluna(s) {faltam} não existe(m). Colunas: {', '.join(cab)}")
    return cols


# ------------------------------------------------------------------ comandos
def cmd_perfil(a):
    nome_aba, abas, cab, dados = ler(a.arquivo, a.aba)
    print(f"Arquivo: {os.path.basename(a.arquivo)}" + (f" | aba: {nome_aba} (abas: {', '.join(abas)})" if abas else ""))
    print(f"Linhas de dados: {len(dados)} | colunas: {len(cab)}")
    pessoais = []
    for j, h in enumerate(cab):
        col = [l[j] for l in dados]
        motivo = coluna_pessoal(h, col)
        t = tipo_coluna(col)
        vazios = sum(1 for v in col if not str(v).strip())
        if motivo:
            pessoais.append(h)
            print(f"  [PESSOAL - oculto] {h} | motivo: {motivo}")
            continue
        distintos = len(set(str(v).strip() for v in col if str(v).strip()))
        ex = list(dict.fromkeys(str(v).strip()[:40] for v in col if str(v).strip()))[:3]
        print(f"  {h} | {t} | {distintos} valores distintos | {vazios} vazios | exemplos: {ex}")
    if DESCARTADAS:
        print(f"\nLinhas descartadas (total, subtotal ou nota de rodapé): {len(DESCARTADAS)} | {DESCARTADAS[:4]}")
    if parece_oficial():
        print("Parece exportação de sistema oficial (TabNet/DATASUS, e-Gestor ou similar). Cite o sistema como fonte no documento.")
    meses = [h for h in cab if _mes(h)]
    if len(meses) >= 3:
        print(f"Há {len(meses)} colunas de mês ({meses[0]} a {meses[-1]}). Para uma série mensal, use: "
              f"agregar --colunas \"{meses[0]}..{meses[-1]}\" --ano AAAA")
    if pessoais:
        print("\nATENÇÃO LGPD: este arquivo tem dados pessoais nas colunas marcadas. Eles não serão usados nem citados.")
        print("Use só totais e contagens agregadas. Grupos pequenos serão juntados em 'Outros'.")


def cmd_agregar(a):
    nome_aba, _, cab, dados = ler(a.arquivo, a.aba)
    idx = {h: j for j, h in enumerate(cab)}
    pessoais = {h for j, h in enumerate(cab) if coluna_pessoal(h, [l[j] for l in dados])}
    colunas = _colunas(a.colunas, cab) if a.colunas else []
    for col in [a.soma, a.por] + colunas + [f.split("=", 1)[0] for f in a.filtro]:
        if col and col not in idx:
            sys.exit(f"Coluna '{col}' não existe. Colunas: {', '.join(cab)}")
        if col and col in pessoais:
            sys.exit(f"Recusado: '{col}' é coluna com dado pessoal. Agregue por unidade, mês, faixa etária etc.")
    if colunas and a.por:
        sys.exit("--colunas já faz a série (uma coluna por ponto); use --filtro para escolher as linhas, não --por.")
    linhas = dados
    for f in a.filtro:
        col, val = f.split("=", 1)
        linhas = [l for l in linhas if str(l[idx[col]]).strip() == val]
    if not linhas:
        sys.exit("Nenhuma linha depois dos filtros.")
    # Contar registros é contar pessoas ou casos: grupos pequenos podem identificar alguém,
    # mesmo sem CPF ou nome no arquivo (um caso de uma doença num bairro, por exemplo).
    protege = bool(pessoais) or a.contar
    if protege and len(linhas) < a.minimo:
        sys.exit(f"Recusado: o recorte tem menos de {a.minimo} registros e poderia identificar alguém. "
                 f"Use um recorte maior ou diga no texto que são menos de {a.minimo}, sem o número exato.")

    def valor_de(grupo):
        if a.soma:
            return sum(numero(l[idx[a.soma]]) or 0 for l in grupo)
        return len(grupo)

    fonte = f"Arquivo enviado pela secretaria: {os.path.basename(a.arquivo)}" + (f" (aba {nome_aba})" if nome_aba else "")
    filtros = "; ".join(a.filtro)
    extra = {"filtros": filtros} if filtros else {}
    if DESCARTADAS:
        extra["linhas_descartadas"] = len(DESCARTADAS)
    ev = c.carregar(a.evidencias)
    if colunas:
        def periodo_col(h):
            m = _mes(h)
            d = data(h)
            if d:
                return d.strftime("%Y-%m")
            return f"{a.ano}-{m:02d}" if (m and a.ano) else h
        pontos = [(periodo_col(h), sum(numero(l[idx[h]]) or 0 for l in linhas)) for h in colunas]
        s = c.serie(ev, a.id, a.rotulo, a.unidade, fonte, None, "arquivo", pontos, casas=a.casas, **extra)
        c.item(ev, a.id + "_total", a.rotulo + " (total)", sum(v for _, v in pontos), a.unidade, fonte, None,
               a.periodo, "arquivo", casas=a.casas, **extra)
        print(f"Série {a.id}: {len(pontos)} colunas | total gravado como {a.id}_total")
        for p in s["pontos"][:40]:
            print(f"  {p['periodo']}: {p['fmt']}")
    elif not a.por:
        reg = c.item(ev, a.id, a.rotulo, valor_de(linhas), a.unidade, fonte, None, a.periodo, "arquivo", casas=a.casas, **extra)
        print(c.resumo(reg))
    else:
        j = idx[a.por]
        grupos = {}
        eh_data = tipo_coluna([x[j] for x in linhas]) == "data"
        for l in linhas:
            chave = str(l[j]).strip() or "(vazio)"
            d = data(chave) if eh_data else None
            if d:
                chave = d.strftime("%Y-%m")
            grupos.setdefault(chave, []).append(l)
        pontos, outros = [], []
        for chave in sorted(grupos):
            g = grupos[chave]
            if protege and len(g) < a.minimo:
                outros.extend(g)
            else:
                pontos.append((chave, valor_de(g)))
        if outros:
            pontos.append((f"Outros (grupos com menos de {a.minimo})", valor_de(outros)))
        s = c.serie(ev, a.id, a.rotulo, a.unidade, fonte, None, "arquivo", pontos, casas=a.casas, **extra)
        c.item(ev, a.id + "_total", a.rotulo + " (total)", valor_de(linhas), a.unidade, fonte, None, a.periodo, "arquivo", casas=a.casas, **extra)
        print(f"Série {a.id}: {len(pontos)} grupos | total gravado como {a.id}_total")
        for p in s["pontos"][:40]:
            print(f"  {p['periodo']}: {p['fmt']}")
    if DESCARTADAS:
        print(f"(descartadas {len(DESCARTADAS)} linhas de total ou rodapé: {DESCARTADAS[:3]})")
    c.salvar(ev, a.evidencias)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidencias")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("perfil"); s.add_argument("arquivo"); s.add_argument("--aba")
    s = sub.add_parser("agregar"); s.add_argument("arquivo"); s.add_argument("--aba")
    s.add_argument("--id", required=True); s.add_argument("--rotulo", required=True)
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--soma"); g.add_argument("--contar", action="store_true")
    g.add_argument("--colunas", help='colunas a somar, uma por ponto: "Jan,Fev,Mar" ou "Jan..Dez"')
    s.add_argument("--ano", type=int, help="ano dos meses em --colunas (Jan -> AAAA-01)")
    s.add_argument("--por"); s.add_argument("--filtro", action="append", default=[])
    s.add_argument("--unidade", default="registros"); s.add_argument("--periodo"); s.add_argument("--casas", type=int)
    s.add_argument("--minimo", type=int, default=5)
    a = p.parse_args()
    cmd_perfil(a) if a.cmd == "perfil" else cmd_agregar(a)


if __name__ == "__main__":
    main()
