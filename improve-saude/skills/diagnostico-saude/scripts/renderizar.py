"""Gera o HTML A4 com a marca Improve a partir de documento.json + evidencias.json.

  python renderizar.py [--documento documento.json] [--evidencias evidencias.json]
                       [--saida diagnostico-<municipio>.html] [--sem-checagem]

Roda a checagem antes e recusa gerar se ela reprovar. Os números entram pelo
`fmt` de cada evidência; os gráficos são SVG desenhados aqui, a partir das
evidências. O agente não toca em número nenhum nesta etapa.

Hierarquia visual: o insight de prioridade 1 ganha uma página inteira; os de
prioridade 2 e 3, meia página com gráfico; os demais, uma lista compacta.
"""
import argparse
import base64
import html
import json
import os
import re
import sys
from datetime import datetime

import _comum as c
from checagem import MARCADOR, checar

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(AQUI, "..", "assets", "logo-improve.png")

# Marca Improve (skill improve-design, perfil publicações)
C = {"laranja": "#F2703E", "roxo": "#483C8F", "texto": "#252527", "apoio": "#4F4F51",
     "sup": "#F5F2F0", "supL": "#FFF7F3", "linha": "#D9D4D0", "verde": "#2E7D5B", "vermelho": "#C0392B"}
TIPO = {"alerta": ("Alerta", C["vermelho"]), "risco": ("Risco", C["vermelho"]), "oportunidade": ("Oportunidade", C["verde"]),
        "tendencia": ("Tendência", C["roxo"]), "comparacao": ("Comparação", C["roxo"]), "eficiencia": ("Eficiência", C["laranja"])}
CONFIANCA = {"alta": "Confiança alta", "media": "Confiança média", "baixa": "Confiança baixa"}
ORIGEM = {"api": "Dado público", "arquivo": "Arquivo da secretaria", "calculo": "Cálculo", "relato": "Relato da secretaria"}
SITE = "https://improve.business"
EMAIL = "contato@improve.business"
# Deixa claro que o documento não é um trabalho contratado da Improve.
AVISO = ("Diagnóstico gerado automaticamente e de graça pelo plugin Improve · Saúde Pública, a partir de uma conversa "
         "curta e dos dados enviados. Não é uma consultoria contratada nem foi revisado pela equipe da Improve Business.")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]

esc = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def data_extenso(d=None):
    d = d or datetime.now()
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


# ------------------------------------------------------------------ texto
MONOSSILABOS = re.compile(r"(?<![\w\u00a0])(a|o|e|é|à|ao|de|do|da|em|no|na|um|os|as|se)\s+(?=\S)", re.I)


def amarrar(s):
    """Espaço inseparável depois de palavras curtas, para nenhuma ficar sozinha no fim da linha."""
    return MONOSSILABOS.sub(lambda mt: mt.group(1) + "\u00a0", s)


def nome_proprio(s):
    """POUSO ALEGRE/SANTA RITA DO SAPUCAI -> Pouso Alegre/Santa Rita do Sapucai."""
    t = (s or "").title()
    return re.sub(r"\b(De|Do|Da|Dos|Das|E)\b", lambda mt: mt.group(1).lower(), t)


def minuscula_inicial(s):
    """'Faltas por UBS' -> 'faltas por UBS' (sem estragar siglas: 'UBS ativas' fica como está)."""
    return s[:1].lower() + s[1:] if len(s) > 1 and not s[1].isupper() else s


def periodo(p):
    """'2026-11' -> 'nov 2026'; '2026 e jan a out 2026' -> 'jan a out 2026'."""
    p = str(p or "")
    p = re.sub(r"\b(\d{4})-(\d{2})\b", lambda mt: f"{MESES[int(mt.group(2)) - 1][:3]} {mt.group(1)}" if 1 <= int(mt.group(2)) <= 12 else mt.group(0), p)
    partes = [x.strip() for x in p.split(" e ")]
    if len(partes) > 1:
        partes = [x for x in partes if not (re.fullmatch(r"\d{4}", x) and any(x in y and y != x for y in partes))]
    return " e ".join(dict.fromkeys(partes))


def plano(s):
    """Texto simples para dentro de um bloco: escapa e cuida das quebras como texto()."""
    return re.sub(r" (?=[^ \u00a0<>]{1,14}$)", "\u00a0", amarrar(esc(s)))


def texto(s, itens):
    """Escapa, troca {{id}} pelo número formatado e aceita **negrito**.

    Também cuida das quebras: palavras curtas se prendem à seguinte e a última
    palavra se prende à anterior (espaço inseparável); o CSS faz o resto."""
    partes, pos = [], 0
    for mt in MARCADOR.finditer(s or ""):
        partes.append(amarrar(esc(s[pos:mt.start()])))
        it = itens[mt.group(1)]
        cls = "num relato" if it["origem"] == "relato" else "num"
        partes.append(f'<span class="{cls}">{esc(it["fmt"])}</span>')
        pos = mt.end()
    partes.append(amarrar(esc((s or "")[pos:])))
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", "".join(partes))
    return re.sub(r" (?=[^ \u00a0<>]{1,14}$)", "\u00a0", out)


