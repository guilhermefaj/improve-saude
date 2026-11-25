"""Busca dados públicos agregados por município e grava em evidencias.json.

Uso (sempre a partir da pasta de trabalho da conversa):
  python fontes.py municipio --nome "Pouso Alegre" --uf MG
  python fontes.py populacao
  python fontes.py financas --ano 2025
  python fontes.py cnes
  python fontes.py arbovirose --ano 2026 [--doenca dengue|chikungunya|zika]
  python fontes.py aps
  python fontes.py siops --ano 2025
  python fontes.py repasses --ano 2025
  python fontes.py contexto

Cada comando imprime um resumo curto. Nada é inventado: se a fonte não
responder, o comando falha e diz isso. Só contagens e totais são gravados;
nenhum nome de pessoa ou estabelecimento entra nas evidências.
Fontes testadas em 25/11/2026; detalhes em references/fontes-publicas.md.
"""
import argparse
import sys
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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
        print(f"Aviso: o RREO Anexo 14 de {a.ano} não traz o % aplicado em saúde (ainda não entregue, entregue sem "
              "esse bloco ou na forma simplificada). Use: python fontes.py siops --ano ...")

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

    # 3) e 4) Pessoal (RGF) e receita corrente líquida (RREO Anexo 03). Se falharem, o resto vale.
    for parte in (_rgf_pessoal, _rreo_rcl):
        try:
            feitos += parte(ev, m, a.ano)
        except c.SemRede as e:
            print(f"Aviso: {parte.__doc__} indisponível ({e}).")
    for f in feitos:
        print(c.resumo(f))
    if not feitos:
        sys.exit(1)


_MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _rgf_pessoal(ev, m, ano):
    """Despesa com pessoal (RGF Anexo 01)"""
    # Quadrimestral na maioria dos municípios; os pequenos entregam o RGF simplificado, por semestre.
    for an in (ano, ano - 1):
        for tipo, per, nrs in (("RGF", "Q", (3, 2, 1)), ("RGF Simplificado", "S", (2, 1)), ("RGF", "S", (2, 1))):
            for nr in nrs:
                params = {"an_exercicio": an, "in_periodicidade": per, "nr_periodo": nr, "co_tipo_demonstrativo": tipo,
                          "no_anexo": "RGF-Anexo 01", "co_esfera": "M", "co_poder": "E", "id_ente": m["ibge"]}
                linhas = c.get_json(f"{SICONFI}/rgf", params).get("items", [])
                pct = {l["cod_conta"]: float(l["valor"]) for l in linhas if l["coluna"].startswith("% sobre a RCL")}
                if "DespesaComPessoalTotal" not in pct:
                    continue
                url = f"{SICONFI}/rgf?" + urllib.parse.urlencode(params)
                mes = _MESES[(4 * nr if per == "Q" else 6 * nr) - 1]  # o RGF soma os 12 meses até o fim do período
                periodo = f"12 meses até {mes}/{an}"
                fonte = f"Siconfi/Tesouro Nacional, {tipo} Anexo 01 (Poder Executivo)"
                feitos = [c.item(ev, "pessoal_rcl_pct", "Despesa com pessoal do Executivo sobre a receita corrente líquida",
                                 pct["DespesaComPessoalTotal"], "%", fonte, url, periodo, "api")]
                for cod, id_, rot in (("LimitePrudencialDespesaComPessoalTotal", "pessoal_limite_prudencial", "Limite prudencial da LRF para pessoal"),
                                      ("LimiteMaximoDespesaComPessoalTotal", "pessoal_limite_maximo", "Limite máximo da LRF para pessoal")):
                    if cod in pct:
                        feitos.append(c.item(ev, id_, rot, pct[cod], "%", fonte, url, periodo, "api"))
                if "LimitePrudencialDespesaComPessoalTotal" in pct:
                    v = pct["LimitePrudencialDespesaComPessoalTotal"] - pct["DespesaComPessoalTotal"]
                    feitos.append(c.item(ev, "pessoal_folga_pp", "Folga até o limite prudencial de pessoal", v, "pontos percentuais",
                                         "Cálculo sobre Siconfi (RGF Anexo 01)", url, periodo, "calculo", casas=1,
                                         fmt=c.fmt_num(v, 1) + " p.p.", formula="pessoal_limite_prudencial − pessoal_rcl_pct",
                                         depende_de=["pessoal_limite_prudencial", "pessoal_rcl_pct"]))
                return feitos
    print(f"Aviso: RGF de {ano} e {ano - 1} não encontrado no Siconfi.")
    return []


