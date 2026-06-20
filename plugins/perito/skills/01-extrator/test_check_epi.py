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


# T0 — parser de C.A. lida com pontuação e ambiguidade sem inventar catálogo faltante
def t0_extract_ca():
    print("T0 — parser de C.A. (pontuação / ambiguidade)")
    check(ce.extract_ca("• 23/07/2018 · 1un · Protetor Auricular · CA 16.048") == "16048",
          "CA com ponto vira 16048")
    check(ce.extract_ca("• 23/10/2017 · 1un · Oculos · CA 10.346/107") == "10346",
          "CA com sufixo /107 preserva o núcleo 10346")
    check(ce.extract_ca("• 31/03/2014 · 1un · Protetor Auricular · CA [20541 / 97022?]") is None,
          "CA ambíguo com dois números não classifica no chute")


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
    # '.*$' só casava se a linha fosse o fim do texto (passava no teste de linha única e falhava
    # no formulário real). Mantém a régua deste arquivo: testar como roda de verdade.
    body = ("▶ COMPROVAÇÃO NR-6\n"
            "• Frequência regular de fornecimento (🔄) — [ ]Sim [ ]Não · obs:\n"
            "• Adequado ao risco ambiental (👤) — [ ]Sim [ ]Não · obs:\n"
            "▶ OBSERVAÇÕES GERAIS\n")
    line = "• Frequência regular de fornecimento (🔄) — [ ]Sim [ ]Não · obs:"
    cov = {"Ruído (An.1)": 31.1}
    gap = {"Ruído (An.1)": "⚠ 4 janelas ~17.6m (ver 📐)"}
    # com gap material → [X]Não + resumo, NO MEIO de um corpo multi-linha
    b1 = ce.fill_nr6_frequencia(body, cov, gap)
    freq = next(l for l in b1.splitlines() if "Frequência regular" in l)
    check("[X]Não" in freq and "[ ]Sim" in freq, "gap material → [X]Não / [ ]Sim: %r" % freq)
    check("ver 📐" in freq, "obs traz o resumo do gap")
    check("[ ]Sim [ ]Não" in b1, "linha 'Adequado ao risco' (👤) fica intacta — só a frequência muda")
    # idempotência: 2ª passada mantém a mesma saída
    check(ce.fill_nr6_frequencia(b1, cov, gap) == b1, "2ª passada não duplica nem altera")
    # cobertura contínua → [X]Sim
    b3 = ce.fill_nr6_frequencia(line, {"Ruído (An.1)": 48.0}, {"Ruído (An.1)": "contínuo, sem gap"})
    check("[X]Sim" in b3 and "[ ]Não" in b3, "contínuo → [X]Sim: %r" % b3)
    # sem cobertura (ficha sem protetor/creme) → corpo intacto (perito decide)
    check(ce.fill_nr6_frequencia(body, {}, {}) == body, "sem cobertura → corpo intacto")


# T9b — guard crava a linha NR-6 "Anotação do C.A." distinguindo item certificável de complementar
def t9b_nr6_ca():
    print("T9b — guard preenche a linha NR-6 'Anotação do C.A.'")
    body = ("▶ COMPROVAÇÃO NR-6\n"
            "• Anotação do C.A., só EPI certificável (🔄) — [ ]Sim [X]Não · obs: texto antigo\n"
            "• Adequado ao risco ambiental (👤) — [ ]Sim [ ]Não · obs:\n"
            "TABELA DE FORNECIMENTO DE EPIs\n"
            "• 09/03/2022 · 1un · BOTINA BICO ACO · CA 12217\n"
            "• 09/03/2022 · 1un · CAMISA BRIM MANGA LONGA · CA nao informado\n"
            "▶ OBSERVAÇÕES GERAIS\n")
    b1 = ce.fill_nr6_ca(body)
    line = next(l for l in b1.splitlines() if "Anotação do C.A." in l)
    check("[X]Sim" in line and "[ ]Não" in line,
          "item complementar sem C.A. não derruba a linha: %r" % line)
    check("não-certificáveis/complementares" in line,
          "obs explica o porquê do Sim com itens sem C.A.")

    body2 = ("▶ COMPROVAÇÃO NR-6\n"
             "• Anotação do C.A., só EPI certificável (🔄) — [X]Sim [ ]Não · obs: texto antigo\n"
             "TABELA DE FORNECIMENTO DE EPIs\n"
             "• 09/03/2022 · 1un · LUVA NITRILICA · CA nao informado\n"
             "▶ OBSERVAÇÕES GERAIS\n")
    b2 = ce.fill_nr6_ca(body2)
    line2 = next(l for l in b2.splitlines() if "Anotação do C.A." in l)
    check("[ ]Sim" in line2 and "[X]Não" in line2,
          "EPI certificável sem C.A. derruba a linha: %r" % line2)
    check("EPI certificável sem C.A." in line2, "obs explica a inconformidade")


