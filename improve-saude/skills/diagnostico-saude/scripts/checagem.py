"""Confere documento.json contra evidencias.json antes de renderizar.

  python checagem.py [--documento documento.json] [--evidencias evidencias.json]

Sai com código 0 se estiver tudo certo. Caso contrário, lista cada problema
com o campo e o trecho, para o agente corrigir e rodar de novo.

Regra: o texto cita números só como {{id}}. Fora dos marcadores, passam apenas
contagens de 1 a 10 sem unidade ("três UBS", "2 temas") e anos de 1990 a 2040.
"""
import argparse
import json
import re
import sys

import _comum as c

MARCADOR = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")
NUMERO = re.compile(r"(?<![\w{])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)(\s*(?:%|º|ª|°|p\.p\.)?)(\s*(?:pontos?|por mil|por cento|mil|milh(?:ão|ões)|bilh(?:ão|ões)|reais|habitantes|casos)?)", re.I)
TIPOS = {"alerta", "oportunidade", "tendencia", "comparacao", "eficiencia", "risco"}
CONFIANCA = {"alta", "media", "baixa"}
PESSOAL = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b[1-2789]\d{14}\b|[^@\s]+@[^@\s]+\.[a-z]{2,}|\(?\d{2}\)?\s?9\d{4}-?\d{4}", re.I)
# a capa e a página dos achados 2 e 3 são as que mais estouram: os limites delas são menores
LIMITES = {"titulo": 85, "subtitulo": 70, "mensagem_principal": 220, "contexto.dor": 120,
           "insights.titulo": 70, "achado": 420, "implicacao": 420, "sec.achado": 240, "sec.implicacao": 290}


def textos(doc):
    """(caminho, texto) de todo campo de texto livre."""
    def campo(caminho, v):
        if isinstance(v, str):
            yield caminho, v
        elif isinstance(v, list):
            for i, x in enumerate(v):
                yield from campo(f"{caminho}[{i}]", x)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k == "grafico" and isinstance(x, dict):  # do gráfico, só o título e os rótulos são texto
                    yield from campo(f"{caminho}.grafico.titulo", x.get("titulo"))
                    for i, r in (x.get("rotulos") or {}).items():
                        yield from campo(f"{caminho}.grafico.rotulos.{i}", r)
                    continue
                if k in ("destaque", "evidencias", "tipo", "confianca", "prioridade"):
                    continue
                yield from campo(f"{caminho}.{k}" if caminho else k, x)
    yield from campo("", doc)


GRAFICOS = {"barras", "serie", "linha", "composicao", "cascata", "referencia", "proporcao"}
GRAFICOS_LISTA = {"composicao", "referencia", "proporcao"}  # cabem numa linha da lista compacta