_RREO3 = {
    "RREO3ReceitaCorrenteLiquida": ("rcl", "Receita corrente líquida (12 meses)"),
    "RREO3TransferenciasObrigatoriasDaUniaoRelativasAsEmendasIndividuais":
        ("emendas_individuais", "Emendas parlamentares individuais recebidas da União, todas as áreas (12 meses)"),
    "RREO3TransferenciasDaUniaoRelativasARemuneracaoDosAgentesComunitariosDeSaude":
        ("repasse_acs_ace", "Repasse da União para agentes comunitários de saúde e de endemias (12 meses)"),
}


def _rreo_rcl(ev, m, ano):
    """Receita corrente líquida (RREO Anexo 03)"""
    for bim in range(6, 0, -1):
        for tipo in ("RREO", "RREO Simplificado"):  # municípios pequenos entregam o simplificado
            params = {"an_exercicio": ano, "nr_periodo": bim, "co_tipo_demonstrativo": tipo,
                      "no_anexo": "RREO-Anexo 03", "id_ente": m["ibge"]}
            linhas = [l for l in c.get_json(f"{SICONFI}/rreo", params).get("items", [])
                      if l["cod_conta"] in _RREO3 and l["coluna"].upper().startswith("TOTAL")]
            if linhas:
                break
        if not linhas:
            continue
        url = f"{SICONFI}/rreo?" + urllib.parse.urlencode(params)
        periodo = f"12 meses até {_MESES[2 * bim - 1]}/{ano}"
        fonte = f"Siconfi/Tesouro Nacional, {tipo} Anexo 03"
        return [c.item(ev, _RREO3[l["cod_conta"]][0], _RREO3[l["cod_conta"]][1], float(l["valor"]), "R$", fonte, url, periodo, "api")
                for l in linhas]
    print(f"Aviso: RREO Anexo 03 de {ano} ainda não foi entregue ao Siconfi.")
    return []


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
                             formula=f"{d}_casos_{a.ano} / pop × 100.000", depende_de=[f"{d}_casos_{a.ano}", "pop"],
                             **c.instavel(total)))
    temps = [(f"SE {str(x['SE'])[-2:]}", x.get("tempmed")) for x in r if x.get("tempmed") is not None]
    if temps:
        c.serie(ev, f"clima_temp_{a.ano}", f"Temperatura média semanal em {a.ano}", "°C", "InfoDengue (dados climáticos)", link, "api", temps, casas=1)
    print(f"Série: {s['rotulo']} ({len(pontos)} semanas)")
    for f in feitos:
        print(c.resumo(f))


def _partes(funcoes, ev, m, *args):
    """Roda cada parte de um comando; uma fonte fora do ar não derruba as outras."""
    feitos = []
    for f in funcoes:
        try:
            feitos += f(ev, m, *args)
        except c.SemRede as e:
            print(f"Aviso: {f.__doc__} indisponível ({e}).")
    for f in feitos:
        print(c.resumo(f))
    if not feitos:
        sys.exit(1)


def _texto(v):
    """Classificações da APS ("BOM", "ESTRATO 4") como se escreve num texto."""
    return str(v).strip().lower()


# ------------------------------------------------------------------ atenção primária
# API do site oficial relatorioaps.saude.gov.br (sem documentação; testada em 25/11/2026).
APS = "https://relatorioaps-prd.saude.gov.br"
APS_SITE = "https://relatorioaps.saude.gov.br"