# T10 — janela de cobertura recortada ao FIM DO CONTRATO (não à data da ação)
def t10_clamp_fim_contrato():
    print("T10 — clamp da janela ao fim do contrato (sem exposição pós-demissão)")
    # imprescrito vai até a data da ação (17/09/2025), mas o contrato terminou em 11/10/2024.
    # Entregas só até jan/2024 → a janela/denominador NÃO podem ir até 2025.
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 02/01/2024 · 1un · PROT AURIC SILICONE · CA 5745"]
    base = ["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
            "Período trabalhado: de 15/09/2008 até 11/10/2024",
            "TABELA DE FORNECIMENTO DE EPIs"] + ent + ["▶ OBSERVAÇÕES GERAIS"]
    # (a) denominador reflete o fim do CONTRATO (~48,8m de 17/09/2020), não a ação (~60m)
    meses = ce._imprescrito_months("\n".join(base))
    check(meses is not None and 47.0 < meses < 50.0,
          "denominador recortado ao contrato (~49m, não ~60): %.1f" % (meses or -1))
    # (b) nenhuma janela de gap se estende além de 11/10/2024 (datas vivem nas linhas de detalhe)
    res, faltou, scoped, cov, gaps = ce.cobertura(base, {}, FAKE)
    check(gaps_de(res) and not any("/2025" in x for x in res),
          "nenhuma data de gap após o fim do contrato (zero /2025): %r" % res)
    check(any("11/10/2024" in x for x in res), "a cauda do gap termina no fim do contrato (11/10/2024)")
    # (c) CONTROLE — sem "Período trabalhado", comportamento atual (sem clamp): janela vai até 2025
    semtrab = [l for l in base if not l.startswith("Período trabalhado")]
    meses2 = ce._imprescrito_months("\n".join(semtrab))
    check(meses2 is not None and meses2 > 58.0, "sem campo de contrato → sem clamp (~60m): %.1f" % (meses2 or -1))


