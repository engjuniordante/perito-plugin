#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressão do DIALETO do Gemini Notebook na minuta de impugnação (skill 04b).

Irmão do test_dialeto_gemini.py do extrator. A régua é a mesma que fechou o bug 5 lá:
**a minuta decorada tem de produzir o MESMO resultado da minuta limpa** — não basta
"não quebrar". O que está em jogo aqui é maior que no extrator: a saída não é um
formulário que o perito relê campo a campo, é uma PETIÇÃO que ele assina e protocola.

Medido antes do conserto (mesma minuta, só mudando a formatação): 3 dos 4 escalares
viravam "____", as 6 linhas do header vazavam como parágrafos da peça, o título saía
"### ESCLARECIMENTOS…" sem negrito e a caixinha do Studio ("Deseja que eu gere um
infográfico…") entrava no documento — com o .docx gerado assim mesmo.
"""
import json
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "04-responde-impugnacao" / "scripts"))
import responde_impugnacao as R
import build_impugnacao as B

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def _docx_text(p):
    import re
    import html
    xml = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8")
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<w:p[ >]", chr(10), xml)))


PASTA = "0011183-33.2025.5.15.0071"

LIMPA = """- CIDADE_VARA: 2ª Vara do Trabalho de Limeira
- NUMERO_PROCESSO: 0011183-33.2025.5.15.0071
- NOME_RECLAMANTE: DIRCEU DA SILVA
- NOME_RECLAMADA: ASW SERVIÇOS LTDA
- IMPUGNANTES: Reclamada (Id. 8f3c21a)

ESCLARECIMENTOS SOLICITADOS PELA RECLAMADA

A Reclamada alega que o ruído não foi medido no setor de prensas.

1- Queira o Sr. Perito informar se mediu o ruído no setor de prensas.
Resposta: Conforme descrito no laudo pericial, a medição foi realizada in loco (item 6.2).
"""

# O mesmo conteúdo como o Gemini Notebook o entrega: título markdown, bullets "*   ",
# negrito nos rótulos, refs de imagem e a caixinha do Studio no fim.
GEMINI = """## Minuta de Esclarecimentos Periciais

*   **CIDADE_VARA:** 2ª Vara do Trabalho de Limeira [12]
*   **NUMERO_PROCESSO:** 0011183-33.2025.5.15.0071
*   **NOME_RECLAMANTE:** DIRCEU DA SILVA
*   **NOME_RECLAMADA:** ASW SERVIÇOS LTDA [Image 4]
*   **IMPUGNANTES:** Reclamada (Id. 8f3c21a)

### ESCLARECIMENTOS SOLICITADOS PELA RECLAMADA

A Reclamada alega que o ruído não foi medido no setor de prensas. [7, Image 11]

1- Queira o Sr. Perito informar se mediu o ruído no setor de prensas.
**Resposta:** Conforme descrito no laudo pericial, a medição foi realizada in loco (item 6.2).

📊 Sugestão de próximo passo: Deseja que eu gere um infográfico comparando os níveis
de ruído medidos com os limites de tolerância da NR-15?
"""


def t_paridade_limpa_x_gemini():
    print("D1 — a minuta decorada produz o MESMO resultado da limpa")
    a_sc, a_esc, a_fl = R.parse_minuta(LIMPA, PASTA)
    b_sc, b_esc, b_fl = R.parse_minuta(GEMINI, PASTA)
    check(a_sc == b_sc, "escalares idênticos (era 3 de 4 em '____' no dialeto Gemini)")
    check(a_esc == b_esc, "corpo idêntico (era 11 parágrafos contra 3)")
    check(not a_fl and not b_fl, "nenhuma flag nos dois")
    check(b_sc["CIDADE_VARA"] == "2ª Vara do Trabalho de Limeira",
          "CIDADE_VARA lida por trás do bullet + negrito")
    check("Id. 8f3c21a" in b_sc["INTRO_IMPUGNANTE"],
          "INTRO composta (era 'Ilustre Patrono ____ conforme Id. ____')")


def t_caixinha_fora_da_peca():
    print("D2 — a caixinha do Studio não entra na petição, com qualquer ícone")
    for icone in ("💡", "📊", "🎧", "🧩"):
        txt = LIMPA + chr(10) + icone + " Sugestão de próximo passo: quer um resumo?" + chr(10)
        _sc, esc, _fl = R.parse_minuta(txt, PASTA)
        check(not any("Sugestão de próximo passo" in e for e in esc),
              "caixinha %s descartada" % icone)
    # sem linha em branco depois (caixinha na última linha do arquivo) e com continuação
    txt = LIMPA + "🧩 Sugestão para o próximo passo: consolidar" + chr(10) + "os dados da ficha?"
    _sc, esc, _fl = R.parse_minuta(txt, PASTA)
    check(not any("consolidar" in e or "dados da ficha" in e for e in esc),
          "caixinha no fim do arquivo sai com a linha de continuação")


def t_contencao():
    print("D3 — contenção: fora do vocabulário fechado nada vira rótulo nem some")
    txt = LIMPA + chr(10) + "### 3 - Da conclusão do laudo" + chr(10) + "Mantém-se o item 7."
    _sc, esc, _fl = R.parse_minuta(txt, PASTA)
    check("3 - Da conclusão do laudo" in esc,
          "subtítulo do corpo permanece como texto (sem os '###' vazando pro .docx)")
    check("Mantém-se o item 7." in esc, "o parágrafo seguinte não foi engolido")
    check(not any(e.startswith("#") for e in esc), "nenhum '#' literal no corpo")


def t_gate_minuta_nao_reconhecida():
    print("D4 — o gate: minuta que o parser não lê é RECUSADA, não gerada com '____'")
    lixo = """Aqui está a análise que você pediu.

O laudo é consistente com a NR-15 e a impugnação não traz fato novo.
"""
    _sc, _esc, fl = R.parse_minuta(lixo, PASTA)
    check(any(f.startswith(R._FLAG_NAO_RECONHECIDA) for f in fl),
          "flag MINUTA NÃO RECONHECIDA levantada")
    # falso positivo é o defeito caro num gate diário: as duas minutas boas passam limpas
    for nome, txt in (("limpa", LIMPA), ("Gemini", GEMINI)):
        _s, _e, f = R.parse_minuta(txt, PASTA)
        check(not any(x.startswith(R._FLAG_NAO_RECONHECIDA) for x in f),
              "gate NÃO dispara na minuta %s" % nome)
    # só o header faltando (mas com título) segue gerando — é caso de ____ , não de recusa
    so_corpo = LIMPA.split("ESCLARECIMENTOS SOLICITADOS")[1]
    _s, _e, f = R.parse_minuta("ESCLARECIMENTOS SOLICITADOS" + so_corpo, PASTA)
    check(not any(x.startswith(R._FLAG_NAO_RECONHECIDA) for x in f),
          "gate NÃO dispara quando só o header falta (o título foi lido)")


def t_docx_end_to_end():
    print("D5 — o .docx: título em negrito, sem markdown e sem a caixinha")
    sc, esc, _fl = R.parse_minuta(GEMINI, PASTA)
    data = {"perito_nome": "Irineu de Freitas Branco Junior", "scalars": sc,
            "esclarecimentos": esc}
    with tempfile.TemporaryDirectory() as d:
        jp = Path(d) / "data.json"
        jp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        op = Path(d) / "out.docx"
        check(B.build(str(TEMPLATE_04), str(jp), str(op)) is True, "build gerou o documento")
        t = _docx_text(op)
        check("{{" not in t, "sem marcador residual")
        check("###" not in t and "*   " not in t, "nenhuma decoração markdown no documento")
        check("infográfico" not in t, "a caixinha do Studio não está no documento")
        check("CIDADE_VARA" not in t, "as linhas do header não vazaram para o corpo")
        check("2ª Vara do Trabalho de Limeira" in t, "a cidade/vara entrou no lugar certo")
        xml = zipfile.ZipFile(op).read("word/document.xml").decode("utf-8")
        i = xml.find("ESCLARECIMENTOS SOLICITADOS PELA RECLAMADA")
        check(i > 0 and "<w:b/>" in xml[max(0, i - 400):i], "título do bloco em negrito")


TEMPLATE_04 = R.TEMPLATE_BUNDLED

if __name__ == "__main__":
    t_paridade_limpa_x_gemini()
    t_caixinha_fora_da_peca()
    t_contencao()
    t_gate_minuta_nao_reconhecida()
    t_docx_end_to_end()
    print()
    if FALHAS:
        print("FALHOU (%d): %s" % (len(FALHAS), "; ".join(FALHAS)))
        sys.exit(1)
    print("OK — o dialeto do Gemini não passa para a petição")
    sys.exit(0)