def _aps_cobertura(ev, m):
    """Cobertura da APS (Relatório Público da APS)"""
    base = {"unidadeGeografica": "MUNICIPIO", "coUf": m["ibge"][:2], "coMunicipio": m["ibge6"]}
    for comp in c.get_json(f"{APS}/data/competencias-cnes")[:4]:
        cob = c.get_json(f"{APS}/cobertura/aps", {**base, "nuCompInicio": comp, "nuCompFim": comp})
        if cob:
            break
    else:
        print("Aviso: sem cobertura da APS nas últimas competências.")
        return []
    x, periodo = cob[0], f"{comp[4:]}/{comp[:4]}"
    fonte = "Ministério da Saúde, Relatório Público da APS"
    link = f"{APS_SITE}/cobertura/aps"
    if (x.get("qtCobertura") or 0) > 100:
        print(f"Aviso: a cobertura oficial da APS passa de 100% ({c.fmt_pct(x['qtCobertura'])}), porque a capacidade das equipes "
              "supera a população. No texto, diga que a cobertura é total; não cite o número acima de 100%.")
    feitos = [
        c.item(ev, "aps_cobertura_pct", "Cobertura da atenção primária", x["qtCobertura"], "%", fonte, link, periodo, "api", casas=1),
        c.item(ev, "aps_esf", "Equipes de Saúde da Família (eSF) consideradas na cobertura", x["qtEsf"], "equipes", fonte, link, periodo, "api"),
        c.item(ev, "aps_eap", "Equipes de Atenção Primária (eAP) consideradas na cobertura",
               (x.get("qtEap20") or 0) + (x.get("qtEap30") or 0), "equipes", fonte, link, periodo, "api"),
    ]
    sb = c.get_json(f"{APS}/cobertura/sb/v2", {**base, "nuCompInicio": comp, "nuCompFim": comp})
    if sb:
        y = sb[0]
        feitos += [
            c.item(ev, "sb_cobertura_pct", "Cobertura de saúde bucal na atenção primária", y["pcCoberturaSbAps"], "%",
                   "Ministério da Saúde, Relatório Público da APS", f"{APS_SITE}/cobertura/sb", periodo, "api", casas=1),
            c.item(ev, "sb_equipes", "Equipes de saúde bucal na atenção primária",
                   sum(y.get(k) or 0 for k in ("qtEquipeSb40h", "qtEquipeSb30h", "qtEquipeSb20h")), "equipes",
                   "Ministério da Saúde, Relatório Público da APS", f"{APS_SITE}/cobertura/sb", periodo, "api"),
        ]
    acs = c.get_json(f"{APS}/cobertura/acs", {**base, "nuCompInicio": comp, "nuCompFim": comp})
    if acs:
        z = acs[0]
        num = lambda s: float(str(s).replace(",", ""))  # vem como texto: "162,133" e "72.70"
        feitos += [
            c.item(ev, "acs_cobertura_pct", "Cobertura de agentes comunitários de saúde", num(z["pcCoberturaAcsAb"]), "%",
                   "Ministério da Saúde, Relatório Público da APS", f"{APS_SITE}/cobertura/acs", periodo, "api", casas=1),
            c.item(ev, "acs_ativos", "Agentes comunitários de saúde ativos", int(num(z["qtAcsAtivoAb"])), "agentes",
                   "Ministério da Saúde, Relatório Público da APS", f"{APS_SITE}/cobertura/acs", periodo, "api"),
        ]
    return feitos


def _aps_pagamento(ev, m):
    """Pagamento federal da APS (Relatório Público da APS)"""
    base = {"unidadeGeografica": "MUNICIPIO", "coUf": m["ibge"][:2], "coMunicipio": m["ibge6"], "tipoRelatorio": "COMPLETO"}
    ano = datetime.now().year
    parcelas = c.get_json(f"{APS}/data/parcelas", {"ano": ano}) or c.get_json(f"{APS}/data/parcelas", {"ano": ano - 1})
    for p in parcelas[:3]:
        r = c.get_json(f"{APS}/financiamento/pagamento", {**base, "nuParcelaInicio": p, "nuParcelaFim": p})
        resumos = r.get("resumosPlanosOrcamentarios") or []
        if resumos:
            break
    else:
        print("Aviso: sem pagamento da APS nas últimas parcelas.")
        return []
    periodo = f"parcela {p[4:]}/{p[:4]}"
    fonte = "Ministério da Saúde, Relatório Público da APS"
    link = f"{APS_SITE}/financiamento/pagamento"
    integral = sum(x.get("vlIntegral") or 0 for x in resumos)
    desconto = -sum(x.get("vlDesconto") or 0 for x in resumos)  # a API manda o desconto negativo
    efetivo = sum(x.get("vlEfetivoRepasse") or 0 for x in resumos)
    feitos = [
        c.item(ev, "aps_repasse_mes", "Repasse federal da atenção primária no mês", efetivo, "R$", fonte, link, periodo, "api"),
        c.item(ev, "aps_repasse_integral", "Repasse federal da atenção primária que seria pago sem descontos", integral, "R$", fonte, link, periodo, "api"),
        c.item(ev, "aps_desconto_mes", "Desconto no repasse federal da atenção primária no mês", desconto, "R$", fonte, link, periodo, "api"),
    ]
    if integral:
        feitos.append(c.item(ev, "aps_desconto_pct", "Parcela do repasse da atenção primária perdida em descontos", desconto / integral * 100, "%",
                             "Cálculo sobre o Relatório Público da APS", link, periodo, "calculo",
                             formula="aps_desconto_mes / aps_repasse_integral × 100", depende_de=["aps_desconto_mes", "aps_repasse_integral"]))
    pag = (r.get("pagamentos") or [{}])[0]
    for campo, id_, rot in (("dsClassificacaoVinculoEsfEap", "aps_class_vinculo", "Classificação de vínculo e acompanhamento das eSF e eAP"),
                            ("dsClassificacaoQualidadeEsfEap", "aps_class_qualidade", "Classificação de qualidade das eSF e eAP"),
                            ("dsClassificacaoQualidadeEmulti", "aps_class_emulti", "Classificação de qualidade das equipes multiprofissionais (eMulti)"),
                            ("dsFaixaIndiceEquidadeEsfEap", "aps_estrato_equidade", "Faixa do índice de equidade usada no cofinanciamento")):
        v = pag.get(campo)
        if v and v.strip() not in ("-", ""):
            feitos.append(c.item(ev, id_, rot, v.strip(), "classificação", fonte, link, periodo, "api", fmt=_texto(v)))
    return feitos


