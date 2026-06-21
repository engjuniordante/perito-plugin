#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste de regressão do recorte do imprescrito (montar_formulario.clamp_imprescrito).

Cobre o bug VILCINEI × VFX/SYLVAMO (contrato 11/09/2024–01/05/2025): o montador colocava o marco
prescricional quinquenal (16/09/2020) na posição de 'fim' do imprescrito, saindo INVERTIDO
(de 01/05/2025 até 16/09/2020). A trava B1 (validate_imprescrito_sanity) pegava, mas o auto-fix
falhava → correção manual.

Causa raiz: o clamp era UNIDIRECIONAL (só puxava o fim p/ baixo) e dependia da ORDEM em que o NLM
escrevia as datas (fim = última data no texto). Quando o marco quinquenal vinha por último — prosa
'retroagindo a…' ou datas reversas — escapava do recorte.

Régua: seja qual for o fraseado do NLM, o imprescrito converge p/ o intervalo do contrato (contrato
curto) ou preserva o marco quinquenal DENTRO do contrato (contrato longo). Nunca inverte.

uso: python3 test_imprescrito.py
"""
import sys

import montar_formulario as mf

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FALHAS.append(msg)


TRAB_V = "de 11/09/2024 até 01/05/2025"
ESP_V = "de 11/09/2024 até 01/05/2025"
CASOS_V = {
    "ordem normal (marco a 01/05)": "16/09/2020 a 01/05/2025",
    "prosa retroagindo (marco no fim)": "A partir de 01/05/2025, retroagindo o quinquênio a 16/09/2020",
    "datas reversas (invertia)": "de 01/05/2025 até 16/09/2020",
    "data única = marco de início": "A partir de 16/09/2020",
    "marco no fim em prosa": "Imprescrito: contrato até 01/05/2025; prescrição quinquenal alcança 16/09/2020",
}

TRAB_K = "de 18/09/2009 até 15/08/2024"
ESP_K = "de 06/09/2020 até 15/08/2024"
CASOS_K = {
    "marco como início explícito": "06/09/2020 a 15/08/2024",
    "data única dentro do contrato": "A partir de 06/09/2020",
}


def main():
    print("I1 — VILCINEI: contrato curto, imprescrito = contrato inteiro (ordem-independente)")
    for nome, txt in CASOS_V.items():
        out = mf.clamp_imprescrito(txt, TRAB_V)
        check(out == ESP_V, f"{nome} → {out}")

    print("I2 — KELLY: contrato longo, marco quinquenal dentro do contrato sobrevive")
    for nome, txt in CASOS_K.items():
        out = mf.clamp_imprescrito(txt, TRAB_K)
        check(out == ESP_K, f"{nome} → {out}")

    print("I3 — não-inversão: nunca devolve início > fim (invariante da trava B1)")
    for txt in list(CASOS_V.values()) + list(CASOS_K.values()):
        for trab in (TRAB_V, TRAB_K):
            out = mf.clamp_imprescrito(txt, trab)
            ds = __import__("re").findall(r"\d{2}/\d{2}/\d{4}", out)
            inverte = len(ds) >= 2 and mf._iso(ds[0]) > mf._iso(ds[-1])
            check(not inverte, f"sem inversão: {out}")

    print("I4 — vazio intacto; data interior (afastamento) não move min/max")
    check(mf.clamp_imprescrito("", TRAB_V) == "", "vazio sem ação → devolve intacto")
    interior = mf.clamp_imprescrito("de 09/03/2022 até 15/04/2025 (afast. 01/01/2023)",
                                    "de 09/03/2022 até 15/04/2025")
    check(interior == "de 09/03/2022 até 15/04/2025", f"data interior ignorada → {interior}")

    print("I5 — PISO QUINQUENAL determinístico (com Data da ação): início = max(admissão, ação−5a)")
    C = mf.clamp_imprescrito
    check(C("06/09/2020 a 15/08/2024", TRAB_K, "06/09/2025") == ESP_K, "KELLY: NLM certo confirmado")
    check(C("01/01/2021 a 15/08/2024", TRAB_K, "06/09/2025") == ESP_K, "KELLY: NLM ERRADO → forçado ao piso 06/09/2020")
    check(C("", TRAB_K, "06/09/2025") == ESP_K, "KELLY: sem valor do NLM → montado do contrato+ação")
    check(C("24/08/2020 a 24/08/2025", "de 09/03/2022 até 15/04/2025", "24/08/2025")
          == "de 09/03/2022 até 15/04/2025", "RAFAEL: marco pré-admissão → pacto inteiro")
    check(C("de 01/05/2025 até 16/09/2020", TRAB_V, "16/09/2025") == ESP_V, "VILCINEI: invertido+ação → pacto inteiro")
    check(mf._menos_cinco_anos("29/02/2024") == "28/02/2019", "edge 29/02/2024−5a → 28/02/2019")

    print("I6 — 4ª invariante B1 (validate_form): início ≠ piso quinquenal → flag")
    import validate_form as vf
    bad = ("Data da ação: 06/09/2025 [interno]\n"
           "Período trabalhado: de 18/09/2009 até 15/08/2024\n"
           "Período imprescrito: ★ de 01/01/2021 até 15/08/2024\n")
    f = []; vf.validate_imprescrito_sanity(bad, f)
    check(any("piso quinquenal" in x for x in f), "KELLY com início errado (01/01/2021) → flag de piso")
    good = ("Data da ação: 06/09/2025 [interno]\n"
            "Período trabalhado: de 18/09/2009 até 15/08/2024\n"
            "Período imprescrito: ★ de 06/09/2020 até 15/08/2024\n")
    f = []; vf.validate_imprescrito_sanity(good, f)
    check(not f, "KELLY com início no piso (06/09/2020) → sem flag")

    print()
    if FALHAS:
        print(f"FALHOU: {len(FALHAS)} verificação(ões)")
        for f in FALHAS:
            print("  -", f)
        sys.exit(1)
    print("OK: recorte do imprescrito robusto à ordem do NLM (VILCINEI zerado)")


if __name__ == "__main__":
    main()