def t10b_clamp_inicio_admissao():
    print("T10b — clamp do início do imprescrito à admissão (sem gap fantasma pré-emprego)")
    # Caso real Rafael × MAHLE (0015098-90, 20/06): o NLM devolveu o imprescrito como '5 anos da
    # data da ação' (24/08/2020 a 24/08/2025) SEM recortar ao pacto (admissão 09/03/2022). Sem o
    # clamp de início, 24/08/2020→09/03/2022 (pré-admissão) entra como 'descoberto' e infla o gap.
    ent = ["• 09/03/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 01/09/2022 · 1un · PROT AURIC SILICONE · CA 5745",
           "• 02/01/2024 · 1un · PROT AURIC SILICONE · CA 5745"]
    base = ["Período imprescrito: ★ de 24/08/2020 até 24/08/2025",
            "Período trabalhado: de 09/03/2022 até 15/04/2025",
            "TABELA DE FORNECIMENTO DE EPIs"] + ent + ["▶ OBSERVAÇÕES GERAIS"]
    # (a) denominador parte da ADMISSÃO (~37m de pacto), não dos 5 anos da ação (~60m)
    meses = ce._imprescrito_months("\n".join(base))
    check(meses is not None and 36.0 < meses < 40.0,
          "denominador recortado à admissão (~38m, não ~60): %.1f" % (meses or -1))
    # (b) nenhuma janela de gap começa antes da admissão (zero datas de 2020/2021)
    res, faltou, scoped, cov, gaps = ce.cobertura(base, {}, FAKE)
    check(not any(("/2020" in x or "/2021" in x) for x in res),
          "nenhum gap pré-admissão (zero /2020 e /2021): %r" % res)
    # (c) CONTROLE — sem "Período trabalhado", sem clamp: janela parte de 2020 (~60m)
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
    # (a) reconcilia: cobertura + gap = exposição; denominador = exposição (imprescrito clampado
    # 48.8m − afastamento 9.0m = ~39.8m), não o imprescrito cheio
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
    g = gaps_de(res)
    check(g and not any("11/10/2024" in x for x in res),
          "janela dentro do afastamento sumiu do gap (não há /11/10/2024): %r" % res)
    # reconcilia: cobertura (~12) + gap (~27.7) ≈ exposição (~39.8)
    cobertura_m = cov.get("Ruído (An.1)", 0)
    check(abs((cobertura_m + 27.7) - den) < 1.5, "cobertura + gap ≈ exposição (reconcilia): %.1f + 27.7 vs %.1f" % (cobertura_m, den))
    # (b) ANTI-COVID: De:/até: de COVID na seção do agente M NÃO é lido como afastamento
    covid = (["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
              "Período trabalhado: de 15/09/2008 até 11/10/2024",
              "TABELA DE FORNECIMENTO DE EPIs"] + ent
             + ["▶ OBSERVAÇÕES GERAIS",
                "M. AGENTES BIOLÓGICOS",
                "[ ] Período de COVID-19 (pandemia) — De: 01/03/2020  até: 31/12/2021"])
    af, ok = ce._afastamentos("\n".join(covid))
    check(af == [] and ok, "COVID De:/até: fora da seção AFASTAMENTOS NÃO é descontado: %r" % af)
    # (c) afastamento FORA do imprescrito → ignorado
    fora = ["De: 01/01/2010 até: 31/12/2010 motivo: antigo"]
    check(ce._afastamento_days_in([(__import__("datetime").date(2010,1,1), __import__("datetime").date(2010,12,31))],
          __import__("datetime").date(2020,9,17), __import__("datetime").date(2024,10,11)) == 0,
          "afastamento fora da janela → 0 dias")
    # (d) data ilegível → não desconta + avisa
    ruim = (["Período imprescrito: ★ de 17/09/2020 até 17/09/2025",
             "▶ AFASTAMENTOS / PERÍODOS EXCLUIR", "De: 08/01/2024  até: (ilegível)  motivo: x",
             "▶ FIM"])
    _, ok2 = ce._afastamentos("\n".join(ruim))
    check(not ok2, "linha De: com data ilegível → ok=False (degrada pro manual)")
    # (e) sem bloco AFASTAMENTOS → no-op (igual v1.30)
    semaf = ["Período imprescrito: ★ de 17/09/2020 até 11/10/2024",
             "TABELA DE FORNECIMENTO DE EPIs"] + ent + ["▶ OBSERVAÇÕES GERAIS"]
    af2, ok3 = ce._afastamentos("\n".join(semaf))
    check(af2 == [] and ok3, "sem bloco AFASTAMENTOS → ([], True) = no-op")


# T12 — guarda rejeita classificação implausível do CAEPI para descrição incompatível
def t12_classificacao_implausivel():
    print("T12 — filtro de classificação implausível do CAEPI")
    class FakeOddCaepi:
        has_vu = False
        build_date = None
        def get(self, ca):
            return {"agente": "Radiação não-ionizante (An.7)", "equipamento": "respirador purificador"}
        def age_days(self):
            return None
    weird = FakeOddCaepi()
    classified, flags, nao_cat = ce.process(
        ["• 01/01/2024 · 1un · MASCARA SEMIFACIAL CONTRA GASES E VAPORES · CA 15019"],
        {},
        weird,
    )
    check(any(c[2] == ce.AN11 for c in classified),
          "máscara respiratória não cai em An.7 quando a descrição aponta An.11")
    classified2, flags2, _ = ce.process(
        ["• 01/01/2024 · 1un · CAPACETE DE SEGURANCA · CA 15366"],
        {},
        type("FakeCap", (), {
            "has_vu": False,
            "build_date": None,
            "get": lambda self, ca: {"agente": "Frio (An.9)", "equipamento": "capacete"},
            "age_days": lambda self: None,
        })(),
    )
    check(not classified2 and any("implausível" in f[1] or "implausivel" in f[1] for f in flags2),
          "capacete com agente implausível vira flag, não classificação")