def cmd_aps(a, ev):
    _partes([_aps_cobertura, _aps_pagamento], ev, _municipio(ev))


# ------------------------------------------------------------------ SIOPS
SIOPS = "https://siops-consulta-publica-api.saude.gov.br/v1"
# Indicadores municipais do SIOPS: número -> (id, rótulo, unidade). Valores recalculados de numerador/denominador.
_SIOPS = {
    "3.2": ("siops_asps_pct", "Receita própria aplicada em saúde (LC 141), segundo o SIOPS", "%"),
    "2.1": ("siops_desp_hab", "Despesa total com saúde por habitante, segundo o SIOPS", "R$"),
    "2.2": ("siops_pessoal_pct", "Parcela da despesa em saúde gasta com pessoal", "%"),
    "2.3": ("siops_medicamentos_pct", "Parcela da despesa em saúde gasta com medicamentos", "%"),
    "2.4": ("siops_terceiros_pct", "Parcela da despesa em saúde com serviços de terceiros (pessoa jurídica)", "%"),
    "2.5": ("siops_investimento_pct", "Parcela da despesa em saúde com investimentos", "%"),
    "3.1": ("siops_transf_pct", "Parcela da despesa em saúde coberta por transferências para a saúde", "%"),
    "1.4": ("siops_uniao_pct", "Parcela da União nas transferências que o município recebe para a saúde", "%"),
}


def cmd_siops(a, ev):
    m = _municipio(ev)
    # Códigos de período deduzidos em 25/11/2026: 2 = ano completo, 1 = 1º semestre. Só sai o que foi homologado.
    for ano, per, nome in ((a.ano, 2, "ano completo"), (a.ano, 1, "1º semestre"), (a.ano - 1, 2, "ano completo")):
        url = f"{SIOPS}/indicador/municipal/{m['ibge6']}/{ano}/{per}"
        try:
            linhas = c.get_json(url)
        except c.SemRede as e:
            if "404" in str(e):
                continue
            raise
        if linhas:
            break
    else:
        sys.exit(f"SIOPS sem dados homologados de {a.ano} nem de {a.ano - 1} para este município.")
    periodo, fonte = f"{ano} ({nome})", "SIOPS/Ministério da Saúde"
    feitos = []
    for l in linhas:
        if l["numero_indicador"] not in _SIOPS or not l.get("denominador"):
            continue
        id_, rot, un = _SIOPS[l["numero_indicador"]]
        v = l["numerador"] / l["denominador"] * (100 if un == "%" else 1)
        feitos.append(c.item(ev, id_, rot, v, un, fonte, url, periodo, "api"))
        if l["numero_indicador"] == "2.1":
            feitos.append(c.item(ev, "siops_desp_total", "Despesa total com saúde sob responsabilidade do município, segundo o SIOPS",
                                 l["numerador"], "R$", fonte, url, periodo, "api"))
    for f in feitos:
        print(c.resumo(f))