def checar_grafico(g, p, prioridade, itens, series, exige):
    """Regras de cada tipo de gráfico (ver references/visualizacao.md)."""
    tipo = g.get("tipo")
    if tipo not in GRAFICOS:
        exige(False, f"{p}.grafico.tipo deve ser um de: {', '.join(sorted(GRAFICOS))}")
        return
    if (prioridade or 0) > 3:
        exige(tipo in GRAFICOS_LISTA, f"{p}.grafico: na lista compacta (prioridade 4 em diante) use {', '.join(sorted(GRAFICOS_LISTA))} ou tire o gráfico")
    ids = list(g.get("itens") or []) + [g[k] for k in ("item", "inicio", "fim", "referencia") if g.get(k)]
    passos = [x if isinstance(x, dict) else {"id": x} for x in g.get("passos") or []]
    ids += [x.get("id") for x in passos] + list(g.get("marcos") or [])
    faltam = [x for x in ids if x not in itens]
    exige(not faltam, f"{p}.grafico: ids inexistentes em evidencias {faltam}")
    if faltam:
        return
    exige(all(isinstance(itens[x]["valor"], (int, float)) for x in ids), f"{p}.grafico: item sem valor numérico")
    unidades = {itens[x]["unidade"] for x in ids}
    if g.get("titulo") is not None:
        exige(isinstance(g["titulo"], str) and len(g["titulo"]) <= 80, f"{p}.grafico.titulo: texto de até 80 caracteres")
    for k, r in (g.get("rotulos") or {}).items():
        exige(k in ids, f"{p}.grafico.rotulos: {k!r} não está no gráfico")
        exige(isinstance(r, str) and len(r) <= 30, f"{p}.grafico.rotulos.{k}: até 30 caracteres")

    if tipo in ("serie", "linha"):
        s = series.get(g.get("serie"))
        exige(s is not None, f"{p}.grafico.serie inexistente: {g.get('serie')!r}")
        if s is not None and g.get("referencia"):
            exige(itens[g["referencia"]]["unidade"] == s.get("unidade"), f"{p}.grafico.referencia: unidade diferente da série")
    elif tipo == "barras" and g.get("serie"):
        s = series.get(g["serie"])
        exige(s is not None, f"{p}.grafico.serie inexistente: {g.get('serie')!r}")
        exige(s is None or 2 <= len(s["pontos"]) <= 12, f"{p}.grafico: barras de série pedem de 2 a 12 pontos")
    elif tipo == "barras":
        exige(2 <= len(g.get("itens") or []) <= 8, f"{p}.grafico.itens: de 2 a 8 itens")
        exige(len(unidades) <= 1, f"{p}.grafico: barras com unidades diferentes {sorted(unidades)}")
    elif tipo == "composicao":
        ids_ = g.get("itens") or []
        exige(2 <= len(ids_) <= 6, f"{p}.grafico.itens: composição pede de 2 a 6 partes")
        exige(len(unidades) <= 1, f"{p}.grafico: partes com unidades diferentes {sorted(unidades)}")
        exige(all(itens[x]["valor"] >= 0 for x in ids_), f"{p}.grafico: composição não aceita parte negativa")
        if unidades == {"%"}:
            soma = sum(itens[x]["valor"] for x in ids_)
            exige(97 <= soma <= 103, f"{p}.grafico: as partes em % somam {c.fmt_num(soma, 1)}, não 100; use as partes de um mesmo todo")
    elif tipo == "cascata":
        exige(g.get("inicio") and g.get("fim") and 1 <= len(passos) <= 4, f"{p}.grafico: cascata pede inicio, fim e de 1 a 4 passos")
        exige(all(x.get("sinal", "-") in ("+", "-") for x in passos), f"{p}.grafico.passos: sinal deve ser '+' ou '-'")
        exige(len(unidades) <= 1, f"{p}.grafico: cascata com unidades diferentes {sorted(unidades)}")
        if g.get("inicio") and g.get("fim"):
            conta = itens[g["inicio"]]["valor"] + sum((1 if x.get("sinal", "-") == "+" else -1) * itens[x["id"]]["valor"] for x in passos)
            fim = itens[g["fim"]]["valor"]
            exige(abs(conta - fim) <= 0.01 * max(abs(fim), abs(itens[g["inicio"]]["valor"]), 1),
                  f"{p}.grafico: a cascata não fecha (início e passos dão {c.fmt_num(conta, 1)}, o fim é {c.fmt_num(fim, 1)})")
    elif tipo == "referencia":
        exige(g.get("item") and 1 <= len(g.get("marcos") or []) <= 3, f"{p}.grafico: referência pede item e de 1 a 3 marcos")
        exige(len(unidades) <= 1, f"{p}.grafico: item e marcos com unidades diferentes {sorted(unidades)}")
    elif tipo == "proporcao":
        exige(g.get("item") and itens[g["item"]]["unidade"] == "%" and 0 <= itens[g["item"]]["valor"] <= 100,
              f"{p}.grafico: proporção pede um item em % entre 0 e 100")


