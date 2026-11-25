"""Busca dados públicos agregados por município e grava em evidencias.json.

Uso (sempre a partir da pasta de trabalho da conversa):
  python fontes.py municipio --nome "Pouso Alegre" --uf MG
  python fontes.py populacao
  python fontes.py financas --ano 2025
  python fontes.py cnes
  python fontes.py arbovirose --ano 2026 [--doenca dengue|chikungunya|zika]

Cada comando imprime um resumo curto. Nada é inventado: se a fonte não
responder, o comando falha e diz isso. Só contagens e totais são gravados;
nenhum nome de pessoa ou estabelecimento entra nas evidências.
Fontes testadas em 24/11/2026; detalhes em references/fontes-publicas.md.
"""
import argparse
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import _comum as c

IBGE = "https://servicodados.ibge.gov.br/api"
MS = "https://apidadosabertos.saude.gov.br"
SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
INFODENGUE = "https://info.dengue.mat.br/api/alertcity"


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.lower().replace("'", " ").replace("-", " ").split())


def _municipio(ev):
    m = ev.get("municipio")
    if not m:
        sys.exit("Defina o município primeiro: python fontes.py municipio --nome \"...\" --uf XX")
    return m


# ------------------------------------------------------------------ município
def cmd_municipio(a, ev):
    if a.ibge:
        dados = c.get_json(f"{IBGE}/v1/localidades/municipios/{a.ibge}")
        candidatos = [dados] if dados else []
    else:
        base = f"{IBGE}/v1/localidades/estados/{a.uf}/municipios" if a.uf else f"{IBGE}/v1/localidades/municipios"
        todos = c.get_json(base)
        alvo = _norm(a.nome)
        candidatos = [m for m in todos if _norm(m["nome"]) == alvo] or [m for m in todos if alvo in _norm(m["nome"])]
    if not candidatos:
        sys.exit("Município não encontrado no IBGE. Confira o nome e a UF.")
    if len(candidatos) > 1:
        print("Mais de um município encontrado. Repita com --ibge:")
        for m in candidatos[:15]:
            uf = (((m.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF") or {}).get("sigla", "?")
            print(f"  {m['id']}  {m['nome']} ({uf})")
        sys.exit(2)
    m = candidatos[0]
    micro = m.get("microrregiao") or {}
    uf = ((micro.get("mesorregiao") or {}).get("UF") or {})
    imediata = m.get("regiao-imediata") or {}
    ev["municipio"] = {
        "ibge": str(m["id"]),
        "ibge6": str(m["id"])[:6],
        "nome": m["nome"],
        "uf": uf.get("sigla"),
        "microrregiao": micro.get("nome"),
        "regiao_imediata": imediata.get("nome"),
        "fonte": "IBGE Localidades",
    }
    # Região e macrorregião de saúde (Ministério da Saúde)
    try:
        r = c.get_json(f"{MS}/macrorregiao-e-regiao-de-saude/municipio", {"codigo_municipio": ev["municipio"]["ibge6"]})
        reg = (r.get("macrorregiao_regiao_saude_municipios") or [{}])[0]
        ev["municipio"]["regiao_saude"] = reg.get("regiao_saude")
        ev["municipio"]["macrorregiao_saude"] = reg.get("macrorregiao_saude")
    except c.SemRede as e:
        print(f"Aviso: região de saúde indisponível ({e}).")
    mm = ev["municipio"]
    print(f"Município: {mm['nome']}/{mm['uf']} (IBGE {mm['ibge']}). Região de saúde: {mm.get('regiao_saude') or 'sem dado'}; "
          f"macrorregião: {mm.get('macrorregiao_saude') or 'sem dado'}.")


# ------------------------------------------------------------------ população
def cmd_populacao(a, ev):
    m = _municipio(ev)
    url = f"{IBGE}/v3/agregados/6579/periodos/-1/variaveis/9324"
    r = c.get_json(url, {"localidades": f"N6[{m['ibge']}]"})
    serie_ = r[0]["resultados"][0]["series"][0]["serie"]
    ano, valor = sorted(serie_.items())[-1]
    reg = c.item(ev, "pop", "População estimada", int(valor), "habitantes",
                 "IBGE, Estimativas de População (tabela 6579)", "https://sidra.ibge.gov.br/tabela/6579", ano, "api", casas=0)
    print(c.resumo(reg))


# ------------------------------------------------------------------ finanças
_SUBFUNCOES = {
    "10 - Saúde": ("desp_saude_liq", "Despesa liquidada em saúde (total)"),
    "10.301 - Atenção Básica": ("desp_ab_liq", "Despesa liquidada em atenção básica"),
    "10.302 - Assistência Hospitalar e Ambulatorial": ("desp_hosp_liq", "Despesa liquidada em assistência hospitalar e ambulatorial"),
    "10.303 - Suporte Profilático e Terapêutico": ("desp_farm_liq", "Despesa liquidada em suporte profilático e terapêutico"),
    "10.304 - Vigilância Sanitária": ("desp_vigsan_liq", "Despesa liquidada em vigilância sanitária"),
    "10.305 - Vigilância Epidemiológica": ("desp_vigepi_liq", "Despesa liquidada em vigilância epidemiológica"),
    "10.122 - Administração Geral": ("desp_adm_liq", "Despesa liquidada em administração geral da saúde"),
}


def cmd_financas(a, ev):
    m = _municipio(ev)
    feitos = []
    # 1) % da receita própria aplicada em saúde (RREO Anexo 14, último bimestre disponível do ano)
    for bim in range(6, 0, -1):
        params = {"an_exercicio": a.ano, "nr_periodo": bim, "co_tipo_demonstrativo": "RREO",
                  "no_anexo": "RREO-Anexo 14", "id_ente": m["ibge"]}
        r = c.get_json(f"{SICONFI}/rreo", params)
        linhas = [i for i in r.get("items", []) if i["conta"].startswith("Despesas com Ações e Serviços Públicos de Saúde")]
        if not linhas:
            continue
        url = f"{SICONFI}/rreo?an_exercicio={a.ano}&nr_periodo={bim}&co_tipo_demonstrativo=RREO&no_anexo=RREO-Anexo%2014&id_ente={m['ibge']}"
        periodo = f"{a.ano} (até o {bim}º bimestre)"
        fonte = "Siconfi/Tesouro Nacional, RREO Anexo 14"
        for l in linhas:
            col = l["coluna"]
            if col.startswith("% Aplicado"):
                feitos.append(c.item(ev, "asps_pct", "Receita própria aplicada em saúde", float(l["valor"]), "%", fonte, url, periodo, "api"))
            elif col.startswith("% Mínimo"):
                feitos.append(c.item(ev, "asps_minimo", "Mínimo constitucional para municípios", float(l["valor"]), "%", fonte, url, periodo, "api", casas=0))
            elif col.startswith("Valor Apurado"):
                feitos.append(c.item(ev, "asps_valor", "Despesa em saúde com recursos próprios (impostos)", float(l["valor"]), "R$", fonte, url, periodo, "api"))
        break
    else:
        print(f"Aviso: RREO Anexo 14 de {a.ano} ainda não foi entregue pelo município ao Siconfi.")

    # 2) Despesa por subfunção (DCA Anexo I-E, contas anuais; tenta o ano e o anterior)
    for ano in (a.ano, a.ano - 1):
        params = {"an_exercicio": ano, "no_anexo": "DCA-Anexo I-E", "id_ente": m["ibge"]}
        r = c.get_json(f"{SICONFI}/dca", params)
        linhas = [i for i in r.get("items", []) if i["coluna"] == "Despesas Liquidadas" and i["conta"] in _SUBFUNCOES]
        if not linhas:
            continue
        url = f"{SICONFI}/dca?an_exercicio={ano}&no_anexo=DCA-Anexo%20I-E&id_ente={m['ibge']}"
        fonte = "Siconfi/Tesouro Nacional, DCA Anexo I-E"
        for l in linhas:
            id_, rot = _SUBFUNCOES[l["conta"]]
            feitos.append(c.item(ev, id_, rot, float(l["valor"]), "R$", fonte, url, ano, "api"))
        # Contas derivadas, registradas como cálculo (com fórmula)
        it = ev["itens"]
        if "desp_saude_liq" in it and "desp_ab_liq" in it:
            v = it["desp_ab_liq"]["valor"] / it["desp_saude_liq"]["valor"] * 100
            feitos.append(c.item(ev, "ab_part_pct", "Parcela da despesa em saúde que foi para a atenção básica", v, "%",
                                 "Cálculo sobre Siconfi (DCA Anexo I-E)", url, ano, "calculo",
                                 formula="desp_ab_liq / desp_saude_liq × 100", depende_de=["desp_ab_liq", "desp_saude_liq"]))
        if "desp_saude_liq" in it and "pop" in it:
            v = it["desp_saude_liq"]["valor"] / it["pop"]["valor"]
            feitos.append(c.item(ev, "desp_saude_hab", "Despesa liquidada em saúde por habitante", v, "R$",
                                 "Cálculo sobre Siconfi (DCA) e IBGE", url, f"{ano} (população {it['pop']['periodo']})", "calculo",
                                 fmt="R$ " + c.fmt_num(v, 0),
                                 formula="desp_saude_liq / pop", depende_de=["desp_saude_liq", "pop"]))
        break
    else:
        print(f"Aviso: DCA de {a.ano} e {a.ano - 1} não encontrada no Siconfi.")
    for f in feitos:
        print(c.resumo(f))
    if not feitos:
        sys.exit(1)


# ------------------------------------------------------------------ CNES
# Tipos de unidade que importam para a gestão pública (códigos do CNES).
_TIPOS_CHAVE = {1: "Postos de saúde", 2: "Centros de saúde / UBS", 4: "Policlínicas", 5: "Hospitais gerais",
                7: "Hospitais especializados", 15: "Unidades mistas", 20: "Prontos-socorros gerais",
                36: "Clínicas e centros de especialidade", 70: "CAPS", 73: "Pronto atendimento (UPA)"}
_MAX_PAGINAS = 1500  # 30 mil estabelecimentos; só a cidade de São Paulo chega perto


def cmd_cnes(a, ev):
    """Atenção: nesta API, `offset` é o NÚMERO DA PÁGINA (0, 1, 2...), não o
    número do registro, e cada página tem no máximo 20 itens (testado em 25/11/2026)."""
    m = _municipio(ev)
    url = f"{MS}/cnes/estabelecimentos"

    def pagina(n):
        return (c.get_json(url, {"codigo_municipio": m["ibge6"], "limit": 20, "offset": n}).get("estabelecimentos") or [])

    regs, n, lote = {}, 0, 10
    with ThreadPoolExecutor(max_workers=lote) as ex:
        while n < _MAX_PAGINAS:
            paginas = list(ex.map(pagina, range(n, n + lote)))
            for p in paginas:
                for r in p:
                    regs[r.get("codigo_cnes")] = r  # chave evita duplicata entre páginas
            n += lote
            if any(len(p) < 20 for p in paginas):
                break
    if n >= _MAX_PAGINAS:
        print("Aviso: contagem parcial (limite de páginas atingido).")
    regs = list(regs.values())
    fonte = "CNES/Ministério da Saúde (API de Dados Abertos)"
    link = f"{url}?codigo_municipio={m['ibge6']}"
    hoje = c.agora_iso()[:7]
    sim = lambda r, k: str(r.get(k, "")).strip().upper() in ("1", "S", "SIM", "TRUE")
    feitos = [
        c.item(ev, "cnes_total", "Estabelecimentos de saúde cadastrados no CNES (públicos e privados)", len(regs), "estabelecimentos", fonte, link, hoje, "api"),
        c.item(ev, "cnes_sus_amb", "Estabelecimentos com atendimento ambulatorial pelo SUS", sum(1 for r in regs if sim(r, "estabelecimento_faz_atendimento_ambulatorial_sus")), "estabelecimentos", fonte, link, hoje, "api"),
        c.item(ev, "cnes_hospitalar", "Estabelecimentos com atendimento hospitalar", sum(1 for r in regs if sim(r, "estabelecimento_possui_atendimento_hospitalar")), "estabelecimentos", fonte, link, hoje, "api"),
    ]
    for cod, nome in _TIPOS_CHAVE.items():
        qtd = sum(1 for r in regs if r.get("codigo_tipo_unidade") == cod)
        if qtd:
            feitos.append(c.item(ev, f"cnes_tipo_{cod:02d}", nome, qtd, "estabelecimentos", fonte, f"{link}&codigo_tipo_unidade={cod}", hoje, "api"))
    if "pop" in ev["itens"] and "cnes_tipo_02" in ev["itens"]:
        ubs = ev["itens"]["cnes_tipo_02"]["valor"] + ev["itens"].get("cnes_tipo_01", {}).get("valor", 0)
        v = ev["itens"]["pop"]["valor"] / ubs if ubs else None
        feitos.append(c.item(ev, "hab_por_ubs", "Habitantes por UBS ou posto de saúde", v, "habitantes", "Cálculo sobre CNES e IBGE",
                             link, hoje, "calculo", casas=0, formula="pop / (cnes_tipo_02 + cnes_tipo_01)",
                             depende_de=["pop", "cnes_tipo_02", "cnes_tipo_01"]))
    for f in feitos:
        print(c.resumo(f))


# ------------------------------------------------------------------ arboviroses
_NIVEL = {1: "verde", 2: "amarelo", 3: "laranja", 4: "vermelho"}


def cmd_arbovirose(a, ev):
    m = _municipio(ev)
    d = a.doenca
    params = {"geocode": m["ibge"], "disease": d, "format": "json",
              "ew_start": 1, "ew_end": 53, "ey_start": a.ano, "ey_end": a.ano}
    r = c.get_json(INFODENGUE, params)
    if not r:
        sys.exit(f"InfoDengue sem dados de {d} em {a.ano} para este município.")
    r = sorted(r, key=lambda x: x["SE"])
    link = f"https://info.dengue.mat.br/alerta/{m['ibge']}/{d}"
    fonte = "InfoDengue (Fiocruz/FGV), casos notificados"
    pontos = [(f"SE {str(x['SE'])[-2:]}", x.get("casos") or 0) for x in r]
    s = c.serie(ev, f"{d}_sem_{a.ano}", f"Casos notificados de {d} por semana em {a.ano}", "casos", fonte, link, "api", pontos, casas=0)
    total = sum(v for _, v in pontos)
    ult = r[-1]
    sem = f"SE {str(ult['SE'])[-2:]}/{a.ano}"
    feitos = [
        c.item(ev, f"{d}_casos_{a.ano}", f"Casos notificados de {d} em {a.ano} (até a {sem})", total, "casos", fonte, link, a.ano, "api", casas=0),
        c.item(ev, f"{d}_nivel_atual", f"Nível de alerta de {d} na última semana", ult.get("nivel"), "nível", fonte, link, sem, "api",
               fmt=f"nível {ult.get('nivel')} ({_NIVEL.get(ult.get('nivel'), 'sem classificação')})"),
    ]
    pico = max(r, key=lambda x: x.get("casos") or 0)
    feitos.append(c.item(ev, f"{d}_pico_{a.ano}", f"Maior número semanal de casos de {d} em {a.ano}", pico.get("casos") or 0, "casos",
                         fonte, link, f"SE {str(pico['SE'])[-2:]}/{a.ano}", "api", casas=0))
    if "pop" in ev["itens"]:
        v = total / ev["itens"]["pop"]["valor"] * 100000
        feitos.append(c.item(ev, f"{d}_inc_{a.ano}", f"Casos de {d} por 100 mil habitantes em {a.ano}", v, "por 100 mil hab.",
                             "Cálculo sobre InfoDengue e IBGE", link, a.ano, "calculo", casas=1,
                             formula=f"{d}_casos_{a.ano} / pop × 100.000", depende_de=[f"{d}_casos_{a.ano}", "pop"]))
    temps = [(f"SE {str(x['SE'])[-2:]}", x.get("tempmed")) for x in r if x.get("tempmed") is not None]
    if temps:
        c.serie(ev, f"clima_temp_{a.ano}", f"Temperatura média semanal em {a.ano}", "°C", "InfoDengue (dados climáticos)", link, "api", temps, casas=1)
    print(f"Série: {s['rotulo']} ({len(pontos)} semanas)")
    for f in feitos:
        print(c.resumo(f))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--evidencias", help="caminho do evidencias.json (padrão: ./evidencias.json)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("municipio"); s.add_argument("--nome"); s.add_argument("--uf"); s.add_argument("--ibge")
    sub.add_parser("populacao")
    s = sub.add_parser("financas"); s.add_argument("--ano", type=int, required=True)
    sub.add_parser("cnes")
    s = sub.add_parser("arbovirose"); s.add_argument("--ano", type=int, required=True)
    s.add_argument("--doenca", default="dengue", choices=["dengue", "chikungunya", "zika"])
    a = p.parse_args()
    if a.cmd == "municipio" and not (a.nome or a.ibge):
        p.error("informe --nome (com --uf) ou --ibge")
    ev = c.carregar(a.evidencias)
    try:
        {"municipio": cmd_municipio, "populacao": cmd_populacao, "financas": cmd_financas,
         "cnes": cmd_cnes, "arbovirose": cmd_arbovirose}[a.cmd](a, ev)
    except c.SemRede as e:
        sys.exit(f"FONTE INDISPONÍVEL: {e}\nSe o ambiente bloqueia a internet (chat na nuvem ou Codex com a rede desligada), "
                 "peça acesso à rede se puder; se não, siga só com os arquivos enviados e diga isso no documento.")
    c.salvar(ev, a.evidencias)


if __name__ == "__main__":
    main()