# ------------------------------------------------------------------ FNS
FNS = "https://consultafns.saude.gov.br/recursos/consulta-consolidada/repasse-bloco"
_FNS = {"atencao de media e alta complexidade ambulatorial e hospitalar": ("fns_mac", "Repasse federal para média e alta complexidade"),
        "atencao primaria": ("fns_aps", "Repasse federal para a atenção primária (custeio)"),
        "vigilancia em saude": ("fns_vigilancia", "Repasse federal para a vigilância em saúde"),
        "assistencia farmaceutica": ("fns_farm", "Repasse federal para a assistência farmacêutica"),
        "gestao do sus": ("fns_gestao", "Repasse federal para a gestão do SUS")}


def cmd_repasses(a, ev):
    m = _municipio(ev)
    params = {"page": 1, "count": 50, "ano": a.ano, "sgUf": m["uf"], "coMunicipioIbge": m["ibge6"]}
    blocos = c.get_json(FNS, params, timeout=90).get("resultado") or []  # a 1ª consulta do dia pode levar ~15 s
    if not blocos:
        sys.exit(f"FNS sem repasses fundo a fundo em {a.ano} para este município.")
    hoje = datetime.now()
    periodo = str(a.ano) if a.ano < hoje.year else f"{a.ano} (até {hoje:%d/%m})"
    fonte = "Fundo Nacional de Saúde, repasses fundo a fundo"
    url = f"{FNS}?ano={a.ano}&sgUf={m['uf']}&coMunicipioIbge={m['ibge6']}&page=1&count=50"
    custeio = next((b for b in blocos if _norm(b["nome"]).startswith("manutencao")), None)
    invest = next((b for b in blocos if _norm(b["nome"]).startswith("estruturacao")), None)
    feitos = []
    if custeio:
        feitos += [c.item(ev, "fns_custeio", "Repasse federal de custeio da saúde (bruto)", custeio["vlTotal"], "R$", fonte, url, periodo, "api"),
                   c.item(ev, "fns_desconto", "Descontos no repasse federal de custeio", custeio.get("vlDesconto") or 0, "R$", fonte, url, periodo, "api")]
        for g in custeio.get("repasses") or []:
            if _norm(g["nome"]) in _FNS:
                id_, rot = _FNS[_norm(g["nome"])]
                feitos.append(c.item(ev, id_, rot, g["vlTotal"], "R$", fonte, url, periodo, "api"))
        it = ev["itens"]
        if custeio["vlTotal"]:
            for id_, rot in (("fns_mac", "média e alta complexidade"), ("fns_aps", "atenção primária")):
                if id_ in it and it[id_]["periodo"] == periodo:
                    feitos.append(c.item(ev, f"{id_}_pct", f"Parcela do custeio federal que foi para {rot}", it[id_]["valor"] / custeio["vlTotal"] * 100,
                                         "%", "Cálculo sobre o FNS", url, periodo, "calculo",
                                         formula=f"{id_} / fns_custeio × 100", depende_de=[id_, "fns_custeio"]))
            if custeio.get("vlDesconto"):
                feitos.append(c.item(ev, "fns_desconto_pct", "Parcela do custeio federal perdida em descontos",
                                     custeio["vlDesconto"] / custeio["vlTotal"] * 100, "%", "Cálculo sobre o FNS", url, periodo, "calculo",
                                     formula="fns_desconto / fns_custeio × 100", depende_de=["fns_desconto", "fns_custeio"]))
    if invest:
        feitos.append(c.item(ev, "fns_investimento", "Repasse federal para investimento (estruturação da rede)", invest["vlTotal"], "R$", fonte, url, periodo, "api"))
    total = sum(b.get("vlTotal") or 0 for b in blocos)
    feitos.append(c.item(ev, "fns_total", "Repasses federais fundo a fundo para a saúde (bruto)", total, "R$", fonte, url, periodo, "api"))
    if "pop" in ev["itens"]:
        v = total / ev["itens"]["pop"]["valor"]
        feitos.append(c.item(ev, "fns_hab", "Repasses federais para a saúde por habitante", v, "R$", "Cálculo sobre FNS e IBGE", url,
                             f"{periodo} (população {ev['itens']['pop']['periodo']})", "calculo", fmt="R$ " + c.fmt_num(v, 0),
                             formula="fns_total / pop", depende_de=["fns_total", "pop"]))
    for f in feitos:
        print(c.resumo(f))


