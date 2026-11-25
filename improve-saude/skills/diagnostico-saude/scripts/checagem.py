"""Confere documento.json contra evidencias.json antes de renderizar.

  python checagem.py [--documento documento.json] [--evidencias evidencias.json]

Sai com código 0 se estiver tudo certo. Caso contrário, lista cada problema
com o campo e o trecho, para o Claude corrigir e rodar de novo.

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
LIMITES = {"titulo": 110, "mensagem_principal": 260, "insights.titulo": 70, "achado": 420, "implicacao": 420}


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
                if k in ("destaque", "evidencias", "grafico", "tipo", "confianca", "prioridade"):
                    continue
                yield from campo(f"{caminho}.{k}" if caminho else k, x)
    yield from campo("", doc)


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
            if g.get("tipo") == "serie":
                exige(g.get("serie") in series, f"{p}.grafico.serie inexistente: {g.get('serie')!r}")
            elif g.get("tipo") == "barras" and g.get("serie"):
                s = series.get(g["serie"])
                exige(s is not None, f"{p}.grafico.serie inexistente: {g.get('serie')!r}")
                exige(s is None or 2 <= len(s["pontos"]) <= 12, f"{p}.grafico: barras de série pedem de 2 a 12 pontos")
            elif g.get("tipo") == "barras":
                ids = g.get("itens") or []
                exige(2 <= len(ids) <= 8, f"{p}.grafico.itens: de 2 a 8 itens")
                faltam = [x for x in ids if x not in itens]
                exige(not faltam, f"{p}.grafico.itens inexistentes: {faltam}")
                unidades = {itens[x]["unidade"] for x in ids if x in itens}
                exige(len(unidades) <= 1, f"{p}.grafico: barras com unidades diferentes {sorted(unidades)}")
                exige(all(isinstance(itens[x]["valor"], (int, float)) for x in ids if x in itens), f"{p}.grafico: item sem valor numérico")
            else:
                problemas.append(f"{p}.grafico.tipo deve ser 'serie' ou 'barras'")
    for k in ("hipoteses", "perguntas", "proximos_passos"):
        exige(len(doc.get(k) or []) <= 4, f"{k}: no máximo 4 itens")
    para = doc.get("para") or {}
    exige(not para.get("nome"), "para.nome não é permitido: use cargo e órgão")

    # ---------- tamanhos (contados sem os marcadores)
    def tam(s):
        return len(MARCADOR.sub("00,0%", s or ""))
    if tam(doc.get("titulo")) > LIMITES["titulo"]:
        problemas.append(f"titulo passa de {LIMITES['titulo']} caracteres")
    if tam(doc.get("mensagem_principal")) > LIMITES["mensagem_principal"]:
        problemas.append(f"mensagem_principal passa de {LIMITES['mensagem_principal']} caracteres")
    for n, i in enumerate(ins):
        if tam(i.get("titulo")) > LIMITES["insights.titulo"]:
            problemas.append(f"insights[{n}].titulo passa de {LIMITES['insights.titulo']} caracteres")
        for k in ("achado", "implicacao"):
            if tam(i.get(k)) > LIMITES[k]:
                problemas.append(f"insights[{n}].{k} passa de {LIMITES[k]} caracteres")

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
