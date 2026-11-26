"""Diz, em poucos segundos, o que funciona neste ambiente antes de começar.

  python ambiente.py

Confere o Python, o navegador que monta o PDF e o acesso às fontes públicas
(IBGE como amostra). Não grava nada. Use o resultado para escolher o caminho:
sem internet, siga só com arquivos e relatos; sem navegador, entregue o HTML.
"""
import sys

import _comum as c
from gerar_pdf import navegadores, rodar


def main():
    print(f"Plugin Improve · Saúde Pública, versão {c.VERSAO}")
    ok_py = sys.version_info >= (3, 9)
    print(f"- Python {sys.version.split()[0]}: {'ok' if ok_py else 'antigo demais; precisa de 3.9 ou mais novo'}")

    pdf = None
    for exe in navegadores():
        try:
            r = rodar(exe, ["--dump-dom", "data:text/html,<p id=t>ok-improve</p>"], timeout=40)
            if "ok-improve" in (r.stdout or ""):
                pdf = exe
                break
        except Exception:  # noqa: BLE001
            continue
    if pdf:
        print(f"- Navegador para o PDF: ok ({pdf})")
    elif navegadores():
        print("- Navegador para o PDF: existe, mas não abriu. " + c.PEDIR_NAVEGADOR)
    else:
        print("- Navegador para o PDF: não encontrado. Entregue o HTML e explique: "
              "abrir no navegador e usar Imprimir > Salvar como PDF.")

    try:
        c.get_json("https://servicodados.ibge.gov.br/api/v1/localidades/estados/MG", tentativas=1, timeout=10)
        rede = True
        print("- Fontes públicas (internet): ok")
    except c.SemRede:
        rede = False
        print("- Fontes públicas (internet): bloqueadas. " + c.PEDIR_REDE)

    caminho = ("completo" if (rede and pdf) else
               "sem dados públicos" if pdf else
               "sem PDF (entregar o HTML)" if rede else
               "só arquivos e relatos, entregando o HTML")
    print(f"Caminho possível nesta sessão: {caminho}.")
    if not ok_py:
        sys.exit(1)


if __name__ == "__main__":
    main()