def checar(doc, ev):
    problemas, divergencias = [], []
    itens, series = ev.get("itens", {}), ev.get("series", {})
    exige = lambda cond, msg: (None if cond else problemas.append(msg))

    # ---------- estrutura
    exige(isinstance(doc.get("titulo"), str) and doc["titulo"].strip(), "titulo é obrigatório")
    exige(isinstance(doc.get("mensagem_principal"), str) and doc["mensagem_principal"].strip(), "mensagem_principal é obrigatória")
    ins = doc.get("insights") or []
    exige(1 <= len(ins) <= 6, f"insights: use de 1 a 6 (vieram {len(ins)})")
    prios = [i.get("prioridade") for i in ins]
    exige(sorted(prios) == list(range(1, len(ins) + 1)), f"prioridade deve ser 1..{len(ins)} sem repetir (veio {prios})")
    for n, i in enumerate(ins):
        p = f"insights[{n}]"
        exige(i.get("tipo") in TIPOS, f"{p}.tipo inválido: {i.get('tipo')!r} (use {', '.join(sorted(TIPOS))})")
        exige(i.get("confianca") in CONFIANCA, f"{p}.confianca inválida: {i.get('confianca')!r}")
        for k in ("titulo", "achado", "implicacao", "cruzamento"):
            exige(isinstance(i.get(k), str) and i[k].strip(), f"{p}.{k} é obrigatório")
        exige(i.get("destaque") in itens, f"{p}.destaque não existe em evidencias: {i.get('destaque')!r}")
        for e in i.get("evidencias") or []:
            exige(e in itens or e in series, f"{p}.evidencias: id inexistente {e!r}")
        exige(len(i.get("acoes") or []) <= 3, f"{p}.acoes: no máximo 3")
        g = i.get("grafico")
        if g:
            checar_grafico(g, p, i.get("prioridade"), itens, series, exige)
    # ---------- números instáveis (taxa sobre poucos casos) precisam de aviso no próprio insight
    for n, i in enumerate(ins):
        citados = {mt.group(1) for _, s in textos(i) for mt in MARCADOR.finditer(s)}
        citados |= {i.get("destaque")} | set(i.get("evidencias") or [])
        instaveis = sorted(x for x in citados if x in itens and itens[x].get("instavel"))
        lim = c.norm(i.get("limites") or "")
        if instaveis and not re.search(r"instav|poucos casos|numero pequeno|numeros pequenos|poucos registros", lim):
            problemas.append(f"insights[{n}] usa número instável ({', '.join(instaveis)}): diga em 'limites' que a conta "
                             "se apoia em poucos casos (use a palavra 'instável' ou 'poucos casos')")
    for k in ("hipoteses", "perguntas", "proximos_passos"):
        exige(len(doc.get(k) or []) <= 4, f"{k}: no máximo 4 itens")
    para = doc.get("para") or {}
    exige(not para.get("nome"), "para.nome não é permitido: use cargo e órgão")

    # ---------- tamanhos (contados sem os marcadores)
    def tam(s):
        return len(MARCADOR.sub("00,0%", s or ""))
    def limite(caminho, s, chave):
        if tam(s) > LIMITES[chave]:
            problemas.append(f"{caminho} tem {tam(s)} caracteres; o limite é {LIMITES[chave]} para caber na página")
    limite("titulo", doc.get("titulo"), "titulo")
    limite("subtitulo", doc.get("subtitulo"), "subtitulo")
    limite("mensagem_principal", doc.get("mensagem_principal"), "mensagem_principal")
    limite("contexto.dor", (doc.get("contexto") or {}).get("dor"), "contexto.dor")
    for n, i in enumerate(ins):
        limite(f"insights[{n}].titulo", i.get("titulo"), "insights.titulo")
        sec = i.get("prioridade") in (2, 3)  # meia página cada
        for k in ("achado", "implicacao"):
            limite(f"insights[{n}].{k}" + (" (achado 2 ou 3, meia página)" if sec else ""), i.get(k), ("sec." if sec else "") + k)

    # ---------- marcadores e números soltos
    for caminho, s in textos(doc):
        for mt in MARCADOR.finditer(s):
            if mt.group(1) not in itens:
                divergencias.append({"campo": caminho, "problema": f"{{{{{mt.group(1)}}}}} não existe em evidencias.json"})
        limpo = MARCADOR.sub(" ", s)
        if PESSOAL.search(limpo):
            problemas.append(f"{caminho}: parece conter dado pessoal (CPF, CNS, e-mail ou telefone)")
        for mt in NUMERO.finditer(limpo):
            num, suf, un = mt.group(1), (mt.group(2) or "").strip(), (mt.group(3) or "").strip()
            antes = limpo[max(0, mt.start() - 3):mt.start()]
            inteiro = int(num) if num.isdigit() else None
            if inteiro is not None and not suf and not un and not re.search(r"R\$\s*$", antes):
                if 1 <= inteiro <= 10 or 1990 <= inteiro <= 2040:
                    continue
            ini = max(0, mt.start() - 35)
            divergencias.append({"campo": caminho, "problema": f"número escrito à mão: '{num}{suf}{(' ' + un) if un else ''}'",
                                 "trecho": limpo[ini:mt.end() + 35].strip()})
    return {"ok": not problemas and not divergencias, "problemas": problemas, "divergencias": divergencias}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--documento", default="documento.json")
    p.add_argument("--evidencias")
    a = p.parse_args()
    with open(a.documento, encoding="utf-8") as f:
        doc = json.load(f)
    r = checar(doc, c.carregar(a.evidencias))
    if r["ok"]:
        print("Checagem OK: todos os números vêm de evidencias.json.")
        return
    print("CHECAGEM REPROVADA. Corrija e rode de novo:")
    for x in r["problemas"]:
        print(f"  - {x}")
    for d in r["divergencias"]:
        print(f"  - {d['campo']}: {d['problema']}" + (f" | \"{d['trecho']}\"" if d.get("trecho") else ""))
    print("Dica: para um número que ainda não existe, crie a evidência com fontes.py, arquivo.py ou evidencias.py calcular/relato.")
    sys.exit(1)


if __name__ == "__main__":
    main()