ROTULO = re.compile(r"^([^:{}]{1,30}):\s+(.+)$", re.S)


def lista(itens_txt, itens, cls="", rotulos=False):
    """rotulos=True: itens no formato "IBGE: população estimada" viram rótulo em
    negrito e descrição na linha de baixo, todos iguais (só se todos seguirem o formato)."""
    if not itens_txt:
        return ""
    if rotulos and all(ROTULO.match(x or "") for x in itens_txt):
        lis = "".join(f'<li><strong class="rot">{plano(ROTULO.match(x).group(1))}</strong>{texto(ROTULO.match(x).group(2), itens)}</li>'
                      for x in itens_txt)
        return f'<ul class="{cls} rotulada">{lis}</ul>'
    return f'<ul class="{cls}">' + "".join(f"<li>{texto(x, itens)}</li>" for x in itens_txt) + "</ul>"


# ------------------------------------------------------------------ gráficos
def _ticks(hi):
    if hi <= 0:
        return [0, 1]
    import math
    passo = 10 ** math.floor(math.log10(hi / 3))
    for m in (1, 2, 2.5, 5, 10):
        if hi / (passo * m) <= 4:
            passo *= m
            break
    t, v = [], 0
    while v < hi + passo * 0.999:
        t.append(v)
        v += passo
    return t


def _periodo_curto(p):
    """2026-03 -> mar/26; o resto fica como veio."""
    mt = re.fullmatch(r"(\d{4})-(\d{2})", str(p))
    if mt and 1 <= int(mt.group(2)) <= 12:
        return f"{MESES[int(mt.group(2)) - 1][:3]}/{mt.group(1)[2:]}"
    return str(p)


