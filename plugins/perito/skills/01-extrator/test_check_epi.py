#!/usr/bin/env python3
"""Teste de regressão do guard de EPI (check_epi.py) — trava o comportamento crítico que
evoluiu muito (gap temporal, cobertura contínua, FLAGS, idempotência). Base-INDEPENDENTE:
não precisa do caepi.sqlite — classifica por palavra-chave/regra absoluta + TYPE_VU.

Rodar:  python3 scripts/test_check_epi.py     (exit 0 = tudo passou)
Motivo: em 06/06 o guard ficou MORTO por dias sem ninguém notar (parser mudou). Este teste
falha na hora se uma mudança futura quebrar a classificação, o gap ou a cobertura.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_epi as ce


class FakeCaepi:
    """CAEPI vazio — força o guard a classificar por regra absoluta / palavra-chave (sem base)."""
    has_vu = False
    build_date = None
    def get(self, ca):
        return None
    def age_days(self):
        return None


FAKE = FakeCaepi()
FALHAS = []


def check(cond, nome):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + nome)
    if not cond:
        FALHAS.append(nome)


def linhas(imprescrito, entregas):
    """Monta um formulário mínimo (formato Notas) com campo imprescrito + tabela de entregas."""
    out = []
    if imprescrito:
        out.append("Período imprescrito: ★ de %s até %s" % imprescrito)
    out.append("TABELA DE FORNECIMENTO DE EPIs")
    out += entregas
    out.append("▶ OBSERVAÇÕES GERAIS")
    return out


def gaps_de(res):
    return [r for r in res if "DESCOBERTO" in r]


# T1 — creme sem C.A. conhecido cai na regra absoluta → An.13 (nunca radiação/solar)
def t1_creme_regra_absoluta():
    print("T1 — creme → An.13 (regra absoluta, sem base)")
    lns = ["• 01/01/2023 · 1un · CREME PROT PELE XYZ · CA 99999"]
    r = ce.process(lns, {}, FAKE)
    classified = r[1] if len(r) == 4 else r[0]   # plugin: (new_lines, fixes, ...); squad: (classified, ...)
    check(any(c[3] == "regra absoluta" and c[2] == ce.AN13 for c in classified),
          "creme classificado como Químico dérmico (An.13) por regra absoluta")


# T2 — gap único de ruído é detectado e datado
def t2_gap_unico():
    print("T2 — gap único de protetor (ruído)")
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 12/07/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 07/03/2023 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2023 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/12/2023 · 1un · PROT AURIC SILICONE · CA 5745"]
    res, faltou, scoped, cov, gaps = ce.cobertura(linhas(("09/03/2022", "31/12/2023"), ent), {}, FAKE)
    g = gaps_de(res)
    check(len(g) >= 1 and any("07/03/2023" in x for x in g),
          "período descoberto detectado terminando em 07/03/2023")
    st = gaps.get("Ruído (An.1)") or ""
    check("⚠" in st and "ver 📐" in st,
          "status do slot marca o gatilho (⚠ … ver 📐): %r" % st)


# T3 — vários gaps curtos (cada <30d) que somados passam de 1 mês → alerta agregado
def t3_morte_por_mil_cortes():
    print("T3 — acumulado (vários gaps de ~20d) não passa batido")
    ent = ["• 01/01/2023 · 1un · CREME PROT LUVEX · CA 11070",
           "• 20/02/2023 · 1un · CREME PROT LUVEX · CA 11070",
           "• 10/04/2023 · 1un · CREME PROT LUVEX · CA 11070",
           "• 30/05/2023 · 1un · CREME PROT LUVEX · CA 11070",
           "• 20/07/2023 · 1un · CREME PROT LUVEX · CA 11070"]
    res, faltou, scoped, cov, gaps = ce.cobertura(linhas(("01/01/2023", "31/07/2023"), ent), {}, FAKE)
    g = gaps_de(res)
    check(any("TOTAL" in x for x in g), "gaps curtos somados disparam alerta de TOTAL")


# T4 — entrega ANTES da janela cobre o início → NÃO acusar gap de abertura falso
def t4_split_sem_falso_positivo():
    print("T4 — cobertura herdada de entrega pré-janela (split-imprescrito)")
    ent = ["• 15/05/2022 · 1un · PROT AURIC SILICONE · CA 5745",   # antes do imprescrito (01/06)
           "• 01/11/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/05/2023 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 20/10/2023 · 1un · PROT AURIC SILICONE · CA 5745"]
    res, faltou, scoped, cov, gaps = ce.cobertura(linhas(("01/06/2022", "31/12/2023"), ent), {}, FAKE)
    check(len(gaps_de(res)) == 0, "nenhum gap de abertura falso (entrega pré-janela herda cobertura)")
    check(gaps.get("Ruído (An.1)") == "contínuo, sem gap",
          "status do slot = 'contínuo, sem gap' quando não há gap material: %r" % gaps.get("Ruído (An.1)"))


# T5 — cobertura é CONTÍNUA (janela − buracos), não a soma Σ que inflava
def t5_cobertura_continua():
    print("T5 — cobertura contínua (não a soma Σ)")
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 12/07/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 07/03/2023 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2023 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/12/2023 · 1un · PROT AURIC SILICONE · CA 5745"]
    res, faltou, scoped, cov, gaps = ce.cobertura(linhas(("09/03/2022", "31/12/2023"), ent), {}, FAKE)
    ruido = cov.get("Ruído (An.1)")
    # janela ~21,8 meses; Σ seria 5×6=30. Contínua tem de ser ≤ janela (e não a soma).
    check(ruido is not None and ruido <= 22.0 and ruido > 17.0,
          "cobertura contínua dentro da janela (~20 m, não a soma 30): %.1f" % (ruido or -1))


# T6 — inject_flags_epi: injeta na seção FLAGS, idempotente, no-op sem a seção
def t6_inject_flags():
    print("T6 — injeção de EPI no FLAGS (idempotente)")
    body = ("## 🚩 FLAGS PARA O PERITO\n1. algo\n\n## ▶ OUTRA\n")
    b1 = ce.inject_flags_epi(body, "Ruído — descoberto X")
    b2 = ce.inject_flags_epi(b1, "Ruído — descoberto X")
    check(b2.count(ce.FLAGS_EPI_MARK) == 1, "linha do guard aparece exatamente 1× após 2 runs")
    b3 = ce.inject_flags_epi(b2, None)
    check(ce.FLAGS_EPI_MARK not in b3, "summary None remove a linha (limpeza)")
    semflags = ce.inject_flags_epi("## ▶ SEM FLAGS\ntexto\n", "qualquer")
    check(ce.FLAGS_EPI_MARK not in semflags, "no-op quando não há seção FLAGS")


# T7 — ficha sem EPI contínuo: não inventa gap, não quebra
def t7_sem_epi_continuo():
    print("T7 — sem creme/protetor: sem gap, sem crash")
    ent = ["• 01/01/2023 · 1un · BOTINA BICO ACO · CA 12217",
           "• 01/01/2023 · 1un · CAPACETE · CA 29638"]
    res, faltou, scoped, cov, gaps = ce.cobertura(linhas(("01/01/2023", "31/12/2023"), ent), {}, FAKE)
    check(len(gaps_de(res)) == 0, "nenhum período descoberto inventado")


# T8 — idempotência do bloco completo no arquivo (run 2× = 1 bloco)
def t8_idempotencia_arquivo():
    print("T8 — idempotência do guard no arquivo (.md)")
    ent = "\n".join(["• 09/03/2022 · 1un · CREME PROT LUVEX · CA 11070",
                     "• 09/02/2024 · 1un · CREME PROT LUVEX · CA 11070"])
    doc = ("Período imprescrito: ★ de 09/03/2022 até 15/04/2025\n\n"
           "## ▶ EPI — RESUMO (An.13)\n • Creme: cobre __/__ meses\n\n"
           "TABELA DE FORNECIMENTO DE EPIs\n" + ent + "\n\n▶ OBSERVAÇÕES GERAIS\n")
    fd, path = tempfile.mkstemp(suffix=".md")
    os.close(fd)
    try:
        open(path, "w", encoding="utf-8").write(doc)
        # roda 2× via main() simulando argv
        for _ in range(2):
            old_argv = sys.argv
            sys.argv = ["check_epi.py", path]
            try:
                try:
                    ce.main()
                except SystemExit:
                    pass
            finally:
                sys.argv = old_argv
        txt = open(path, encoding="utf-8").read()
        check(txt.count(ce.MARK) == 1, "bloco 🚩 VERIFICAÇÃO aparece 1× após 2 runs")
        check(txt.count("(ver 📐)") == 1, "status de gap no slot do RESUMO aparece 1× (idempotente)")
    finally:
        os.unlink(path)


def main():
    print("== Teste de regressão do guard de EPI ==")
    for t in (t1_creme_regra_absoluta, t2_gap_unico, t3_morte_por_mil_cortes,
              t4_split_sem_falso_positivo, t5_cobertura_continua, t6_inject_flags,
              t7_sem_epi_continuo, t8_idempotencia_arquivo):
        t()
    print()
    if FALHAS:
        print("RESULTADO: %d FALHA(S) — %s" % (len(FALHAS), "; ".join(FALHAS)))
        return 1
    print("RESULTADO: todos os testes passaram ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
