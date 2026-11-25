"""Consulta e amplia evidencias.json sem que o agente digite números.

  python evidencias.py listar [--busca TEXTO]
      Lista os ids disponíveis para citar como {{id}}.

  python evidencias.py calcular --id ID --rotulo "..." --op OP --a ID [--b ID ...]
        [--por 1000] [--unidade TEXTO] [--casas N]
      OP: pct (a/b×100) | taxa (a/b×por) | razao (a/b) | diferenca (a−b) |
          variacao_pct ((a−b)/b×100) | variacao_pp (a−b, em pontos percentuais) | soma (a+b+...)
      O resultado entra com origem "calculo", a fórmula e os ids de que depende.

  python evidencias.py relato --id ID --rotulo "..." --valor N --unidade TEXTO [--periodo TEXTO]
      Registra um número que a pessoa DISSE na conversa ("temos 12 equipes").
      Sai no documento marcado como relato da secretaria, nunca como dado oficial.
"""
import argparse
import sys

import _comum as c


def cmd_listar(a, ev):
    m = ev.get("municipio") or {}
    if m:
        print(f"Município: {m.get('nome')}/{m.get('uf')} (IBGE {m.get('ibge')})")
    b = (a.busca or "").lower()
    print("ITENS (cite como {{id}}):")
    for k, v in ev["itens"].items():
        if b and b not in k.lower() and b not in v["rotulo"].lower():
            continue
        print(f"  {k} = {v['fmt']} | {v['rotulo']} | {v.get('periodo') or 's/d'} | {v['origem']}")
    print("SÉRIES (use em grafico.serie):")
    for k, v in ev["series"].items():
        if b and b not in k.lower() and b not in v["rotulo"].lower():
            continue
        pts = v["pontos"]
        faixa = f"{pts[0]['periodo']} a {pts[-1]['periodo']}" if pts else "vazia"
        print(f"  {k} | {v['rotulo']} | {len(pts)} pontos ({faixa}) | {v['origem']}")


def _pega(ev, id_):
    if id_ not in ev["itens"]:
        sys.exit(f"id '{id_}' não existe em evidencias.json (veja: python evidencias.py listar)")
    v = ev["itens"][id_]
    if v["valor"] is None:
        sys.exit(f"'{id_}' está sem dado; não dá para calcular.")
    return v


def cmd_calcular(a, ev):
    ids = [a.a] + (a.b or [])
    vals = [_pega(ev, i) for i in ids]
    x = [float(v["valor"]) for v in vals]
    op = a.op
    if op != "soma" and len(x) != 2:
        sys.exit(f"'{op}' precisa de exatamente --a e um --b.")
    if op in ("pct", "taxa", "razao", "variacao_pct") and x[1] == 0:
        sys.exit("Divisão por zero.")
    if op == "pct":
        r, f, un = x[0] / x[1] * 100, f"{ids[0]} / {ids[1]} × 100", "%"
    elif op == "taxa":
        r, f, un = x[0] / x[1] * a.por, f"{ids[0]} / {ids[1]} × {c.fmt_num(a.por)}", f"por {c.fmt_num(a.por)}"
    elif op == "razao":
        r, f, un = x[0] / x[1], f"{ids[0]} / {ids[1]}", vals[0]["unidade"]
    elif op == "diferenca":
        r, f, un = x[0] - x[1], f"{ids[0]} − {ids[1]}", vals[0]["unidade"]
    elif op == "variacao_pct":
        r, f, un = (x[0] - x[1]) / x[1] * 100, f"({ids[0]} − {ids[1]}) / {ids[1]} × 100", "%"
    elif op == "variacao_pp":
        r, f, un = x[0] - x[1], f"{ids[0]} − {ids[1]} (pontos percentuais)", "p.p."
    else:
        r, f, un = sum(x), " + ".join(ids), vals[0]["unidade"]
    unidade = a.unidade or un
    fontes = sorted({v["fonte"] for v in vals})
    periodos = sorted({str(v.get("periodo")) for v in vals if v.get("periodo")})
    fmt = None
    if unidade == "p.p.":
        fmt = c.fmt_num(r, 1 if a.casas is None else a.casas) + " p.p."
    # Taxa ou percentual sobre poucos casos engana: marca como instável.
    contagem = lambda v: v["unidade"] not in ("%", "R$", "p.p.") and not str(v["unidade"]).startswith("por ")
    extra = {}
    if op in ("pct", "taxa", "razao") and contagem(vals[0]):
        extra = c.instavel(x[0])
    elif op in ("variacao_pct",) and contagem(vals[1]):
        extra = c.instavel(min(x[0], x[1]))
    herdado = next((v["instavel"] for v in vals if v.get("instavel")), None)
    if herdado and not extra:
        extra = {"instavel": "depende de um número instável (" + herdado + ")"}
    reg = c.item(ev, a.id, a.rotulo, r, unidade, "Cálculo sobre: " + "; ".join(fontes), None,
                 " e ".join(periodos) or None, "calculo", casas=a.casas, fmt=fmt, formula=f, depende_de=ids, **extra)
    print(c.resumo(reg) + f" | fórmula: {f}")


def cmd_relato(a, ev):
    reg = c.item(ev, a.id, a.rotulo, a.valor, a.unidade, "Relato da secretaria na conversa", None, a.periodo, "relato", casas=a.casas)
    print(c.resumo(reg))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidencias")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("listar"); s.add_argument("--busca")
    s = sub.add_parser("calcular")
    s.add_argument("--id", required=True); s.add_argument("--rotulo", required=True)
    s.add_argument("--op", required=True, choices=["pct", "taxa", "razao", "diferenca", "variacao_pct", "variacao_pp", "soma"])
    s.add_argument("--a", required=True); s.add_argument("--b", action="append")
    s.add_argument("--por", type=float, default=1000); s.add_argument("--unidade"); s.add_argument("--casas", type=int)
    s = sub.add_parser("relato")
    s.add_argument("--id", required=True); s.add_argument("--rotulo", required=True)
    s.add_argument("--valor", type=float, required=True); s.add_argument("--unidade", required=True)
    s.add_argument("--periodo"); s.add_argument("--casas", type=int)
    a = p.parse_args()
    ev = c.carregar(a.evidencias)
    {"listar": cmd_listar, "calcular": cmd_calcular, "relato": cmd_relato}[a.cmd](a, ev)
    if a.cmd != "listar":
        c.salvar(ev, a.evidencias)


if __name__ == "__main__":
    main()
