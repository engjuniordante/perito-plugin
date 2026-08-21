#!/usr/bin/env python3
"""Teste de DIALETO: o mesmo conteúdo, no formato antigo do NotebookLM e no dialeto do
Gemini Notebook, tem de produzir o MESMO formulário.

Por que este teste existe: os defeitos de formatação não quebram nada — o script devolve
código 0 e o formulário abre bem formatado, só que com campos vazios. Testar cada função
isolada não pega, porque a função está certa e quem chega errado é o argumento. Só pega
quem exercita o montador INTEIRO, da entrada crua ao formulário final.

Dialeto Gemini (colhido em processo real): bullet antes do ▶, negrito nos rótulos,
referência de imagem na citação ([Image 115]), divisória *** e citação dentro da célula
da ficha.
"""
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import montar_formulario as mf

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


ANTIGO = """▶ PROCESSO E EMPRESA
- Nº: 0011203-24.2025.5.15.0071
- Vara: 1ª Vara do Trabalho de Mogi Guaçu
- Reclamante: MARIA DA SILVA
- Reclamada: OMYA BRASIL LTDA
- Autuação (data de propositura): 26/01/2026
- CNAE da atividade principal: 08.10-0-01

▶ IDENTIFICAÇÃO / VÍNCULO
- Período trabalhado: de 01/03/2018 até 15/06/2024
- Período imprescrito: de 26/01/2021 até 15/06/2024

▶ TIPO DE LAUDO
- [X] Insalubridade

▶ PARTICIPANTES
- Reclamante: MARIA DA SILVA

▶ PRÉ-TRIAGEM DE AGENTES
- Ruído (An.1): [Presente — PPRA fls. 40]

▶ ORIGEM DA FICHA: [X] PDF digital nativo
| 09/03/2022 | 1 | LUVA NITRILICA | 5745 |
| 14/07/2023 | 2 | PROTETOR AURICULAR | 12345 |
"""

GEMINI = """*   ▶ PROCESSO E EMPRESA
*   **Nº:** 0011203-24.2025.5.15.0071 [Image 12]
*   **Vara:** 1ª Vara do Trabalho de Mogi Guaçu [4, 9]
*   **Reclamante:** MARIA DA SILVA [Image 3, Image 8]
*   **Reclamada:** OMYA BRASIL LTDA [77, 106, Image 115]
*   **Autuação (data de propositura):** 26/01/2026 [Image 1]
*   **CNAE da atividade principal:** 08.10-0-01 [2]

***

*   ▶ IDENTIFICAÇÃO / VÍNCULO
*   **Período trabalhado:** de 01/03/2018 até 15/06/2024 [Image 5]
*   **Período imprescrito:** de 26/01/2021 até 15/06/2024 [5–7]

***

### ▶ TIPO DE LAUDO
*   [X] Insalubridade [Image 7]

***

*   ▶ PARTICIPANTES
*   Reclamante: MARIA DA SILVA [Image 3]

***

*   ▶ PRÉ-TRIAGEM DE AGENTES
A. Ruído (An.1): [Presente — PPRA fls. 40]

***

*   ▶ ORIGEM DA FICHA: [X] PDF digital nativo
| 09/03/2022 [Image 20] | 1 | LUVA NITRILICA | 5745 |
| 14/07/2023 | 2 | PROTETOR AURICULAR | 12345 [12] |

📊 Sugestão para o próximo passo: posso montar um infográfico com esses dados.

### NOTAS COMPLEMENTARES AO PERITO
| 01/01/2099 | 1 | ITEM FANTASMA DA CAUDA | 9999 |
"""


def _build(texto):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "_bundle.md"
        p.write_text(texto, encoding="utf-8")
        return mf.build_form(p)


