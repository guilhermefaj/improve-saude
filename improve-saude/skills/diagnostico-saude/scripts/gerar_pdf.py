"""Converte o HTML do diagnóstico em PDF com o navegador da própria máquina.

  python gerar_pdf.py [--html diagnostico-<municipio>.html] [--saida diagnostico-<municipio>.pdf]

Usa o Chrome, o Edge ou o Chromium instalado, em modo headless. O documento
não sai da máquina. CHROME_PATH aponta um executável específico, se preciso.
Se nenhum funcionar, o HTML continua pronto: abra no navegador e use
Imprimir > Salvar como PDF (margens padrão, gráficos de fundo ligados).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _comum  # noqa: F401  (acerta o UTF-8 do console)

CAMINHOS = [  # Chrome antes do Edge: em algumas máquinas o Edge headless sai sem gerar nada
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
NOMES = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "microsoft-edge", "msedge", "chrome"]
BASE = ["--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--virtual-time-budget=15000"]


def navegadores():
    achados = []
    candidatos = [os.environ.get("CHROME_PATH")] + CAMINHOS + [shutil.which(n) for n in NOMES]
    for p in candidatos:
        if p and os.path.exists(p) and os.path.normcase(p) not in map(os.path.normcase, achados):
            achados.append(p)
    return achados


# Alguns agentes rodam os comandos dentro de um sandbox próprio (o Codex no Windows,
# por exemplo). Ali o sandbox do Chrome não consegue subir e o navegador cai na
# hora. Nesse caso tentamos de novo sem ele. O navegador só abre o HTML que o
# renderizador acabou de gerar e as fontes da marca.
SEM_SANDBOX = ["--no-sandbox"]
_extra = []


def _rodar(exe, args, timeout):
    perfil = tempfile.mkdtemp(prefix="improve-nav-")
    try:
        return subprocess.run([exe, *BASE, f"--user-data-dir={perfil}", *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)


def rodar(exe, args, timeout=120):
    """Roda o navegador headless com um perfil temporário e devolve o processo concluído."""
    r = _rodar(exe, _extra + args, timeout)
    if r.returncode != 0 and not _extra:
        r2 = _rodar(exe, SEM_SANDBOX + args, timeout)
        if r2.returncode == 0:
            _extra[:] = SEM_SANDBOX
        return r2
    return r


def _imprimir(exe, html, saida):
    if os.path.exists(saida):
        os.remove(saida)
    r = rodar(exe, ["--no-pdf-header-footer", f"--print-to-pdf={saida}", Path(html).resolve().as_uri()])
    if not os.path.exists(saida) or os.path.getsize(saida) == 0:
        raise RuntimeError(f"não gerou o PDF (código {r.returncode})")
    return os.path.basename(exe)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--html", help="padrão: o diagnostico-*.html mais recente da pasta")
    p.add_argument("--saida")
    a = p.parse_args()
    a.html = a.html or _comum.html_padrao()
    if not os.path.exists(a.html):
        print(f"Não achei o HTML ({os.path.abspath(a.html)}). Rode renderizar.py antes; se ele recusou, corrija o que a checagem apontou.")
        sys.exit(2)
    saida = os.path.abspath(a.saida or os.path.splitext(a.html)[0] + ".pdf")
    lista = navegadores()
    erros = []
    for exe in lista:
        try:
            print(f"PDF gerado com {_imprimir(exe, a.html, saida)}: {saida}")
            return
        except Exception as e:  # noqa: BLE001
            erros.append(f"{os.path.basename(exe)}: {e}")
    print("Não consegui gerar o PDF aqui:")
    for e in erros or ["nenhum Chrome, Edge ou Chromium encontrado (defina CHROME_PATH)"]:
        print(f"  - {e}")
    print(f"O HTML está pronto em {os.path.abspath(a.html)}. Abra no navegador e use Imprimir > Salvar como PDF.")
    sys.exit(2)


if __name__ == "__main__":
    main()
