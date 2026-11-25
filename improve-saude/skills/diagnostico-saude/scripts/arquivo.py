"""Lê um arquivo enviado pelo gestor (CSV ou XLSX) sem expor dados pessoais.

  python arquivo.py perfil ARQUIVO [--aba NOME]
      Mostra colunas, tipos e exemplos. Colunas com cara de dado pessoal
      (CPF, CNS, nome de pessoa, nascimento, endereço, telefone, e-mail)
      são marcadas e NUNCA têm valores exibidos.

  python arquivo.py agregar ARQUIVO --id ID --rotulo "..." [--aba NOME]
        [--soma COLUNA | --contar] [--por COLUNA] [--filtro COLUNA=VALOR ...]
        [--unidade TEXTO] [--periodo TEXTO] [--casas N] [--minimo 5]
      Grava em evidencias.json um total (sem --por) ou uma série (com --por).
      Não aceita agrupar ou filtrar por coluna pessoal. Se o arquivo tem uma
      pessoa por linha, grupos com menos de --minimo linhas viram "Outros".

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
    for i, l in enumerate(linhas[:15]):
        if sum(1 for x in l if str(x).strip()) >= max(2, len(l) // 2):
            cab, dados = l, linhas[i + 1:]
            break
    else:
        cab, dados = linhas[0], linhas[1:]
    cab = [str(h).strip() or f"coluna_{j + 1}" for j, h in enumerate(cab)]
    dados = [l + [""] * (len(cab) - len(l)) for l in dados]
    return nome_aba, abas, cab, [l[:len(cab)] for l in dados]


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
    if pessoais:
        print("\nATENÇÃO LGPD: este arquivo tem dados pessoais nas colunas marcadas. Eles não serão usados nem citados.")
        print("Use só totais e contagens agregadas. Grupos pequenos serão juntados em 'Outros'.")


def cmd_agregar(a):
    nome_aba, _, cab, dados = ler(a.arquivo, a.aba)
    idx = {h: j for j, h in enumerate(cab)}
    pessoais = {h for j, h in enumerate(cab) if coluna_pessoal(h, [l[j] for l in dados])}
    for col in [a.soma, a.por] + [f.split("=", 1)[0] for f in a.filtro]:
        if col and col not in idx:
            sys.exit(f"Coluna '{col}' não existe. Colunas: {', '.join(cab)}")
        if col and col in pessoais:
            sys.exit(f"Recusado: '{col}' é coluna com dado pessoal. Agregue por unidade, mês, faixa etária etc.")
    linhas = dados
    for f in a.filtro:
        col, val = f.split("=", 1)
        linhas = [l for l in linhas if str(l[idx[col]]).strip() == val]
    if not linhas:
        sys.exit("Nenhuma linha depois dos filtros.")

    def valor_de(grupo):
        if a.soma:
            return sum(numero(l[idx[a.soma]]) or 0 for l in grupo)
        return len(grupo)

    fonte = f"Arquivo enviado pela secretaria: {os.path.basename(a.arquivo)}" + (f" (aba {nome_aba})" if nome_aba else "")
    filtros = "; ".join(a.filtro)
    extra = {"filtros": filtros} if filtros else {}
    ev = c.carregar(a.evidencias)
    if not a.por:
        reg = c.item(ev, a.id, a.rotulo, valor_de(linhas), a.unidade, fonte, None, a.periodo, "arquivo", casas=a.casas, **extra)
        print(c.resumo(reg))
    else:
        j = idx[a.por]
        grupos = {}
        for l in linhas:
            chave = str(l[j]).strip() or "(vazio)"
            d = data(chave) if tipo_coluna([x[j] for x in linhas]) == "data" else None
            if d:
                chave = d.strftime("%Y-%m")
            grupos.setdefault(chave, []).append(l)
        por_pessoa = bool(pessoais)
        pontos, outros = [], []
        for chave in sorted(grupos):
            g = grupos[chave]
            if por_pessoa and len(g) < a.minimo:
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
    c.salvar(ev, a.evidencias)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidencias")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("perfil"); s.add_argument("arquivo"); s.add_argument("--aba")
    s = sub.add_parser("agregar"); s.add_argument("arquivo"); s.add_argument("--aba")
    s.add_argument("--id", required=True); s.add_argument("--rotulo", required=True)
    g = s.add_mutually_exclusive_group(required=True); g.add_argument("--soma"); g.add_argument("--contar", action="store_true")
    s.add_argument("--por"); s.add_argument("--filtro", action="append", default=[])
    s.add_argument("--unidade", default="registros"); s.add_argument("--periodo"); s.add_argument("--casas", type=int)
    s.add_argument("--minimo", type=int, default=5)
    a = p.parse_args()
    cmd_perfil(a) if a.cmd == "perfil" else cmd_agregar(a)


if __name__ == "__main__":
    main()
