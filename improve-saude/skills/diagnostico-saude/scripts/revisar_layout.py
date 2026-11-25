"""Revisa espaçamento, quebras de linha e paginação do diagnóstico antes da entrega.

  python revisar_layout.py [--html diagnostico.html] [--pdf diagnostico.pdf]

Abre o HTML no navegador da máquina (sem interface), na largura útil da página
A4, mede cada bloco e aponta:

  PROBLEMAS (impedem a entrega)
    - seção que não cabe no número de páginas previsto (capa, achado principal,
      achados 2 e 3, fechamento: uma página cada);
    - palavra sozinha na última linha de um título ou parágrafo;
    - título que quebra em linhas demais;
    - texto ou bloco que passa da margem;
    - rótulo de gráfico cortado pela borda ou sobreposto a outro;
    - PDF com número de páginas diferente do previsto (quebra inesperada).
  AVISOS (olhar com atenção)
    - fonte da marca que não carregou (o layout caiu para Arial);
    - página de uma seção só com muito espaço vazio;
    - rótulo de gráfico encurtado com reticências.

Sai com código 0 se não houver problema, 1 se houver. Cada item diz onde está
e o que fazer. A revisão automática não substitui olhar o PDF página a página.
"""
import argparse
import json
import math
import os
import re
import sys
import tempfile
from pathlib import Path

import _comum  # noqa: F401
from gerar_pdf import navegadores, rodar

LARGURA_MM, ALTURA_MM = 178, 266  # A4 menos as margens do @page do renderizador

