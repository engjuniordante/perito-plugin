#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ficha_dedicada.py — a ficha de EPI em notebook PRÓPRIO (T7).

Roda offline: nenhum destes testes fala com o `nlm`. O que eles travam é a parte
DETERMINÍSTICA do T7 — quem vai para o notebook dedicado, que marco temporal a
Parte 3a leva junto quando sai da conversa do lote, e o digest que a Parte 3b
recebe no lugar da tabela inteira.

Cada caso aqui é um jeito de perder entrega de EPI em silêncio, que é o modo de
falhar que o perito só descobre na diligência, com a ficha na mão.

    python test_ficha_dedicada.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrai_processo import (          # noqa: E402
    achar_ficha, separar_ficha, imprescrito_de, resumo_ficha,
)

falhas = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        falhas.append(label)


def P(nome):
    """Um Path de PDF, só para nome — nada é lido do disco."""
    return Path("/proc") / nome


# ── A. qual PDF é a ficha ────────────────────────────────────────────────────
print("A — achar_ficha reconhece a ficha pelas grafias que o perito usa")

ok(achar_ficha([P("3-ficha-epi.pdf")]).name == "3-ficha-epi.pdf",
   "'3-ficha-epi' é ficha")
ok(achar_ficha([P("3-EPI.pdf")]).name == "3-EPI.pdf",
   "'3-EPI' (maiúscula) é ficha")
ok(achar_ficha([P("4-ficha de epi.pdf")]).name == "4-ficha de epi.pdf",
   "'4-ficha de epi' é ficha")
ok(achar_ficha([P("2-CONTESTAÇÃO E DOCUMENTOS.pdf")]) is None,
   "contestação não é ficha")
ok(achar_ficha([P("1-peticao inicial.pdf"), P("4-ata-agendamento-quesitos.pdf")]) is None,
   "inicial e ata não são ficha (nenhuma contém 'epi'/'ficha')")

quatro = [P("1-inicial.pdf"), P("2-contestacao.pdf"),
          P("3-ficha-epi.pdf"), P("4-ata-agendamento-quesitos.pdf")]
ok(achar_ficha(quatro).name == "3-ficha-epi.pdf",
   "na pasta de 4 partes, elege só a ficha")

# ── B. o que sobra para o notebook do lote ───────────────────────────────────
print("\nB — separar_ficha: o lote nunca pode ficar sem fonte")

ficha, lote = separar_ficha(quatro)
ok(ficha is not None and len(lote) == 3 and ficha not in lote,
   "4 PDFs → ficha isolada, 3 no lote")

ficha, lote = separar_ficha(quatro, ficha_no_lote=True)
ok(ficha is None and len(lote) == 4,
   "--ficha-no-lote → comportamento antigo, 4 no lote")

so_ficha = [P("3-ficha-epi.pdf")]
ficha, lote = separar_ficha(so_ficha)
ok(ficha is None and len(lote) == 1,
   "ficha É O ÚNICO PDF → NÃO isola (senão o lote fica com zero fonte e P1/P2/P4 morrem)")

sem_ficha = [P("1-inicial.pdf"), P("2-contestacao.pdf")]
ficha, lote = separar_ficha(sem_ficha)
ok(ficha is None and len(lote) == 2,
   "sem arquivo de ficha (ela vem embutida na contestação) → nada muda")

# ── C. o marco do imprescrito que a 3a leva na mão ───────────────────────────
print("\nC — imprescrito_de: a 3a saiu da conversa do lote e precisa da data explícita")

p1_fechado = "- Período trabalhado: de 01/03/2018 a 15/06/2024\n" \
             "- Período imprescrito: de 21/09/2023 até 01/10/2025"
ok(imprescrito_de(p1_fechado) == "21/09/2023", "intervalo fechado 'de … até'")

ok(imprescrito_de("- Período imprescrito: 26/01/2021 a 26/01/2026") == "26/01/2021",
   "sem a palavra 'de' → pega a primeira data")

# o motivo de existir o limpar() aqui dentro: no Gemini a linha vem assim.
p1_gemini = "*   **Período imprescrito:** de 21/09/2023 até 01/10/2025 [Image 5]"
ok(imprescrito_de(p1_gemini) == "21/09/2023",
   "dialeto Gemini (negrito + [Image 5]) → mesma data")

ok(imprescrito_de("- Período imprescrito: NÃO LOCALIZADO\n- Nº: 0011183-33") is None,
   "imprescrito não localizado → None (não pesca a data da linha seguinte)")
ok(imprescrito_de("") is None and imprescrito_de(None) is None,
   "P1 vazia/ausente → None")

# ── D. o digest que substitui a tabela na Parte 3b ───────────────────────────
print("\nD — resumo_ficha: o que a 3b recebe no lugar da tabela inteira")

p3a = (
    "| DATA | QTD | EQUIPAMENTO | C.A. |\n"
    "|---|---|---|---|\n"
    "| 31/01/2020 | 1 | LUVA NITRILICA | 5745 |\n"
    "| 01/02/2021 | 2 | PROTETOR AURICULAR | 12345 |\n"
    "| 09/03/2022 | 1 | BOTINA | não informado |\n"
)
d = resumo_ficha(p3a)
ok("- entregas registradas: 3" in d, "conta as 3 linhas de entrega (e não o cabeçalho)")
ok("5745" in d and "12345" in d, "lista os C.A. reais")
ok("2020" not in d.split("C.A. distintos")[-1] and "2022" not in d.split("C.A. distintos")[-1],
   "o ANO da coluna de data NÃO vira C.A. fantasma")
ok("31/01/2020 a 01/02/2021" not in d, "faixa não é ordenada como string crua…")
ok("- período coberto pela ficha: 31/01/2020 a 09/03/2022" in d,
   "…e sim por (ano, mês, dia): 31/01/2020 a 09/03/2022")
ok("- entregas SEM C.A. informado: 1" in d, "acusa a entrega sem C.A.")

p3a_gemini = (
    "| **DATA** | **QTD** | **EQUIPAMENTO** | **C.A.** |\n"
    "|---|---|---|---|\n"
    "| **09/03/2022** [Image 20] | 1 | LUVA NITRILICA | 5745 [12] |\n"
    "| **14/07/2023** | 2 | PROTETOR AURICULAR | 12345 [Image 21] |\n"
)
dg = resumo_ficha(p3a_gemini)
ok("- entregas registradas: 2" in dg,
   "dialeto Gemini (negrito + citação na célula) → as 2 entregas contam")
ok("5745" in dg and "12345" in dg, "dialeto Gemini → C.A. saem limpos")

ok(resumo_ficha("") == "" and resumo_ficha(None) == "",
   "3a vazia → digest vazio (a 3b vai sem contexto, e o chamador avisa)")

gorda = "| DATA | QTD | EQUIP | C.A. |\n" + "".join(
    f"| 0{(i % 9) + 1}/03/2022 | 1 | LUVA | {10000 + i} |\n" for i in range(200))
dgorda = resumo_ficha(gorda)
ok(len(dgorda) <= 1200, "ficha de 200 entregas → digest respeita o limite de 1200 chars")
ok("- entregas registradas: 200" in dgorda,
   "…e o número de entregas sobrevive ao corte (vem antes da lista de C.A.)")

# ── resultado ────────────────────────────────────────────────────────────────
print()
if falhas:
    print(f"FALHOU ({len(falhas)}):")
    for f in falhas:
        print("  - " + f)
    sys.exit(1)
print("✓ tudo verde — ficha de EPI em notebook próprio (T7)")
