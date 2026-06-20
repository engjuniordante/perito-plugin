#!/usr/bin/env python3
"""Regressão do gate determinístico do plugin (validate_form.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_form as vf

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def v_imprescrito_sanity():
    print("V1 — sanidade do imprescrito (recorte ao contrato)")
    pre_adm = ("Período trabalhado: de 09/03/2022 até 15/04/2025\n"
               "Período imprescrito ★: de 24/08/2020 até 15/04/2025\n")
    f = []
    vf.validate_imprescrito_sanity(pre_adm, f)
    check(any("ANTES da admissão" in x for x in f), "início pré-admissão → flag")

    pos_dem = ("Período trabalhado: de 09/03/2022 até 15/04/2025\n"
               "Período imprescrito ★: de 09/03/2022 até 24/08/2025\n")
    f = []
    vf.validate_imprescrito_sanity(pos_dem, f)
    check(any("DEPOIS da demissão" in x for x in f), "fim pós-demissão → flag")

    ok = ("Período trabalhado: de 09/03/2022 até 15/04/2025\n"
          "Período imprescrito ★: de 09/03/2022 até 15/04/2025\n")
    f = []
    vf.validate_imprescrito_sanity(ok, f)
    check(not f, "imprescrito == contrato → sem flag")

    f = []
    vf.validate_imprescrito_sanity("Período imprescrito ★: de 09/03/2022 até 15/04/2025\n", f)
    check(not f, "sem campo de contrato → no-op")


def v_process_identity():
    print("V2 — identidade do processo (form × bundle)")
    form = "## ▶ PROCESSO\n- Nº: 0015098-90.2025.5.15.0071\n"
    f = []
    vf.validate_process_identity(form, "Processo 0011354-87.2025.5.15.0071\n", f)
    check(any("DIVERGE" in x for x in f), "nº do form ≠ nº do bundle → flag")

    f = []
    vf.validate_process_identity(form, "Processo 0015098-90.2025.5.15.0071\n", f)
    check(not f, "mesmo processo → sem flag")

    f = []
    vf.validate_process_identity("- Nº:\n", "0015098-90.2025.5.15.0071\n", f)
    check(any("ausente" in x for x in f), "form sem nº → flag")


def v_guard_block():
    print("V3 — guard-block presente")
    import check_epi as ce
    f = []
    vf.validate_guard_block("formulário sem carimbo do guard", f)
    check(any("guard" in x.lower() for x in f), "sem MARK do guard → flag")

    f = []
    vf.validate_guard_block(f"corpo\n{ce.MARK}\nresto", f)
    check(not f, "MARK presente → sem flag")


def main():
    print("== Regressão do gate do plugin (validate_form) ==")
    for t in (v_imprescrito_sanity, v_process_identity, v_guard_block):
        t()
    print()
    if FALHAS:
        print("RESULTADO: %d FALHA(S) — %s" % (len(FALHAS), "; ".join(FALHAS)))
        sys.exit(1)
    print("RESULTADO: todos os testes passaram ✓")


if __name__ == "__main__":
    main()