def grafico_serie(s, w=640, h=230):
    pts = [p for p in s["pontos"] if isinstance(p["valor"], (int, float))]
    if len(pts) < 2:
        return ""
    l, r, t, b = 52, 18, 26, 30
    vals = [p["valor"] for p in pts]
    lo = min(0, min(vals))
    ticks = _ticks(max(vals))
    hi = ticks[-1] or 1
    x = lambda i: l + i * (w - l - r) / (len(pts) - 1)
    y = lambda v: t + (1 - (v - lo) / (hi - lo)) * (h - t - b)
    grade = "".join(f'<line x1="{l}" x2="{w - r}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{C["linha"]}" stroke-width="0.7"/>'
                    f'<text x="{l - 6}" y="{y(v) + 3:.1f}" text-anchor="end" class="eixo">{esc(c.formatar(v, s["unidade"] if s["unidade"] in ("%", "R$") else "", 0))}</text>'
                    for v in ticks)
    linha = " ".join(f"{x(i):.1f},{y(p['valor']):.1f}" for i, p in enumerate(pts))
    area = f"{x(0):.1f},{y(lo):.1f} {linha} {x(len(pts) - 1):.1f},{y(lo):.1f}"
    cabem = max(2, int((w - l - r) / 62))
    passo = max(1, -(-len(pts) // cabem))
    mostrar = [i for i in range(len(pts)) if i % passo == 0]
    if (len(pts) - 1 - mostrar[-1]) * 62 / passo >= 40 or len(mostrar) == 1:
        mostrar.append(len(pts) - 1)
    elif mostrar[-1] != len(pts) - 1:
        mostrar[-1] = len(pts) - 1
    rot_x = "".join(f'<text x="{x(i):.1f}" y="{h - 10}" text-anchor="middle" class="eixo">{esc(_periodo_curto(pts[i]["periodo"]))}</text>'
                    for i in mostrar)
    imax = max(range(len(pts)), key=lambda i: pts[i]["valor"])
    marcas = ""
    for i in sorted({imax, len(pts) - 1}):
        p = pts[i]
        marcas += (f'<circle cx="{x(i):.1f}" cy="{y(p["valor"]):.1f}" r="4.5" fill="{C["laranja"]}" stroke="#fff" stroke-width="1.5"/>'
                   f'<text x="{min(max(x(i), l + 20), w - r - 20):.1f}" y="{y(p["valor"]) - 10:.1f}" text-anchor="middle" class="rot">{esc(p["fmt"])}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" class="graf" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(s["rotulo"])}">'
            f'{grade}<polygon points="{area}" fill="{C["laranja"]}" fill-opacity="0.10"/>'
            f'<polyline points="{linha}" fill="none" stroke="{C["laranja"]}" stroke-width="2.5" stroke-linejoin="round"/>'
            f'{marcas}{rot_x}</svg>')


def _sem_prefixo(rotulos):
    """Tira as palavras iniciais repetidas em todos os rótulos ("Despesa liquidada em ...")."""
    partes = [r.split() for r in rotulos]
    n = 0
    while len(partes) > 1 and all(len(p) > n + 1 and p[n].lower() == partes[0][n].lower() for p in partes):
        n += 1
    return [" ".join(p[n:]) for p in partes], " ".join(partes[0][:n])


def grafico_barras(ids, itens, destaque=None, dados=None, compacto=False):
    """Barras horizontais. `dados` = [(chave, {rotulo, valor, fmt})]; sem ele, usa os itens."""
    dados = dados or [(i, itens[i]) for i in ids]
    dados = sorted(dados, key=lambda kv: -kv[1]["valor"])
    curtos, prefixo = _sem_prefixo([v["rotulo"] for _, v in dados])
    dados = [(k, dict(v, rotulo=cur[:1].upper() + cur[1:])) for (k, v), cur in zip(dados, curtos)]
    altura_barra, gap = (16, 7) if compacto else (22, 12)
    w, l, corte = (460, 175, 27) if compacto else (640, 230, 36)
    r = 16 + 7.4 * max(len(v["fmt"]) for _, v in dados)  # espaço para o valor depois da maior barra
    rotulos = [_quebrar(v["rotulo"], corte) for _, v in dados]
    passo_linha = 12.5
    alturas = [max(altura_barra, len(q) * passo_linha + 2) for q in rotulos]
    h = sum(a + gap for a in alturas) + 6
    hi = max(v["valor"] for _, v in dados) or 1
    linhas, yy = "", 4
    for (i, v), rot, alt in zip(dados, rotulos, alturas):
        larg = max(2, (w - l - r) * v["valor"] / hi)
        cor = C["laranja"] if i == destaque else C["roxo"]
        op = "1" if i == destaque else "0.35"
        meio = yy + alt / 2
        y0 = meio - (len(rot) - 1) * passo_linha / 2 + 4
        tspans = "".join(f'<tspan x="{l - 10}" y="{y0 + k * passo_linha:.1f}">{esc(t)}</tspan>' for k, t in enumerate(rot))
        linhas += (f'<text text-anchor="end" class="bar-rot">{tspans}</text>'
                   f'<rect x="{l}" y="{meio - altura_barra / 2:.1f}" width="{larg:.1f}" height="{altura_barra}" rx="4" fill="{cor}" fill-opacity="{op}"/>'
                   f'<text x="{l + larg + 8:.1f}" y="{meio + 4:.1f}" class="rot">{esc(v["fmt"])}</text>')
        yy += alt + gap
    return f'<svg viewBox="0 0 {w} {h:.0f}" class="graf" xmlns="http://www.w3.org/2000/svg">{linhas}</svg>', prefixo


def _quebrar(rotulo, corte):
    """Rótulo em até duas linhas equilibradas, quebrando entre palavras; só corta se nem assim couber."""
    if len(rotulo) <= corte:
        return [rotulo]
    p = rotulo.split()
    opcoes = [(" ".join(p[:k]), " ".join(p[k:])) for k in range(1, len(p))]
    cabem = [o for o in opcoes if len(o[0]) <= corte and len(o[1]) <= corte]
    if cabem:
        return list(min(cabem, key=lambda o: abs(len(o[0]) - len(o[1]))))
    l1 = opcoes[0][0] if opcoes and len(opcoes[0][0]) <= corte else rotulo[:corte - 1] + "…"
    resto = rotulo[len(l1):].strip() if not l1.endswith("…") else ""
    return [l1] + ([resto if len(resto) <= corte else resto[:corte - 1].rstrip() + "…"] if resto else [])


def grafico(g, ev, destaque, compacto=False):
    """SVG do gráfico + legenda curta dizendo o que está sendo medido."""
    if not g:
        return ""
    if g.get("tipo") == "serie":
        s = ev["series"][g["serie"]]
        svg, leg = grafico_serie(s, *((420, 190) if compacto else (640, 230))), s["rotulo"]
    elif g.get("serie"):  # barras a partir de uma série por categoria (ex.: faltas por UBS)
        s = ev["series"][g["serie"]]
        dados = [(p["periodo"], {"rotulo": p["periodo"], "valor": p["valor"], "fmt": p["fmt"]})
                 for p in s["pontos"] if isinstance(p["valor"], (int, float))]
        realce = g.get("realce") or max(dados, key=lambda kv: kv[1]["valor"])[0]
        svg, _ = grafico_barras([], {}, realce, dados=dados, compacto=compacto)
        leg = s["rotulo"]
    else:
        # laranja: o `realce` pedido; senão o número em destaque, se for uma das barras; senão a maior
        realce = g.get("realce") if g.get("realce") in g["itens"] else destaque
        if realce not in g["itens"]:
            realce = max(g["itens"], key=lambda i: ev["itens"][i]["valor"])
        svg, prefixo = grafico_barras(g["itens"], ev["itens"], realce, compacto=compacto)
        periodos = sorted({periodo(ev["itens"][i].get("periodo")) for i in g["itens"] if ev["itens"][i].get("periodo")})
        prefixo = re.sub(r"\s+(em|de|da|do|das|dos|por|na|no|nas|nos)$", "", prefixo or "", flags=re.I)
        leg = (prefixo or "Comparação") + (" · " + " e ".join(periodos) if periodos else "")
    if not svg:
        return ""
    return f'<div class="legenda-graf">{plano(leg[:1].upper() + leg[1:])}</div>{svg}'


def fontes_de(ins, ev):
    vistos = []
    ids = [ins["destaque"]] + list(ins.get("evidencias") or [])
    g = ins.get("grafico") or {}
    ids += g.get("itens") or []
    if g.get("serie"):
        ids.append(g["serie"])
    while ids:
        i = ids.pop(0)
        e = ev["itens"].get(i) or ev["series"].get(i)
        if not e:
            continue
        if e.get("origem") == "calculo" and e.get("depende_de"):
            ids.extend(e["depende_de"])
        elif e["fonte"] not in vistos:
            vistos.append(e["fonte"])
    return " · ".join(vistos)


# ------------------------------------------------------------------ blocos
def topo(municipio, titulo, logo):
    img = '<span class="logo" role="img" aria-label="Improve"></span>' if logo else ""
    return (f'<header class="topo"><div><span class="kicker">{esc(municipio)} · Diagnóstico de Saúde Pública</span>'
            f'<h2>{esc(titulo)}</h2></div>{img}</header>')


def selos(ins):
    rot, cor = TIPO[ins["tipo"]]
    return (f'<span class="selo" style="color:{cor};border-color:{cor}">{rot}</span>'
            f'<span class="selo conf">{CONFIANCA[ins["confianca"]]}</span>')


def bloco_acoes(ins, itens):
    if not ins.get("acoes"):
        return ""
    return f'<div class="acoes"><h4>O que fazer</h4>{lista(ins["acoes"], itens)}</div>'


def insight_principal(ins, ev, municipio, logo, marca):
    it = ev["itens"]
    d = it[ins["destaque"]]
    return f"""<section class="pagina hero" data-nome="Achado principal" data-paginas="1">{marca}{topo(municipio, "Achado principal", logo)}
  <div class="selos">{selos(ins)}</div>
  <h3 class="hero-titulo">{texto(ins["titulo"], it)}</h3>
  <div class="hero-num"><div class="valor">{plano(d["fmt"])}</div><div class="legenda-num">{plano(d["rotulo"])}<br><span>{plano(periodo(d.get("periodo")))}</span></div></div>
  <div class="graf-box">{grafico(ins.get("grafico"), ev, ins["destaque"])}</div>
  <p class="achado">{texto(ins["achado"], it)}</p>
  <div class="implicacao"><h4>O que isso significa para o seu trabalho</h4><p>{texto(ins["implicacao"], it)}</p></div>
  {bloco_acoes(ins, it)}
  <p class="cruz"><strong>Cruzamento:</strong> {texto(ins["cruzamento"], it)}</p>
  {f'<p class="limites"><strong>Limites:</strong> {texto(ins["limites"], it)}</p>' if ins.get("limites") else ""}
  <p class="fonte">Fontes: {plano(fontes_de(ins, ev))}</p>
</section>"""


def insight_secundario(ins, ev):
    it = ev["itens"]
    d = it[ins["destaque"]]
    graf = grafico(ins.get("grafico"), ev, ins["destaque"], compacto=True)
    return f"""<article class="sec">
  <div class="selos">{selos(ins)}</div>
  <h3>{texto(ins["titulo"], it)}</h3>
  <div class="sec-corpo{'' if graf else ' sem-graf'}">
    <div><div class="sec-num">{plano(d["fmt"])}</div><div class="sec-rot">{plano(d["rotulo"])} · {plano(periodo(d.get("periodo")))}</div>
      <p>{texto(ins["achado"], it)}</p></div>
    {f'<div class="graf-box">{graf}</div>' if graf else ''}
  </div>
  <div class="sec-pe">
    <div class="implicacao"><h4>Para o seu trabalho</h4><p>{texto(ins["implicacao"], it)}</p></div>
    {bloco_acoes(ins, it)}
  </div>
  <p class="fonte">Cruzamento: {texto(ins["cruzamento"], it)} · Fontes: {plano(fontes_de(ins, ev))}</p>
</article>"""


def insight_compacto(ins, ev):
    it = ev["itens"]
    d = it[ins["destaque"]]
    rot, cor = TIPO[ins["tipo"]]
    return f"""<li style="border-left-color:{cor}"><span class="mini-tipo" style="color:{cor}">{rot}</span>
  <strong>{texto(ins["titulo"], it)}</strong> <span class="num">{esc(d["fmt"])}</span><br>{texto(ins["achado"], it)}
  <span class="fonte-mini">Fontes: {plano(fontes_de(ins, ev))}</span></li>"""


def ids_citados(doc, ev):
    ids = []
    def add(i):
        if i and i not in ids:
            ids.append(i)
    for _, s in _todos_textos(doc):
        for mt in MARCADOR.finditer(s):
            add(mt.group(1))
    for ins in doc.get("insights") or []:
        add(ins.get("destaque"))
        for i in ins.get("evidencias") or []:
            add(i)
        g = ins.get("grafico") or {}
        for i in g.get("itens") or []:
            add(i)
        add(g.get("serie"))
    # inclui as evidências de que os cálculos dependem
    for i in list(ids):
        for dep in (ev["itens"].get(i) or {}).get("depende_de") or []:
            add(dep)
    return ids


def _todos_textos(doc):
    from checagem import textos
    return textos(doc)


def fontes_base(e, ev, vistos=None):
    """Fontes originais de um cálculo, descendo por cálculos feitos sobre outros cálculos."""
    vistos = set() if vistos is None else vistos
    fontes = []
    for dep in e.get("depende_de") or []:
        if dep in vistos:
            continue
        vistos.add(dep)
        d = ev["itens"].get(dep) or ev["series"].get(dep) or {}
        novas = fontes_base(d, ev, vistos) if d.get("origem") == "calculo" and d.get("depende_de") else [d.get("fonte")]
        fontes += [f for f in novas if f and f not in fontes]
    return fontes


def rastro(doc, ev):
    linhas = ""
    for i in ids_citados(doc, ev):
        e = ev["itens"].get(i)
        if e:
            valor = e["fmt"]
        else:
            e = ev["series"].get(i)
            if not e:
                continue
            pts = [p for p in e["pontos"] if isinstance(p["valor"], (int, float))]
            lo, hi = min(pts, key=lambda p: p["valor"]), max(pts, key=lambda p: p["valor"])
            valor = f"{lo['fmt']} a {hi['fmt']}" if pts else "série vazia"
            if e["pontos"] and not e.get("periodo"):
                e = {**e, "periodo": f"{e['pontos'][0]['periodo']} a {e['pontos'][-1]['periodo']}"}
        origem = ORIGEM.get(e["origem"], e["origem"])
        if e.get("formula"):
            f = e["formula"]
            for dep in e.get("depende_de") or []:
                if dep in ev["itens"]:
                    f = re.sub(rf"\b{re.escape(dep)}\b", minuscula_inicial(ev["itens"][dep]["rotulo"]), f)
            origem += f"<br><span class='formula'>{plano(f)}</span>"
        if e.get("instavel"):
            origem += "<br><span class='formula'>poucos casos: número instável</span>"
        if e["origem"] == "calculo" and e.get("depende_de"):
            fonte = "<br>".join(plano(f) for f in fontes_base(e, ev)) or plano(e["fonte"])
        else:
            fonte = plano(e["fonte"])
            if e.get("url"):
                fonte = f'<a href="{esc(e["url"])}">{fonte}</a>'
        linhas += (f"<tr><td>{plano(e['rotulo'])}</td><td class='v'>{esc(valor)}</td><td>{plano(periodo(e.get('periodo')))}</td>"
                   f"<td>{fonte}</td><td>{origem}</td></tr>")
    return linhas


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
@import url('https://api.fontshare.com/v2/css?f[]=clash-display@500,600&display=swap');
@page { size: A4; margin: 15mm 16mm 16mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'Inter', Arial, sans-serif; color: __texto__; font-size: 10.3pt; line-height: 1.5;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1, h2, h3, .valor, .sec-num, .kpi { font-family: 'Clash Display', 'Inter', Arial, sans-serif; font-weight: 600; }
/* quebras: títulos balanceados, parágrafos sem palavra sozinha no fim, sem hifenização automática */
h1, h2, h3, h4, .manchete, .kpi-rot, .legenda-num, .sec-rot, .legenda-graf { text-wrap: balance; }
p, li, td, .mensagem, .contexto div { text-wrap: pretty; orphans: 3; widows: 3; hyphens: manual; }
a { color: __roxo__; }
.pagina { position: relative; }
.pagina + .pagina { break-before: page; }
.ficticio { position: absolute; top: 110mm; left: -10mm; right: -10mm; text-align: center; transform: rotate(-28deg);
            font-size: 44pt; font-weight: 700; color: rgba(192,57,43,.12); pointer-events: none; z-index: 0; }
.kicker { font-size: 8pt; text-transform: uppercase; letter-spacing: .08em; color: __apoio__; }
.topo { position: relative; border-bottom: 2px solid __laranja__; padding: 0 20mm 3mm 0; margin-bottom: 6mm; }
/* top > 0 de propósito: com top 0, o Chrome desenha uma faixa do logo no pé da página anterior */
.topo .logo { position: absolute; right: 0; top: 1.5mm; width: 12mm; height: 12mm; background: var(--logo) no-repeat center / contain; }
.topo h2 { margin: 1mm 0 0; font-size: 18pt; }
.num { font-weight: 700; color: __roxo__; white-space: nowrap; }
.num.relato { text-decoration: underline dotted; text-underline-offset: 2px; }
.selos { margin-bottom: 2mm; }
.selo { display: inline-block; border: 1px solid; border-radius: 10px; padding: 0 2.5mm; font-size: 7.5pt; font-weight: 600; margin-right: 2mm; }
.selo.conf { color: __apoio__; border-color: __linha__; font-weight: 500; }
.fonte { font-size: 7.6pt; color: __apoio__; margin-top: 3mm; }
.graf { width: 100%; height: auto; display: block; }
.graf .eixo { font-size: 10px; fill: __apoio__; font-family: Inter, Arial, sans-serif; }
.graf .rot { font-size: 12px; font-weight: 700; fill: __texto__; font-family: Inter, Arial, sans-serif; }
.graf .bar-rot { font-size: 11.5px; fill: __texto__; font-family: Inter, Arial, sans-serif; }
.implicacao { background: __supL__; border-left: 3px solid __laranja__; border-radius: 0 2mm 2mm 0; padding: 3mm 4mm; margin: 4mm 0; }
.implicacao h4, .acoes h4 { margin: 0 0 1mm; font-size: 9pt; text-transform: uppercase; letter-spacing: .05em; color: __apoio__; }
.implicacao p { margin: 0; }
.acoes ul { margin: 1mm 0 0; padding-left: 5mm; } .acoes li { margin-bottom: 1mm; }
/* capa */
/* a capa fica dentro das margens: qualquer coisa mais larga que a página faz o Chrome reduzir o documento inteiro */
.capa { display: flex; flex-direction: column; min-height: 262mm; background: linear-gradient(180deg, __supL__ 0, #fff 110mm); border-radius: 3mm; padding: 10mm 10mm 8mm; }
.capa-topo { display: flex; justify-content: space-between; align-items: center; }
.logo-capa { height: 18mm; }
.capa h1 { font-size: 36pt; margin: 11mm 0 1mm; line-height: 1.05; }
.sub { color: __apoio__; font-size: 10.5pt; }
.manchete { font-size: 19pt; margin: 8mm 0 4mm; color: __roxo__; line-height: 1.22; }
.mensagem { font-size: 12.5pt; border-left: 3px solid __roxo__; padding-left: 4mm; margin: 0 0 7mm; }
.contexto { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; }
.contexto div { background: #fff; border: 1px solid __linha__; border-top: 3px solid __laranja__; border-radius: 2.5mm; padding: 3mm 3.5mm; font-size: 9pt; }
.contexto h4 { margin: 0 0 1.5mm; font-size: 8pt; text-transform: uppercase; letter-spacing: .06em; color: __apoio__; }
.contexto ul { margin: 0; padding-left: 4mm; }
.contexto ul.rotulada { list-style: none; padding-left: 0; }
.contexto ul.rotulada li + li { margin-top: 1.2mm; }
.contexto .rot { display: block; font-weight: 600; color: __texto__; }
.aviso { margin: 1.5mm 0 0; font-size: 7.3pt; line-height: 1.4; color: __apoio__; max-width: 150mm; }
.para { margin-top: auto; padding-top: 5mm; font-size: 9pt; color: __apoio__; }
.sub .seg { white-space: nowrap; }
/* insight principal */
.hero-titulo { font-size: 21pt; line-height: 1.15; margin: 1mm 0 5mm; }
.hero-num { display: flex; align-items: baseline; gap: 5mm; margin-bottom: 3mm; }
.hero-num .valor { font-size: 46pt; line-height: 1; color: __laranja__; white-space: nowrap; }
.legenda-num { font-size: 10pt; font-weight: 600; } .legenda-num span { font-weight: 400; color: __apoio__; font-size: 8.5pt; }
.graf-box { margin: 2mm 0 3mm; }
.legenda-graf { font-size: 7.8pt; font-weight: 600; color: __apoio__; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 1.5mm; }
.achado { font-size: 11.5pt; }
.cruz, .limites { font-size: 8.8pt; color: __apoio__; margin: 1.5mm 0; }
/* secundários */
.sec { break-inside: avoid; border-top: 1px solid __linha__; padding-top: 4mm; margin-bottom: 4mm; }
.sec:first-of-type { border-top: 0; padding-top: 0; }
.sec h3 { font-size: 14pt; margin: 0 0 2.5mm; line-height: 1.2; }
.sec-corpo { display: grid; grid-template-columns: 68mm 1fr; gap: 7mm; align-items: start; }
.sec-corpo.sem-graf { grid-template-columns: 1fr; }
.sec-corpo p { margin: 2mm 0 0; font-size: 9.5pt; line-height: 1.45; }
.sec-num { font-size: 27pt; color: __laranja__; line-height: 1; white-space: nowrap; }
.sec-rot { font-size: 8pt; font-weight: 600; color: __apoio__; margin-top: 1.5mm; line-height: 1.3; }
.sec-pe { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; align-items: start; }
.sec-pe .implicacao { margin: 3mm 0 0; font-size: 9.5pt; }
.sec-pe .acoes { margin-top: 3mm; font-size: 9.2pt; }
.sec-pe:has(> :only-child) { grid-template-columns: 1fr; }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 4mm; margin: 0 0 6mm; }
.kpi-card { background: #fff; border-radius: 2.5mm; padding: 3.5mm 4mm; border: 1px solid __linha__; }
.kpi-card .kpi { font-size: 22pt; color: __laranja__; line-height: 1.05; white-space: nowrap; }
.kpi-card .kpi-rot { font-size: 8.3pt; margin-top: 1.5mm; line-height: 1.3; }
.kpi-card .kpi-per { font-size: 7.5pt; color: __apoio__; }
.kpi-card.p1 { border: 1.5px solid __laranja__; background: __supL__; }
h3.mais { font-size: 13pt; margin: 0 0 3mm; }
/* compactos */
.compactos { list-style: none; padding: 0; margin: 0; }
.compactos li { background: __sup__; border-left: 3px solid; border-radius: 0 2mm 2mm 0; padding: 2.5mm 3.5mm; margin-bottom: 2.5mm; font-size: 9.3pt; break-inside: avoid; }
.mini-tipo { font-size: 7.5pt; font-weight: 700; text-transform: uppercase; letter-spacing: .05em; margin-right: 2mm; }
.fonte-mini { display: block; font-size: 7.4pt; color: __apoio__; margin-top: 1mm; }
/* fechamento */
.duas { display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }
.bloco h3 { font-size: 13pt; margin: 0 0 2mm; }
.bloco ul, .bloco ol { padding-left: 5mm; margin: 0; } .bloco li { margin-bottom: 2mm; }
.nota-hip { font-size: 8.5pt; color: __apoio__; margin: 0 0 2mm; }
.convite { background: __roxo__; color: #fff; border-radius: 3mm; padding: 6mm 7mm; margin: 8mm 0; break-inside: avoid; }
.convite h3 { margin: 0 0 1.5mm; font-size: 16pt; color: #fff; } .convite p { margin: 0; }
.convite a { color: #fff; font-weight: 600; text-decoration: underline; text-decoration-color: __laranja__; text-underline-offset: 2px; }
/* rastro */
table.rastro { width: 100%; border-collapse: collapse; font-size: 8pt; table-layout: fixed; }
table.rastro th { text-align: left; color: __apoio__; font-weight: 600; border-bottom: 1.5px solid __laranja__; padding: 1.5mm 1.5mm; }
table.rastro td { border-bottom: 1px solid __sup__; padding: 1.5mm; vertical-align: top; }
table.rastro td.v { font-weight: 700; white-space: nowrap; }
table.rastro tr { break-inside: avoid; }
.formula { color: __apoio__; font-size: 7.2pt; }
.metodo { font-size: 8.3pt; color: __apoio__; margin-top: 6mm; }
"""


def render(doc, ev):
    it = ev["itens"]
    m = ev.get("municipio") or {}
    municipio = m.get("nome") or (doc.get("para") or {}).get("orgao") or "Secretaria de Saúde"
    logo = ""
    if os.path.exists(LOGO):
        logo = "data:image/png;base64," + base64.b64encode(open(LOGO, "rb").read()).decode()
    marca = '<div class="ficticio">DADOS FICTÍCIOS · TESTE</div>' if (doc.get("ficticio") or ev.get("ficticio")) else ""
    ins = sorted(doc["insights"], key=lambda i: i["prioridade"])
    ctx = doc.get("contexto") or {}
    para = doc.get("para") or {}
    sub = " · ".join(f'<span class="seg">{esc(x)}</span>' for x in [f"{m['nome']}/{m['uf']}" if m.get("nome") else "", f"{c.fmt_num(it['pop']['valor'])} habitantes ({it['pop']['periodo']})" if "pop" in it else "",
                                 f"região de saúde {nome_proprio(m['regiao_saude'])}" if m.get("regiao_saude") else ""] if x)
    kpis = "".join(
        f'<div class="kpi-card p{i["prioridade"]}"><div class="kpi">{esc(it[i["destaque"]]["fmt"])}</div>'
        f'<div class="kpi-rot">{plano(it[i["destaque"]]["rotulo"])}</div><div class="kpi-per">{plano(periodo(it[i["destaque"]].get("periodo")))}</div></div>'
        for i in ins[:3])
    capa = f"""<section class="pagina capa" data-nome="Capa" data-paginas="1">{marca}
  <div class="capa-topo">{f'<img class="logo-capa" src="{logo}" alt="Improve">' if logo else ''}
    <span class="kicker">Diagnóstico de Saúde Pública · {esc(data_extenso())}</span></div>
  <h1>{esc(municipio)}</h1><div class="sub">{sub}</div>
  <h3 class="manchete">{texto(doc["titulo"], it)}</h3>
  {f'<p class="sub">{texto(doc["subtitulo"], it)}</p>' if doc.get("subtitulo") else ""}
  <div class="mensagem">{texto(doc["mensagem_principal"], it)}</div>
  <div class="kpis">{kpis}</div>
  <div class="contexto">
    <div><h4>O que você contou</h4>{texto(ctx.get("dor", ""), it)}</div>
    <div><h4>O que você enviou</h4>{lista(ctx.get("material_recebido"), it, rotulos=True) or "Só a conversa."}</div>
    <div><h4>Com o que cruzamos</h4>{lista(ctx.get("fontes_cruzadas"), it, rotulos=True)}</div>
  </div>
  <p class="para">{"Preparado para: " + plano(" · ".join(x for x in [para.get("cargo"), para.get("orgao")] if x)) if para else ""}</p>
  <p class="aviso">{plano(AVISO)}</p>
</section>"""
    paginas = [capa, insight_principal(ins[0], ev, municipio, logo, marca)]
    if len(ins) > 1:
        secs = "".join(insight_secundario(i, ev) for i in ins[1:3])
        paginas.append(f'<section class="pagina" data-nome="Achados 2 e 3" data-paginas="1">{marca}{topo(municipio, "Outros achados importantes", logo)}{secs}</section>')
    comp = ""
    if len(ins) > 3:  # achados de menor prioridade abrem a página de fechamento, em lista compacta
        comp = ('<h3 class="mais">Outros sinais nos dados</h3><ul class="compactos">'
                + "".join(insight_compacto(i, ev) for i in ins[3:]) + "</ul>")
    hip = doc.get("hipoteses") or []
    per = doc.get("perguntas") or []
    prox = doc.get("proximos_passos") or []
    convite = (f'<div class="convite"><h3>Quer aprofundar este diagnóstico?</h3>'
               f'<p>A Improve Business ajuda secretarias de saúde a transformar dados em decisões e resultados. '
               f'Fale com a gente: <a href="mailto:{EMAIL}">{EMAIL}</a> · <a href="{SITE}">improve.business</a></p></div>') if doc.get("convite", True) else ""
    titulo_fim = ("Outros sinais, hipóteses e próximos passos" if comp else "Hipóteses, perguntas e próximos passos")
    paginas.append(f"""<section class="pagina" data-nome="Fechamento" data-paginas="1">{marca}{topo(municipio, titulo_fim, logo)}
  {comp}
  <div class="duas"{' style="margin-top:7mm"' if comp else ''}>
    <div class="bloco"><h3>Hipóteses</h3><p class="nota-hip">Possíveis explicações. Ainda precisam ser confirmadas pela equipe.</p>{lista(hip, it)}</div>
    <div class="bloco"><h3>Perguntas que os dados levantam</h3>{lista(per, it)}</div>
  </div>
  {f'<div class="bloco" style="margin-top:6mm"><h3>Próximos passos</h3>{lista(prox, it)}</div>' if prox else ""}
  {convite}
</section>""")
    paginas.append(f"""<section class="pagina" data-nome="De onde vem cada número">{marca}{topo(municipio, "De onde vem cada número", logo)}
  <table class="rastro"><colgroup><col style="width:30%"><col style="width:14%"><col style="width:14%"><col style="width:24%"><col style="width:18%"></colgroup><thead><tr><th>Indicador</th><th>Valor</th><th>Período</th><th>Fonte</th><th>Origem</th></tr></thead>
  <tbody>{rastro(doc, ev)}</tbody></table>
  <div class="metodo"><p><strong>Como este documento foi feito.</strong> {plano(AVISO)} Ele foi montado
  a partir de dados públicos agregados por município e do material que a secretaria compartilhou na conversa.
  Nenhum dado pessoal foi usado ou citado. Os textos foram redigidos com apoio de inteligência artificial. Todos os números saíram
  das fontes acima e passaram por uma checagem automática antes da geração. Números sublinhados com pontilhado foram informados pela
  secretaria e não foram conferidos em fonte oficial.</p><p>Gerado em {esc(data_extenso())} pelo plugin
  <a href="{SITE}">Improve · Saúde Pública</a>, versão {c.VERSAO}.</p></div>
</section>""")
    css = CSS + (f":root {{ --logo: url('{logo}'); }}" if logo else "")
    for k, v in C.items():
        css = css.replace(f"__{k}__", v)
    titulo = f"Diagnóstico de Saúde Pública · {municipio}"
    return (f'<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{esc(titulo)}</title>'
            f'<meta name="viewport" content="width=device-width, initial-scale=1"><style>{css}</style></head><body>{"".join(paginas)}</body></html>')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--documento", default="documento.json")
    p.add_argument("--evidencias")
    p.add_argument("--saida", help="padrão: diagnostico-<municipio>.html")
    p.add_argument("--sem-checagem", action="store_true", help="só para depurar o layout; nunca para entregar")
    a = p.parse_args()
    with open(a.documento, encoding="utf-8") as f:
        doc = json.load(f)
    ev = c.carregar(a.evidencias)
    if not a.sem_checagem:
        r = checar(doc, ev)
        if not r["ok"]:
            print("Checagem reprovada. Rode: python checagem.py, corrija e gere de novo.")
            sys.exit(1)
    nome = (ev.get("municipio") or {}).get("nome")
    saida = a.saida or (f"diagnostico-{c.slug(nome)}.html" if nome else "diagnostico.html")
    with open(saida, "w", encoding="utf-8") as f:
        f.write(render(doc, ev))
    print(f"HTML gerado: {os.path.abspath(saida)}")


if __name__ == "__main__":
    main()
