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


# T9 — guard crava a linha NR-6 "Frequência regular" a partir da cobertura (idempotente)
def t9_nr6_frequencia():
    print("T9 — guard preenche a linha NR-6 'Frequência regular'")
    # corpo MULTI-LINHA (a linha NR-6 NÃO é a última) — pega o bug do regex sem re.M, em que
    # '.*$' só casava se a linha fosse o fim do texto (passava em linha única e falhava no real).
    body = ("▶ COMPROVAÇÃO NR-6\n"
            "• Frequência regular de fornecimento (🔄) — [ ]Sim [ ]Não · obs:\n"
            "• Adequado ao risco ambiental (👤) — [ ]Sim [ ]Não · obs:\n"
            "▶ OBSERVAÇÕES GERAIS\n")
    line = "• Frequência regular de fornecimento (🔄) — [ ]Sim [ ]Não · obs:"
    cov = {"Ruído (An.1)": 31.1}
    gap = {"Ruído (An.1)": "⚠ 4 janelas ~17.6m (ver 📐)"}
    b1 = ce.fill_nr6_frequencia(body, cov, gap)
    freq = next(l for l in b1.splitlines() if "Frequência regular" in l)
    check("[X]Não" in freq and "[ ]Sim" in freq, "gap material → [X]Não / [ ]Sim: %r" % freq)
    check("ver 📐" in freq, "obs traz o resumo do gap")
    check("[ ]Sim [ ]Não" in b1, "linha 'Adequado ao risco' (👤) fica intacta — só a frequência muda")
    check(ce.fill_nr6_frequencia(b1, cov, gap) == b1, "2ª passada não duplica nem altera")
    b3 = ce.fill_nr6_frequencia(line, {"Ruído (An.1)": 48.0}, {"Ruído (An.1)": "contínuo, sem gap"})
    check("[X]Sim" in b3 and "[ ]Não" in b3, "contínuo → [X]Sim: %r" % b3)
    check(ce.fill_nr6_frequencia(body, {}, {}) == body, "sem cobertura → corpo intacto")


# T10 — janela de cobertura recortada ao FIM DO CONTRATO (não à data da ação)
def t10_clamp_fim_contrato():
    print("T10 — clamp da janela ao fim do contrato (sem exposição pós-demissão)")
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 02/01/2024 · 1un · PROT AURIC SILICONE · CA 5745"]
    base = ["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
            "Período trabalhado: de 15/09/2008 até 11/10/2024",
            "TABELA DE FORNECIMENTO DE EPIs"] + ent + ["▶ OBSERVAÇÕES GERAIS"]
    meses = ce._imprescrito_months("\n".join(base))
    check(meses is not None and 47.0 < meses < 50.0,
          "denominador recortado ao contrato (~49m, não ~60): %.1f" % (meses or -1))
    res, faltou, scoped, cov, gaps = ce.cobertura(base, {}, FAKE)
    check(gaps_de(res) and not any("/2025" in x for x in res),
          "nenhuma data de gap após o fim do contrato (zero /2025): %r" % res)
    check(any("11/10/2024" in x for x in res), "a cauda do gap termina no fim do contrato (11/10/2024)")
    semtrab = [l for l in base if not l.startswith("Período trabalhado")]
    meses2 = ce._imprescrito_months("\n".join(semtrab))
    check(meses2 is not None and meses2 > 58.0, "sem campo de contrato → sem clamp (~60m): %.1f" % (meses2 or -1))


# T11 — desconto automático de afastamento (exposição = imprescrito − afastamento)
def t11_desconto_afastamento():
    print("T11 — desconto automático de afastamento (Opção 1, à prova de erro)")
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 02/01/2024 · 1un · PROT AURIC SILICONE · CA 5745"]
    afast_block = ["▶ AFASTAMENTOS / PERÍODOS EXCLUIR",
                   "De: 08/01/2024  até: 31/01/2024  motivo: B31",
                   "De: 01/02/2024  até: 10/10/2024  motivo: limbo",
                   "Total excluído: ~276 dias"]
    base = (["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
             "Período trabalhado: de 15/09/2008 até 11/10/2024"] + afast_block
            + ["TABELA DE FORNECIMENTO DE EPIs"] + ent + ["▶ OBSERVAÇÕES GERAIS"])
    res, faltou, scoped, cov, gaps = ce.cobertura(base, {}, FAKE)
    expo_line = next((x for x in res if "de exposição" in x), "")
    import re as _re
    den = float(_re.search(r"de ~([\d.]+) meses de exposição", expo_line).group(1)) if expo_line else 0
    check("de exposição" in expo_line and 39.0 <= den <= 41.0,
          "denominador = exposição ~40m (não o imprescrito ~49): %.1f" % den)
    fr = next((x for x in res if x.startswith("Exposição =")), "")
    check("imprescrito" in fr and "afastamento" in fr and "2 períodos" in fr,
          "frase clara da conta presente: %r" % fr)
    check(any("afastamentos descontados:" in x and "08/01/2024" in x and "01/02/2024" in x for x in res),
          "eco dos períodos descontados presente")
    check(gaps_de(res) and not any("11/10/2024" in x for x in res),
          "janela dentro do afastamento sumiu do gap (não há /11/10/2024): %r" % res)
    cobertura_m = cov.get("Ruído (An.1)", 0)
    check(abs((cobertura_m + 27.7) - den) < 1.5, "cobertura + gap ≈ exposição (reconcilia): %.1f + 27.7 vs %.1f" % (cobertura_m, den))
    # ANTI-COVID: De:/até: de COVID na seção do agente M NÃO é lido como afastamento
    covid = (["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
              "TABELA DE FORNECIMENTO DE EPIs"] + ent
             + ["▶ OBSERVAÇÕES GERAIS", "M. AGENTES BIOLÓGICOS",
                "[ ] Período de COVID-19 (pandemia) — De: 01/03/2020  até: 31/12/2021"])
    af, ok = ce._afastamentos("\n".join(covid))
    check(af == [] and ok, "COVID De:/até: fora da seção AFASTAMENTOS NÃO é descontado: %r" % af)
    # data ilegível → não desconta + avisa
    ruim = ["▶ AFASTAMENTOS / PERÍODOS EXCLUIR", "De: 08/01/2024  até: (ilegível)  motivo: x", "▶ FIM"]
    _, ok2 = ce._afastamentos("\n".join(ruim))
    check(not ok2, "linha De: com data ilegível → ok=False (degrada pro manual)")
    # sem bloco AFASTAMENTOS → no-op
    af2, ok3 = ce._afastamentos("\n".join(["Período imprescrito: ★ de 17/09/2020 até 11/10/2024"]))
    check(af2 == [] and ok3, "sem bloco AFASTAMENTOS → ([], True) = no-op")


def main():
    print("== Teste de regressão do guard de EPI ==")
    for t in (t1_creme_regra_absoluta, t2_gap_unico, t3_morte_por_mil_cortes,
              t4_split_sem_falso_positivo, t5_cobertura_continua, t6_inject_flags,
              t7_sem_epi_continuo, t8_idempotencia_arquivo, t9_nr6_frequencia,
              t10_clamp_fim_contrato, t11_desconto_afastamento):
        t()
    print()
    if FALHAS:
        print("RESULTADO: %d FALHA(S) — %s" % (len(FALHAS), "; ".join(FALHAS)))
        return 1
    print("RESULTADO: todos os testes passaram ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
