"""Funções comuns aos scripts da skill Diagnóstico de Saúde Pública (Improve).

Regra central: todo número que aparece no documento nasce aqui, num script,
e fica gravado em evidencias.json com fonte, período e origem. O agente não
digita números no documento: ele cita {{id}}.

Só biblioteca padrão do Python (3.9+), para rodar em qualquer agente (Claude,
Codex, ChatGPT) e em ambientes de código na nuvem sem instalar nada.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:  # Windows usa cp1252 no console; sem isso os acentos quebram
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

VERSAO = "0.6.2"  # versão do plugin; aparece na nota final do PDF
USER_AGENT = f"improve-saude/{VERSAO} (+https://improve.business)"
VERSAO_EVIDENCIAS = 1
MINIMO_ESTAVEL = 20  # abaixo disso, uma taxa muda muito com um caso a mais ou a menos


def instavel(n):
    """Extra para c.item quando a conta se apoia em poucos casos."""
    if n is None or n >= MINIMO_ESTAVEL:
        return {}
    return {"instavel": f"calculado sobre {fmt_num(n)} caso{'' if n == 1 else 's'}; com menos de {MINIMO_ESTAVEL}, "
                        "um caso a mais ou a menos muda muito o resultado"}


# --------------------------------------------------------------------- sandbox
# Agentes como o Codex rodam os comandos num sandbox que pode bloquear o navegador e a internet.
# A saída é pedir a liberação do próprio comando na hora: a pessoa só aprova, sem configurar nada.
PEDIR_NAVEGADOR = ("O navegador existe, mas não abriu: em geral é o sandbox do agente (no Codex, por exemplo). "
                   "Rode este mesmo comando de novo agora, pedindo para rodar fora do sandbox (no Codex: permissão elevada), "
                   "com a justificativa \"abrir o navegador da máquina para montar o diagnóstico\". Não pergunte antes à pessoa: "
                   "o pedido de aprovação já é a pergunta. Só siga sem o navegador se isso falhar ou for recusado.")
PEDIR_REDE = ("Se for o sandbox do agente (no Codex, por exemplo), rode este mesmo comando de novo agora, pedindo acesso "
              "à rede ou para rodar fora do sandbox, com a justificativa \"consultar dados públicos do município\". "
              "Não pergunte antes à pessoa: o pedido de aprovação já é a pergunta. Só siga sem as fontes públicas "
              "se isso falhar ou for recusado, e diga isso no documento.")


# --------------------------------------------------------------------- rede
class SemRede(Exception):
    """A fonte não respondeu. Em chats na nuvem e no Codex com a rede
    desligada isso é esperado: o ambiente bloqueia sites do governo."""


def get_json(url, params=None, tentativas=3, timeout=60):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe="[]")
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corpo = r.read()
            try:
                return json.loads(corpo.decode("utf-8"))
            except UnicodeDecodeError:  # alguns sistemas do governo respondem em Latin-1
                return json.loads(corpo.decode("latin-1"))
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code in (400, 401, 403, 404):
                break
        except Exception as e:  # rede, timeout, DNS, proxy do sandbox
            ultimo = e
        time.sleep(1.5 * (i + 1))
    raise SemRede(f"Sem resposta de {url.split('?')[0]}: {ultimo}")


def agora_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# --------------------------------------------------------------- formatação
def _milhar(inteiro_str):
    neg = inteiro_str.startswith("-")
    s = inteiro_str.lstrip("-")
    grupos = []
    while len(s) > 3:
        grupos.insert(0, s[-3:])
        s = s[:-3]
    grupos.insert(0, s)
    return ("-" if neg else "") + ".".join(grupos)


def fmt_num(v, casas=0):
    """1234567.891 -> '1.234.567,9' (casas=1)."""
    if v is None:
        return "sem dado"
    s = f"{float(v):.{casas}f}"
    if "." in s:
        inteiro, dec = s.split(".")
        return _milhar(inteiro) + "," + dec
    return _milhar(s)


def fmt_pct(v, casas=1):
    return "sem dado" if v is None else fmt_num(v, casas) + "%"


def fmt_brl(v):
    """Valores grandes em forma compacta, como se fala: R$ 398,8 milhões."""
    if v is None:
        return "sem dado"
    a = abs(float(v))
    if a == 0:
        return "R$ 0"
    if a >= 1e9:  # "R$ 1,2 bilhão", mas "R$ 2,0 bilhões"
        return "R$ " + fmt_num(v / 1e9, 1) + (" bilhão" if a < 1.95e9 else " bilhões")
    if a >= 1e6:
        return "R$ " + fmt_num(v / 1e6, 1) + (" milhão" if a < 1.95e6 else " milhões")
    if a >= 1e4:
        return "R$ " + fmt_num(v / 1e3, 1) + " mil"
    return "R$ " + fmt_num(v, 2 if a < 100 else 0)


def formatar(valor, unidade, casas=None):
    if unidade == "%":
        return fmt_pct(valor, 1 if casas is None else casas)
    if unidade == "R$":
        return fmt_brl(valor)
    if casas is None:
        casas = 0 if valor is None or float(valor).is_integer() else 1
    return fmt_num(valor, casas)


# --------------------------------------------------------------- evidências
def caminho_evidencias(caminho=None):
    return caminho or os.environ.get("EVIDENCIAS", "evidencias.json")


def carregar(caminho=None):
    caminho = caminho_evidencias(caminho)
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    return {"versao": VERSAO_EVIDENCIAS, "municipio": None, "itens": {}, "series": {}}


def salvar(ev, caminho=None):
    caminho = caminho_evidencias(caminho)
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ev, f, ensure_ascii=False, indent=2)
    os.replace(tmp, caminho)
    return caminho


def item(ev, id_, rotulo, valor, unidade, fonte, url, periodo, origem, casas=None, fmt=None, **extra):
    """Grava um número. `origem`: api | arquivo | calculo.
    `fmt` substitui a formatação automática (ex.: "nível 3 (laranja)")."""
    if not id_ or not all(c.isalnum() or c == "_" for c in id_):
        raise ValueError(f"id inválido: {id_!r} (use letras, números e _)")
    ev["itens"][id_] = {
        "rotulo": rotulo,
        "valor": valor,
        "fmt": fmt or formatar(valor, unidade, casas),
        "unidade": unidade,
        "periodo": str(periodo) if periodo is not None else None,
        "fonte": fonte,
        "url": url,
        "origem": origem,
        "registrado_em": agora_iso(),
        **extra,
    }
    return ev["itens"][id_]


def serie(ev, id_, rotulo, unidade, fonte, url, origem, pontos, casas=None, **extra):
    """pontos: lista de (periodo, valor) em ordem cronológica."""
    ev["series"][id_] = {
        "rotulo": rotulo,
        "unidade": unidade,
        "fonte": fonte,
        "url": url,
        "origem": origem,
        "registrado_em": agora_iso(),
        "pontos": [{"periodo": str(p), "valor": v, "fmt": formatar(v, unidade, casas)} for p, v in pontos],
        **extra,
    }
    return ev["series"][id_]


def resumo(registrado):
    """Linha curta para o agente ler no terminal, sem despejar JSON."""
    linha = f"{registrado['rotulo']}: {registrado['fmt']} ({registrado.get('periodo') or 's/d'}; {registrado['fonte']})"
    if registrado.get("instavel"):
        linha += f"\n  ATENÇÃO, número instável: {registrado['instavel']}. Se usar, diga isso em 'limites'."
    return linha


# ------------------------------------------------------------------- arquivos
def norm(texto):
    """Minúsculas sem acento, para comparar textos."""
    import unicodedata
    return unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()


def slug(texto):
    s = norm(texto)
    return "-".join(p for p in "".join(ch if ch.isalnum() else " " for ch in s).split()) or "municipio"


def html_padrao():
    """O diagnóstico mais recente da pasta de trabalho (diagnostico-<municipio>.html)."""
    achados = sorted((f for f in os.listdir(".") if f.startswith("diagnostico") and f.endswith(".html")),
                     key=os.path.getmtime, reverse=True)
    return achados[0] if achados else "diagnostico.html"