# T13 — guard sobrescreve cobertura antiga do EPI — RESUMO para impedir drift
def t13_inline_coverage_overwrite():
    print("T13 — sobrescrita autoritativa do EPI — RESUMO")
    body = ("\n".join([
        "Período imprescrito: ★ de 01/01/2023 até 31/12/2023",
        "EPI — RESUMO (imprescrito)",
        " • Protetor (ruído): __un · CA__ · cobre 99/99 meses · ⚠ 9 janelas ~99m (ver 📐) · [ ]✓ [ ]⚠gap [ ]✗",
        "TABELA DE FORNECIMENTO DE EPIs",
        "• 01/01/2023 · 1un · PROT AURIC SILICONE · CA 5745",
        "• 01/07/2023 · 1un · PROT AURIC SILICONE · CA 5745",
        "▶ OBSERVAÇÕES GERAIS",
    ]))
    res = ce.cobertura(body.splitlines(), {}, FAKE)
    out = ce.fill_inline_coverage(body, res[3], res[4], ce._imprescrito_months(body))
    line = next(l for l in out.splitlines() if "Protetor (ruído):" in l)
    check("99/99" not in line and ("contínuo, sem gap" in line or "ver 📐" in line),
          "guard substitui valores antigos do resumo por cobertura recalculada: %r" % line)
    check("[ ]✓ [ ]⚠gap [ ]✗" in line,
          "guard preserva o trecho de checkbox/veredicto do perito: %r" % line)


# T14 — guard preenche quantidade/CA/material dos slots do EPI — RESUMO (v1.34)
def t14_resumo_items():
    print("T14 — preenchimento do EPI — RESUMO (quantidade/CA/material por slot)")
    body = "\n".join([
        "Período imprescrito: ★ de 01/01/2023 até 31/12/2023",
        "EPI — RESUMO (imprescrito)",
        " • Protetor (ruído): __un · CA__ · cobre __/__ meses · [ ]✓ [ ]⚠gap [ ]✗",
        " • Creme (óleo/álcali An.13): __potes · cobre __/__ meses · [ ]✓ [ ]⚠ [ ]✗",
        " • Luva imperm.: __pares · __material (látex/nitríl./PVC)",
        " • Máscara/resp.: __un · [ ]PFF1 [ ]PFF2 [ ]PFF3 [ ]cartucho VO",
        "TABELA DE FORNECIMENTO DE EPIs",
        "• 01/01/2023 · 23un · PROT AURIC SILICONE · CA 5745",
        "• 01/02/2023 · 34un · CREME PROT LUVEX SP · CA 11070",
        "• 01/03/2023 · 10un · LUVA NITRILICA · CA 28011",
        "• 01/03/2023 · 5un · LUVA RASPA PUNHO · CA 8048",
        "• 01/04/2023 · 50un · MASCARA PFF2 · CA 2072",
        "▶ OBSERVAÇÕES GERAIS",
    ])
    out = ce.fill_resumo_items(body, body.splitlines(), {}, FAKE)
    prot = next(l for l in out.splitlines() if "Protetor (ruído):" in l)
    creme = next(l for l in out.splitlines() if "Creme" in l and "An.13" in l)
    luva = next(l for l in out.splitlines() if "Luva imperm.:" in l)
    mask = next(l for l in out.splitlines() if "Máscara/resp.:" in l)
    check("23un CA 5745" in prot, "Protetor consolidado: %r" % prot)
    check("· cobre __/__ meses" in prot, "Protetor preserva o segmento de cobertura: %r" % prot)
    check("34 potes CA 11070" in creme, "Creme em 'potes': %r" % creme)
    check("10un CA 28011" in luva and "[X]nitril" in luva, "Luva impermeável consolidada+material: %r" % luva)
    check("8048" not in luva, "Luva de raspa NÃO entra no slot 'imperm.': %r" % luva)
    check("50un CA 2072" in mask and "[X]PFF2" in mask, "Máscara consolidada + PFF2: %r" % mask)
    out2 = ce.fill_resumo_items(out, out.splitlines(), {}, FAKE)
    check(out2 == out, "fill_resumo_items é idempotente")


