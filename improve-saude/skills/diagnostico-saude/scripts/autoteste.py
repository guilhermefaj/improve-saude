"""Roda o fluxo inteiro com um exemplo fictício e diz se tudo funciona aqui.

  python autoteste.py

Usa assets/exemplo (Pouso Alegre com planilhas inventadas, marcado como
fictício), numa pasta temporária: checagem, HTML, PDF e revisão de layout.
Não precisa de internet; sem ela, as fontes da marca caem para Arial e a
revisão só avisa. Serve para conferir uma instalação nova ou um problema
relatado. A pasta do teste fica no temporário do sistema.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _comum as c

AQUI = Path(__file__).resolve().parent
EXEMPLO = AQUI.parent / "assets" / "exemplo"
PASSOS = [("Checagem dos números", "checagem.py"), ("HTML", "renderizar.py"),
          ("PDF", "gerar_pdf.py"), ("Revisão de layout", "revisar_layout.py")]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.parse_args()
    pasta = tempfile.mkdtemp(prefix="improve-autoteste-")
    for nome in ("documento.json", "evidencias.json"):
        shutil.copy(EXEMPLO / nome, pasta)
    print(f"Autoteste do plugin Improve · Saúde Pública {c.VERSAO} em {pasta}")
    falhou = False
    for titulo, script in PASSOS:
        r = subprocess.run([sys.executable, str(AQUI / script)], cwd=pasta, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        ok = r.returncode == 0
        print(f"- {titulo}: {'ok' if ok else 'FALHOU'}")
        if not ok:
            falhou = True
            print("  " + "\n  ".join((r.stdout + r.stderr).strip().splitlines()[-8:]))
            if script == "gerar_pdf.py":
                print("  Sem PDF, o resto do teste não tem o que revisar.")
                break
    pdfs = [f for f in os.listdir(pasta) if f.endswith(".pdf")]
    if falhou:
        print(f"Algo falhou. A pasta do teste ficou em {pasta} para investigar.")
        sys.exit(1)
    print(f"Tudo certo. PDF de exemplo: {os.path.join(pasta, pdfs[0])}" if pdfs else "Tudo certo.")


if __name__ == "__main__":
    main()