MEDIDOR = r"""
<style>@media screen { html, body { width: __LARGURA__mm; margin: 0; } }</style>
<script>
(async () => {
  const saida = { fontes: [], secoes: [], problemas: [], avisos: [] };
  try { await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 8000))]); } catch (e) {}
  const mm = px => px * 25.4 / 96;
  const corpo = document.body.getBoundingClientRect();
  const curto = t => (t || "").replace(/\s+/g, " ").trim().slice(0, 70);
  const onde = el => { const s = el.closest("section.pagina"); return (s ? s.dataset.nome : "?") + " › " + curto(el.innerText || el.textContent); };

  for (const f of ["Inter", "Clash Display"]) saida.fontes.push({ fonte: f, ok: document.fonts.check(`600 12px "${f}"`) });

  document.querySelectorAll("section.pagina").forEach(s => {
    const alt = mm(s.getBoundingClientRect().height);
    const ultimo = [...s.children].filter(c => !c.classList.contains("ficticio")).pop();
    const fim = ultimo ? mm(ultimo.getBoundingClientRect().bottom - s.getBoundingClientRect().top) : alt;
    saida.secoes.push({ nome: s.dataset.nome, altura_mm: alt, conteudo_mm: fim, limite: +(s.dataset.paginas || 0) });
    // blocos que não podem ser partidos: a soma deles também precisa caber
    const inteiros = [...s.querySelectorAll(".sec")];
    if (inteiros.length) saida.secoes[saida.secoes.length - 1].blocos_mm = inteiros.map(b => mm(b.getBoundingClientRect().height));
  });

  // linhas de texto, palavra por palavra
  const SEL = "h1,h2,h3,h4,p,li,td,.mensagem,.kpi-rot,.kpi-per,.sec-rot,.legenda-num,.legenda-graf,.sub,.kicker,.contexto > div,.fonte-mini,.formula";
  const LIM = [["h1", 1], [".manchete", 3], [".hero-titulo", 2], [".sec h3", 2], [".topo h2", 1], [".kpi-rot", 3], [".compactos strong", 2]];
  for (const el of document.querySelectorAll(SEL)) {
    if (el.querySelector("p,ul,ol,div,table,svg")) continue;   // só blocos de texto "folha"
    const palavras = [];
    const andar = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (andar.nextNode()) {
      const n = andar.currentNode, t = n.nodeValue, re = /[^\s ]+/g;
      let m;
      while ((m = re.exec(t))) {
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        const q = [...r.getClientRects()].filter(x => x.width > 0);
        if (q.length) palavras.push({ p: m[0], y: q[q.length - 1].top, h: q[q.length - 1].height });
      }
    }
    if (!palavras.length) continue;
    const linhas = [];
    for (const w of palavras) {
      const l = linhas.find(l => Math.abs(l.y - w.y) < Math.max(4, w.h * 0.5));
      if (l) l.n.push(w.p); else linhas.push({ y: w.y, n: [w.p] });
    }
    linhas.sort((a, b) => a.y - b.y);
    const ult = linhas[linhas.length - 1].n;
    if (linhas.length >= 2 && ult.length === 1 && ult[0].length < 25)
      saida.problemas.push({ tipo: "palavra sozinha", onde: onde(el), detalhe: `a última linha tem só "${ult[0]}"`,
        corrigir: "reescreva a frase com algumas palavras a mais ou a menos" });
    for (const [sel, max] of LIM)
      if (el.matches(sel) && linhas.length > max)
        saida.problemas.push({ tipo: "título longo", onde: onde(el), detalhe: `${linhas.length} linhas (máximo ${max})`,
          corrigir: "encurte o texto deste título" });
  }

  // passa da margem
  for (const el of document.body.querySelectorAll("*")) {
    if (el.closest("svg") || el.classList.contains("ficticio")) continue;
    const r = el.getBoundingClientRect();
    if (r.width && (r.right > corpo.right + 1 || r.left < corpo.left - 1))
      saida.problemas.push({ tipo: "passa da margem", onde: onde(el), detalhe: `${mm(Math.max(r.right - corpo.right, corpo.left - r.left)).toFixed(1)} mm além da margem (o navegador reduz o documento inteiro para caber)`,
        corrigir: "encurte o texto ou quebre o valor; se for do layout, ajuste o renderizador" });
    else if (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).overflowX !== "visible")
      saida.problemas.push({ tipo: "texto cortado", onde: onde(el), detalhe: "o conteúdo é mais largo que a caixa", corrigir: "encurte o texto" });
  }

  // gráficos
  document.querySelectorAll("svg.graf").forEach(svg => {
    const vb = svg.viewBox.baseVal, textos = [...svg.querySelectorAll("text")];
    const caixas = textos.map(t => ({ t, b: t.getBBox() }));
    const nome = onde(svg.closest(".graf-box") || svg);
    for (const { t, b } of caixas) {
      if (b.x < vb.x - 0.5 || b.x + b.width > vb.x + vb.width + 0.5 || b.y < vb.y - 0.5 || b.y + b.height > vb.y + vb.height + 0.5)
        saida.problemas.push({ tipo: "rótulo cortado", onde: nome, detalhe: `"${t.textContent}" sai da área do gráfico`, corrigir: "ajuste o renderizador ou encurte o rótulo da evidência" });
      if (t.textContent.includes("…"))
        saida.avisos.push({ tipo: "rótulo encurtado", onde: nome, detalhe: `"${t.textContent}"`, corrigir: "se o corte atrapalhar a leitura, use um rótulo mais curto na evidência" });
    }
    for (let i = 0; i < caixas.length; i++) for (let j = i + 1; j < caixas.length; j++) {
      const a = caixas[i].b, b = caixas[j].b;
      const dx = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
      const dy = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
      if (dx > 1 && dy > 1)
        saida.problemas.push({ tipo: "rótulos sobrepostos", onde: nome, detalhe: `"${caixas[i].t.textContent}" encosta em "${caixas[j].t.textContent}"`, corrigir: "ajuste o renderizador" });
    }
  });

  const pre = document.createElement("script");
  pre.type = "application/json"; pre.id = "revisao-layout"; pre.textContent = JSON.stringify(saida);
  document.body.appendChild(pre);
})();
</script>
"""