def main():
    print("Dialeto Gemini Notebook × formato antigo — mesmo conteúdo, mesmo formulário")
    mf.AVISOS.clear()
    antigo, gemini = _build(ANTIGO), _build(GEMINI)

    print("D1 — campos que o dialeto derrubava")
    for campo, valor in (("nº do processo", "0011203-24.2025.5.15.0071"),
                         ("vara", "Mogi Guaçu"),
                         ("reclamante", "MARIA DA SILVA"),
                         ("reclamada", "OMYA BRASIL LTDA"),
                         ("autuação", "26/01/2026"),
                         ("CNAE", "08.10-0-01"),
                         ("período trabalhado", "01/03/2018"),
                         ("imprescrito", "26/01/2021")):
        check(valor in gemini, f"{campo} preenchido no dialeto Gemini")

    print("D2 — nenhuma citação/ref de imagem vaza para o formulário")
    for lixo in ("[Image", "Image 115", "[77, 106", "[5–7]", "[4, 9]"):
        check(lixo not in gemini, f"{lixo!r} não aparece no formulário")

    print("D3 — sinais de controle sobrevivem")
    check(gemini.count("[ ]") > 20, f"checkbox vazio preservado ({gemini.count('[ ]')} ocorrências)")
    check("[X]" in gemini, "checkbox marcado preservado")

    print("D4 — entregas de EPI (citação dentro da célula não pode sumir com a linha)")
    for data in ("09/03/2022", "14/07/2023"):
        check(data in gemini, f"entrega {data} presente")
    check("5745" in gemini and "12345" in gemini, "os dois C.A. presentes")

    print("D5 — cauda emendada pelo modelo NÃO vira entrega de EPI")
    check("ITEM FANTASMA" not in gemini, "linha da cauda descartada")
    check("01/01/2099" not in gemini, "data da cauda descartada")

    print("D6 — caixinha de sugestão não vaza")
    check("Sugestão para o próximo passo" not in gemini, "caixinha removida")

    print("D7 — pré-triagem com prefixo de letra marca o agente")
    i = gemini.find("A. RUÍDO")
    trecho = gemini[i:i + 200] if i > 0 else ""
    check("[X] Presente" in trecho, "Ruído pré-marcado como Presente (prefixo 'A.' aceito)")

    print("D8 — os dois dialetos produzem o MESMO formulário")
    check(antigo == gemini, "saída idêntica entre formato antigo e dialeto Gemini")
    if antigo != gemini:
        import difflib
        d = list(difflib.unified_diff(antigo.split("\n"), gemini.split("\n"),
                                      "antigo", "gemini", lineterm="", n=0))
        print("    --- diferenças (primeiras 25 linhas) ---")
        for line in d[:25]:
            print("    " + line[:150])

    print("D9 — heading que ESQUECEU o ▶ ainda abre seção")
    # Medido no 0011183-33 (21/08/2026): o Gemini largou o marcador nas três primeiras seções
    # da Parte 1 ("### PROCESSO E EMPRESA") e manteve nas outras 18. Sem glifo não há o que
    # normalizar, e o formulário saiu com 9 de 9 campos vazios — inclusive a data da autuação,
    # sem a qual o guard de EPI perde o imprescrito e subestima o período descoberto.
    sem_marcador = re.sub(r"^▶[ \t]*", "### ", ANTIGO, flags=re.M)
    check("▶" not in sem_marcador, "fixture realmente não tem nenhum ▶")
    check(_build(sem_marcador) == antigo, "heading sem ▶ produz o MESMO formulário")

    print("D10 — a promoção não inventa seção onde não há")
    # A régua é vocabulário FECHADO + nível ≤ 3. Sem as duas metades, um subtítulo interno
    # partiria o bloco de quesitos em dois e uma cauda do modelo viraria seção.
    norm = mf.normalize_bundle(
        "### QUESITOS DO RECLAMANTE\n"
        "#### XV — QUESITOS DE INSALUBRIDADE\n"
        "1. Pergunta.\n"
        "### NOTAS COMPLEMENTARES AO PERITO\n"
        "#### PROCESSO E EMPRESA\n")
    check("▶ QUESITOS DO RECLAMANTE" in norm, "seção conhecida em ### foi promovida")
    check("#### XV — QUESITOS DE INSALUBRIDADE" in norm,
          "subtítulo #### não vira seção (não parte o bloco de quesitos)")
    check("### NOTAS COMPLEMENTARES AO PERITO" in norm,
          "título fora do vocabulário não vira seção")
    check("#### PROCESSO E EMPRESA" in norm,
          "nome conhecido em nível 4 continua sendo subtítulo")
    secs = mf.split_subsections(norm)
    check(len(secs) == 1, f"exatamente 1 seção reconhecida (obtido: {len(secs)})")

    print()
    if FALHAS:
        print(f"✗ {len(FALHAS)} falha(s)")
        return 1
    print("✓ tudo verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