# ------------------------------------------------------------------ contexto (IBGE)
# Censo 2022: (tabela, variável, classificação, categoria, id, rótulo). Variável 1000381 = % dos domicílios.
_CENSO_PCT = [
    (6805, 1000381, "11558", "46290", "esgoto_adequado_pct", "Domicílios com esgoto na rede geral, pluvial ou em fossa ligada à rede"),
    (6803, 1000381, "1821", "72144", "agua_rede_pct", "Domicílios abastecidos principalmente pela rede geral de água"),
    (6892, 1000381, "67", "2520", "lixo_coletado_pct", "Domicílios com lixo coletado"),
]
# Indicadores do IBGE Cidades: id -> (id da evidência, rótulo, unidade, casas)
_CIDADES = {30279: ("mort_infantil", "Taxa de mortalidade infantil (óbitos por mil nascidos vivos)", "por mil nascidos vivos", 1),
            60032: ("intern_diarreia", "Internações por diarreia pelo SUS (por 100 mil habitantes)", "por 100 mil habitantes", 1),
            329756: ("idhm", "Índice de Desenvolvimento Humano Municipal (IDHM)", "índice", 3)}


def _num(v):
    """Valor do IBGE como número. Na convenção do IBGE, "-" é zero (ex.: nenhum óbito no ano):
    tratá-lo como falta faria o script pular para um ano antigo. "X" (sigilo), "..." e vazio viram None."""
    if isinstance(v, str) and v.strip() == "-":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _ibge_v3(tabela, variavel, m, classificacao=None):
    params = {"localidades": f"N6[{m['ibge']}]"}
    if classificacao:
        params["classificacao"] = classificacao
    return c.get_json(f"{IBGE}/v3/agregados/{tabela}/periodos/-1/variaveis/{variavel}", params)


def _censo(ev, m):
    """Censo 2022 do IBGE"""
    feitos = []
    for tab, var, cl, cat, id_, rot in _CENSO_PCT:
        r = _ibge_v3(tab, var, m, f"{cl}[{cat}]")
        ano, v = list(r[0]["resultados"][0]["series"][0]["serie"].items())[0]
        if _num(v) is not None:
            feitos.append(c.item(ev, id_, rot, _num(v), "%", f"IBGE, Censo {ano} (tabela {tab})", f"https://sidra.ibge.gov.br/tabela/{tab}", ano, "api"))
    r = _ibge_v3(9543, 2513, m, "2[6794]|86[95251]|287[100362]")
    ano, v = list(r[0]["resultados"][0]["series"][0]["serie"].items())[0]
    if _num(v) is not None:
        feitos.append(c.item(ev, "alfabetizacao_pct", "Taxa de alfabetização das pessoas de 15 anos ou mais", _num(v), "%",
                             f"IBGE, Censo {ano} (tabela 9543)", "https://sidra.ibge.gov.br/tabela/9543", ano, "api"))
    for x in _ibge_v3(9515, "10612|10613", m):
        ano, v = list(x["resultados"][0]["series"][0]["serie"].items())[0]
        if _num(v) is None:
            continue
        if x["id"] == "10612":
            feitos.append(c.item(ev, "indice_envelhecimento", "Índice de envelhecimento (pessoas com 65 anos ou mais para cada 100 de 0 a 14 anos)",
                                 _num(v), "por 100 jovens", f"IBGE, Censo {ano} (tabela 9515)", "https://sidra.ibge.gov.br/tabela/9515", ano, "api", casas=1))
        else:
            feitos.append(c.item(ev, "idade_mediana", "Idade mediana da população", _num(v), "anos",
                                 f"IBGE, Censo {ano} (tabela 9515)", "https://sidra.ibge.gov.br/tabela/9515", ano, "api", casas=0))
    # População por faixa etária: o total e as faixas de 5 anos (mais "100 anos ou mais"). "-" é faixa vazia.
    r = _ibge_v3(9514, 93, m, "2[6794]|286[113635]|287[all]")
    faixas = {}
    for res in r[0]["resultados"]:
        nome = list(res["classificacoes"][-1]["categoria"].values())[0]
        ano, v = list(res["series"][0]["serie"].items())[0]
        faixas[nome] = int(_num(v) or 0)
    fonte, link = f"IBGE, Censo {ano} (tabela 9514)", "https://sidra.ibge.gov.br/tabela/9514"
    total = faixas.get("Total")
    idosos = sum(v for k, v in faixas.items()
                 if (k.split()[0].isdigit() and " a " in k and int(k.split()[0]) >= 60) or k == "100 anos ou mais")
    if total:
        feitos += [c.item(ev, "pop_censo", "População recenseada", total, "habitantes", fonte, link, ano, "api", casas=0),
                   c.item(ev, "pop_0a4", "Crianças de 0 a 4 anos", faixas.get("0 a 4 anos"), "crianças", fonte, link, ano, "api", casas=0),
                   c.item(ev, "pop_60mais", "Pessoas com 60 anos ou mais", idosos, "pessoas", "Cálculo sobre IBGE (soma das faixas de 60 anos ou mais)",
                          link, ano, "calculo", casas=0, formula="soma das faixas de 60 a 64 anos até 100 anos ou mais", depende_de=["pop_censo"]),
                   c.item(ev, "pop_60mais_pct", "Parcela da população com 60 anos ou mais", idosos / total * 100, "%", "Cálculo sobre IBGE (Censo)",
                          link, ano, "calculo", formula="pop_60mais / pop_censo × 100", depende_de=["pop_60mais", "pop_censo"])]
    return feitos