# T15 — conjunto C (Defensivo/Umidade) + conjunto NÃO entra no slot de luva avulsa (v1.34)
def t15_resumo_conjunto():
    print("T15 — conjunto C Defensivo/Umidade + 'conjunto' fora da luva avulsa")
    body = "\n".join([
        "Período imprescrito: ★ de 01/01/2023 até 31/12/2023",
        "EPI — RESUMO (imprescrito)",
        " • Luva imperm.: __pares · __material (látex/nitríl./PVC)",
        " • Umidade An.10:  bota[ ] avental[ ] luva[ ]",
        " • Defensivo An.13:  conjunto/pulveriz.[ ] bota[ ] luva[ ] resp/PFF2[ ] viseira[ ] touca árabe[ ]",
        "TABELA DE FORNECIMENTO DE EPIs",
        "• 01/03/2023 · 1un · CONJUNTO IMPERMEAVEL CAQUI (LUVA C/CAPUZ) · CA 2636",
        "• 01/03/2023 · 3un · LUVA NITRILICA · CA 5774",
        "• 01/03/2023 · 1un · BOTA PVC · CA 38200",
        "• 01/03/2023 · 1un · RESPIRADOR PFF2 · CA 2072",
        "▶ OBSERVAÇÕES GERAIS",
    ])
    out = ce.fill_resumo_items(body, body.splitlines(), {}, FAKE)
    luva = next(l for l in out.splitlines() if "Luva imperm.:" in l)
    defv = next(l for l in out.splitlines() if "Defensivo An.13:" in l)
    umi = next(l for l in out.splitlines() if "Umidade An.10:" in l)
    check("CONJUNTO" not in luva.upper(), "conjunto NÃO entra no slot de luva avulsa: %r" % luva)
    check("CA 5774" in luva, "luva nitrílica avulsa entra na luva: %r" % luva)
    check("conjunto/pulveriz.[X]" in defv and "resp/PFF2[X]" in defv and "bota[X]" in defv,
          "Defensivo C marca conjunto/resp/bota: %r" % defv)
    check("bota[X]" in umi and "luva[X]" in umi, "Umidade C marca bota/luva: %r" % umi)
    out2 = ce.fill_resumo_items(out, out.splitlines(), {}, FAKE)
    check(out2 == out, "conjunto C idempotente")


# T16 — conjunto Frio An.9: japona conta; "luva altas temperaturas" (CALOR) NÃO conta (v1.34)
def t16_resumo_frio():
    print("T16 — Frio An.9 (japona marca; 'altas temperaturas' = calor, fora)")
    body = "\n".join([
        "Período imprescrito: ★ de 01/01/2024 até 31/12/2024",
        "EPI — RESUMO (imprescrito)",
        " • Frio An.9:  __peças (japona/calça/luva/balaclava/bota)",
        "TABELA DE FORNECIMENTO DE EPIs",
        "• 15/04/2024 · 1un · JAPONA TERMICA · CA 14943",
        "• 15/04/2024 · 1un · LUVA ALTAS TEMPERATURAS · CA 28688",
        "▶ OBSERVAÇÕES GERAIS",
    ])
    out = ce.fill_resumo_items(body, body.splitlines(), {}, FAKE)
    frio = next(l for l in out.splitlines() if "Frio An.9:" in l)
    check("japona[X]" in frio and "14943" in frio, "japona térmica marcada: %r" % frio)
    check("luva[ ]" in frio, "luva de CALOR (altas temp.) NÃO conta como frio: %r" % frio)
    out2 = ce.fill_resumo_items(out, out.splitlines(), {}, FAKE)
    check(out2 == out, "Frio idempotente")


def main():
    print("== Teste de regressão do guard de EPI ==")
    for t in (t0_extract_ca, t1_creme_regra_absoluta, t2_gap_unico, t3_morte_por_mil_cortes,
              t4_split_sem_falso_positivo, t5_cobertura_continua, t6_inject_flags,
              t7_sem_epi_continuo, t8_idempotencia_arquivo, t9_nr6_frequencia,
              t9b_nr6_ca,
              t12_classificacao_implausivel, t13_inline_coverage_overwrite,
              t14_resumo_items, t15_resumo_conjunto, t16_resumo_frio,
              t10_clamp_fim_contrato, t10b_clamp_inicio_admissao, t11_desconto_afastamento):
        t()
    print()
    if FALHAS:
        print("RESULTADO: %d FALHA(S) — %s" % (len(FALHAS), "; ".join(FALHAS)))
        return 1
    print("RESULTADO: todos os testes passaram ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