def medir(html):
    fonte = Path(html).read_text(encoding="utf-8")
    medidor = MEDIDOR.replace("__LARGURA__", str(LARGURA_MM))
    pasta = os.path.dirname(os.path.abspath(html))
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=pasta, delete=False, encoding="utf-8") as tmp:
        tmp.write(fonte.replace("</body>", medidor + "</body>"))
    try:
        erros = []
        for exe in navegadores():
            r = rodar(exe, ["--dump-dom", Path(tmp.name).resolve().as_uri()])
            mt = re.search(r'<script type="application/json" id="revisao-layout">(.*?)</script>', r.stdout or "", re.S)
            if mt:
                return json.loads(mt.group(1).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
            erros.append(f"{os.path.basename(exe)}: a medição não terminou")
        raise RuntimeError("; ".join(erros) or "nenhum Chrome, Edge ou Chromium encontrado")
    finally:
        os.remove(tmp.name)


def paginas_pdf(pdf):
    dados = Path(pdf).read_bytes()
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", dados))


def avaliar(m, pdf=None):
    problemas, avisos = list(m["problemas"]), list(m["avisos"])
    for f in m["fontes"]:
        if not f["ok"]:
            avisos.append({"tipo": "fonte", "onde": f["fonte"], "detalhe": "não carregou; o layout medido usou a fonte reserva",
                           "corrigir": "confira a internet da máquina e gere de novo"})
    previstas = 0
    for s in m["secoes"]:
        uso = s["altura_mm"] / ALTURA_MM
        if s["limite"]:
            previstas += s["limite"]
            if s.get("blocos_mm") and len(s["blocos_mm"]) > 1:
                cab = s["altura_mm"] - sum(s["blocos_mm"])
                if s["altura_mm"] > ALTURA_MM:
                    excesso = s["altura_mm"] - ALTURA_MM
                    problemas.append({"tipo": "página estourada", "onde": s["nome"],
                                      "detalhe": f"os blocos somam {s['altura_mm']:.0f} mm para {ALTURA_MM} mm disponíveis ({excesso:.0f} mm a mais; cabeçalho {cab:.0f} mm)",
                                      "corrigir": "encurte achado, implicação ou ações dos insights 2 e 3, ou tire uma ação"})
            elif s["altura_mm"] > ALTURA_MM + 0.5:
                problemas.append({"tipo": "página estourada", "onde": s["nome"],
                                  "detalhe": f"{s['altura_mm']:.0f} mm para {ALTURA_MM} mm disponíveis ({s['altura_mm'] - ALTURA_MM:.0f} mm a mais)",
                                  "corrigir": "encurte os textos desta página (achado, implicação, ações, limites)"})
            elif s["nome"] not in ("Fechamento", "Capa") and s["conteudo_mm"] / ALTURA_MM < 0.6:
                avisos.append({"tipo": "página vazia", "onde": s["nome"],
                               "detalhe": f"o conteúdo ocupa {s['conteudo_mm'] / ALTURA_MM:.0%} da página",
                               "corrigir": "aceitável se o achado é curto; se parecer vazio, acrescente uma ação ou um limite"})
        else:
            previstas += max(1, math.ceil(uso - 0.01))
    total = None
    if pdf and os.path.exists(pdf):
        total = paginas_pdf(pdf)
        if total and total != previstas:
            problemas.append({"tipo": "quebra inesperada", "onde": os.path.basename(pdf),
                              "detalhe": f"o PDF tem {total} páginas; o previsto era {previstas}",
                              "corrigir": "algum bloco foi empurrado para outra página: veja os itens de página estourada"})
    return problemas, avisos, previstas, total


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--html", default="diagnostico.html")
    p.add_argument("--pdf", help="padrão: o .pdf ao lado do HTML, se existir")
    p.add_argument("--json", action="store_true", help="imprime a medição completa em JSON")
    a = p.parse_args()
    pdf = a.pdf or os.path.splitext(a.html)[0] + ".pdf"
    try:
        m = medir(a.html)
    except Exception as e:  # noqa: BLE001
        print(f"Não consegui medir o layout: {e}")
        print("Faça a revisão só pelo olho, página por página.")
        sys.exit(2)
    if a.json:
        print(json.dumps(m, ensure_ascii=False, indent=1))
    problemas, avisos, previstas, total = avaliar(m, pdf)
    print("Páginas por seção:")
    for s in m["secoes"]:
        lim = f" (limite {s['limite']})" if s["limite"] else ""
        print(f"  - {s['nome']}: {s['altura_mm']:.0f} mm de {ALTURA_MM} mm = {s['altura_mm'] / ALTURA_MM:.2f} página{lim}")
    print(f"  Total previsto: {previstas} páginas" + (f"; PDF: {total}" if total is not None else ""))
    for titulo, itens in (("PROBLEMAS", problemas), ("AVISOS", avisos)):
        if itens:
            print(f"\n{titulo} ({len(itens)}):")
            for x in itens:
                print(f"  - [{x['tipo']}] {x['onde']}\n      {x['detalhe']}\n      -> {x['corrigir']}")
    if problemas:
        print("\nREVISÃO REPROVADA. Corrija o documento.json, rode checagem, renderizar, gerar_pdf e esta revisão de novo.")
        sys.exit(1)
    print("\nRevisão automática OK. Agora olhe o PDF página por página (lista no SKILL.md).")


if __name__ == "__main__":
    main()
