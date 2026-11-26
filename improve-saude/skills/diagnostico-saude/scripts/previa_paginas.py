"""Gera uma imagem PNG de cada página do diagnóstico, para a revisão visual.

  python previa_paginas.py [--html diagnostico-<municipio>.html] [--pasta previa]

Serve para qualquer agente que consiga abrir imagens, mesmo sem ler PDF.
Usa o mesmo navegador do gerar_pdf.py e não envia nada para fora da máquina.

Cada seção do documento vira uma folha A4 com as mesmas margens do PDF:
pagina-01.png, pagina-02.png e assim por diante. Uma seção mais longa que
uma página (a tabela "De onde vem cada número") sai numa imagem só, mais alta.
As quebras de página reais quem confere é o revisar_layout.py, sobre o PDF.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import _comum  # noqa: F401
from gerar_pdf import navegadores, rodar

ESCALA = 1.5            # pixels por pixel CSS: deixa o texto nítido na imagem
LARGURA_PX = 794        # 210 mm a 96 px por polegada
ALTURA_A4_PX = 1123     # 297 mm

FOLHA = r"""
<style id="previa">
@media screen {
  html, body { margin: 0 !important; background: #fff; }
  /* as margens do @page viram padding do corpo, para não mexer no padding das seções (a capa tem o seu) */
  body { width: 210mm !important; padding: 15mm 16mm 16mm !important; box-sizing: border-box; }
  section.pagina:not(.previa-mostrar) { display: none !important; }
}
</style>
<script>
(async () => {
  const alvo = __ALVO__;
  const secoes = [...document.querySelectorAll("section.pagina")];
  secoes.forEach((s, i) => { if (alvo < 0 || i === alvo) s.classList.add("previa-mostrar"); });
  if (alvo >= 0) return;
  try { await Promise.race([document.fonts.ready, new Promise(r => setTimeout(r, 8000))]); } catch (e) {}
  const out = document.createElement("script");
  out.type = "application/json"; out.id = "previa-medidas";
  out.textContent = JSON.stringify(secoes.map(s => ({ nome: s.dataset.nome || "", altura: Math.ceil(s.getBoundingClientRect().height + 31 * 96 / 25.4) })));
  document.body.appendChild(out);
})();
</script>
"""


def _copia(fonte, pasta, alvo):
    tmp = tempfile.NamedTemporaryFile("w", suffix=".html", dir=pasta, delete=False, encoding="utf-8")
    with tmp:
        tmp.write(fonte.replace("</body>", FOLHA.replace("__ALVO__", str(alvo)) + "</body>"))
    return tmp.name


def _medir(exe, fonte, pasta):
    nome = _copia(fonte, pasta, -1)
    try:
        r = rodar(exe, [f"--window-size={LARGURA_PX},{ALTURA_A4_PX}", "--dump-dom", Path(nome).resolve().as_uri()])
    finally:
        os.remove(nome)
    mt = re.search(r'<script type="application/json" id="previa-medidas">(.*?)</script>', r.stdout or "", re.S)
    if not mt:
        raise RuntimeError("a medição das páginas não terminou")
    return json.loads(mt.group(1).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def _fotografar(exe, fonte, pasta, i, altura, destino):
    nome = _copia(fonte, pasta, i)
    try:
        if os.path.exists(destino):
            os.remove(destino)
        rodar(exe, [f"--window-size={LARGURA_PX},{max(altura, ALTURA_A4_PX)}", f"--force-device-scale-factor={ESCALA}",
                    "--hide-scrollbars", f"--screenshot={destino}", Path(nome).resolve().as_uri()])
    finally:
        os.remove(nome)
    if not os.path.exists(destino) or os.path.getsize(destino) == 0:
        raise RuntimeError("não gerou a imagem")


def gerar_previa(html, pasta_saida):
    """Gera as imagens e devolve [(caminho, nome da seção, altura em páginas)]."""
    fonte = Path(html).read_text(encoding="utf-8")
    pasta_html = os.path.dirname(os.path.abspath(html))
    os.makedirs(pasta_saida, exist_ok=True)
    for velho in Path(pasta_saida).glob("pagina-*.png"):
        velho.unlink()
    erros = []
    for exe in navegadores():
        try:
            medidas = _medir(exe, fonte, pasta_html)
            feitas = []
            for i, m in enumerate(medidas):
                destino = os.path.abspath(os.path.join(pasta_saida, f"pagina-{i + 1:02d}.png"))
                _fotografar(exe, fonte, pasta_html, i, m["altura"], destino)
                feitas.append((destino, m["nome"], m["altura"] / ALTURA_A4_PX))
            return feitas
        except Exception as e:  # noqa: BLE001
            erros.append(f"{os.path.basename(exe)}: {e}")
    raise RuntimeError("; ".join(erros) or "nenhum Chrome, Edge ou Chromium encontrado (defina CHROME_PATH)")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--html", help="padrão: o diagnostico-*.html mais recente da pasta")
    p.add_argument("--pasta", default="previa")
    a = p.parse_args()
    a.html = a.html or _comum.html_padrao()
    try:
        feitas = gerar_previa(a.html, a.pasta)
    except Exception as e:  # noqa: BLE001
        print(f"Não consegui gerar a prévia: {e}")
        if navegadores():
            print(_comum.PEDIR_NAVEGADOR)
        print("Sem o navegador: se você consegue ler PDF, faça a revisão visual direto no diagnostico.pdf.")
        sys.exit(2)
    print("Prévia das páginas (abra cada imagem e confira a lista do passo 8):")
    for caminho, nome, paginas in feitas:
        extra = f" ({paginas:.1f} páginas de altura)" if paginas > 1.02 else ""
        print(f"  - {caminho}  {nome}{extra}")


if __name__ == "__main__":
    main()
