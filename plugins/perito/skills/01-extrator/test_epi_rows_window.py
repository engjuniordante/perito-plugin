#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Teste de regressão do recorte da tabela de EPI (montar_formulario.parse_ficha_rows).

Ponto cego do montador: o recorte das linhas dependia do marcador ▼ emitido pelo NLM. Se o NLM não
o emitia, a tabela inundava com histórico pré-vínculo; se o emitia, a EPI de admissão acima do ▼
sumia (não havia janela de graça). E ficha com 100% das entregas anteriores ao imprescrito zerava a
tabela em silêncio (parecia 'EPI não carregou', mas é ACHADO: não cobre o período).

Régua: recorta por DATA na janela [início_imprescrito − GRACE, demissão], usando o periodo_impr
DETERMINÍSTICO (clamp_imprescrito) — imune ao ▼. Ficha 100% fora da janela vira linha de achado.

uso: python3 test_epi_rows_window.py
"""
import sys

import montar_formulario as mf

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ ") + msg)
    if not cond:
        FALHAS.append(msg)


def has(rows, frag):
    return any(frag in r for r in rows)


IMPR, DEM = "02/03/2020", "20/12/2022"  # max(admissão, ação−5a) … demissão
SEM_MARC = ("| 10/01/2018 | 1 | Luva velha | 11111 |\n"
            "| 02/03/2020 | 2 | Luva adm | 22222 |\n"
            "| 15/06/2021 | 1 | Bota | 33333 |\n")


def main():
    print("E1 — sem ▼ + janela determinística: mantém admissão+imprescrito, corta pré-vínculo")
    rows = mf.parse_ficha_rows(SEM_MARC, IMPR, DEM)
    check(has(rows, "02/03/2020"), "EPI de admissão entra (era o bug: sumia)")
    check(has(rows, "15/06/2021"), "EPI do imprescrito entra")
    check(not has(rows, "10/01/2018"), "histórico pré-vínculo (2018) fica fora")

    print("E2 — entrega ANTES da admissão dentro da graça (≤31d) entra; fora sai")
    f_in = "| 28/02/2020 | 2 | Luva adm | 22222 |\n| 15/06/2021 | 1 | Bota | 33333 |\n"
    f_out = "| 02/01/2020 | 2 | Pre-pacto | 22222 |\n| 15/06/2021 | 1 | Bota | 33333 |\n"
    check(has(mf.parse_ficha_rows(f_in, IMPR, DEM), "28/02/2020"), "3d antes da admissão entra")
    check(not has(mf.parse_ficha_rows(f_out, IMPR, DEM), "02/01/2020"), "60d antes da admissão sai")

    print("E3 — recorte ao fim do contrato: entrega após a demissão sai")
    f_post = "| 15/06/2021 | 1 | Bota | 33333 |\n| 10/01/2023 | 1 | Pos | 44444 |\n"
    rows = mf.parse_ficha_rows(f_post, IMPR, DEM)
    check(has(rows, "15/06/2021") and not has(rows, "10/01/2023"), "pós-demissão fica fora")

    print("E4 — ficha 100% PRÉ-IMPRESCRITO: tabela não sai vazia, vira ACHADO explícito")
    f_pre = "| 05/01/2018 | 1 | Luva | 11111 |\n| 10/03/2019 | 1 | Bota | 22222 |\n"
    rows = mf.parse_ficha_rows(f_pre, IMPR, DEM)
    check(len(rows) == 1 and "NENHUMA entrega de EPI no período imprescrito" in rows[0],
          "uma linha de achado nomeando a ausência de cobertura")
    check(rows and "05/01/2018–10/03/2019" in rows[0] and "02/03/2020" in rows[0],
          "achado mostra faixa de datas e cita o início do imprescrito")

    print("E5 — fallback gracioso: sem janela determinística, recorta pelo ▼ (legado)")
    ficha_marc = ("| 10/01/2018 | 1 | Luva velha | 11111 |\n"
                  "▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO\n"
                  "| 15/06/2021 | 1 | Bota | 33333 |\n")
    rows = mf.parse_ficha_rows(ficha_marc)
    check(has(rows, "15/06/2021") and not has(rows, "10/01/2018"), "fallback ▼ ainda filtra")

    print()
    if FALHAS:
        print(f"FALHAS: {len(FALHAS)}")
        for f in FALHAS:
            print("  -", f)
        sys.exit(1)
    print("OK: tabela de EPI recortada por data, imune ao marcador ▼ (ponto cego do montador zerado)")


if __name__ == "__main__":
    main()