def _cidades(ev, m):
    """Indicadores do IBGE Cidades"""
    feitos = []
    obitos = None
    try:  # óbitos de menores de 1 ano: diz se a taxa de mortalidade infantil é estável
        r = c.get_json(f"{IBGE}/v1/pesquisas/indicadores/78160/resultados/{m['ibge']}")
        serie_ = r[0]["res"][0]["res"]
        obitos = {k: _num(v) for k, v in serie_.items() if _num(v) is not None}
    except (c.SemRede, LookupError, ValueError):
        pass
    for ind, (id_, rot, un, casas) in _CIDADES.items():
        r = c.get_json(f"{IBGE}/v1/pesquisas/indicadores/{ind}/resultados/{m['ibge']}")
        serie_ = {k: _num(v) for k, v in r[0]["res"][0]["res"].items() if _num(v) is not None}
        if not serie_:
            continue
        ano = max(serie_)
        link = f"{IBGE}/v1/pesquisas/indicadores/{ind}/resultados/{m['ibge']}"
        extra = c.instavel(obitos.get(ano)) if (id_ == "mort_infantil" and obitos) else {}
        feitos.append(c.item(ev, id_, rot, serie_[ano], un, "IBGE Cidades", link, ano, "api", casas=casas, **extra))
        if id_ == "mort_infantil" and obitos and ano in obitos:
            feitos.append(c.item(ev, "obitos_infantis", "Óbitos de menores de 1 ano", obitos[ano], "óbitos", "IBGE Cidades", link, ano, "api", casas=0))
        if id_ in ("mort_infantil", "intern_diarreia") and len(serie_) >= 3:
            pontos = sorted(serie_.items())[-10:]
            c.serie(ev, f"{id_}_serie", rot.replace(" (", ", série anual (", 1), un, "IBGE Cidades", link, "api", pontos, casas=casas)
    return feitos


def cmd_contexto(a, ev):
    _partes([_censo, _cidades], ev, _municipio(ev))


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
    sub.add_parser("aps")
    s = sub.add_parser("siops"); s.add_argument("--ano", type=int, required=True)
    s = sub.add_parser("repasses"); s.add_argument("--ano", type=int, required=True)
    sub.add_parser("contexto")
    a = p.parse_args()
    if a.cmd == "municipio" and not (a.nome or a.ibge):
        p.error("informe --nome (com --uf) ou --ibge")
    ev = c.carregar(a.evidencias)
    try:
        {"municipio": cmd_municipio, "populacao": cmd_populacao, "financas": cmd_financas,
         "cnes": cmd_cnes, "arbovirose": cmd_arbovirose, "aps": cmd_aps, "siops": cmd_siops,
         "repasses": cmd_repasses, "contexto": cmd_contexto}[a.cmd](a, ev)
    except c.SemRede as e:
        sys.exit(f"FONTE INDISPONÍVEL: {e}\nSe o ambiente bloqueia a internet (chat na nuvem ou Codex com a rede desligada), "
                 "peça acesso à rede se puder; se não, siga só com os arquivos enviados e diga isso no documento.")
    c.salvar(ev, a.evidencias)


if __name__ == "__main__":
    main()
