#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regressão da fatia mecânica da impugnação (responde_impugnacao.py).
Cobre o parse da minuta do NLM (1 e 2 partes), o corte do fecho fixo, a limpeza de
citações, os fallbacks (nº pela pasta, partes pelos títulos) e a extração do prompt.
Não chama o `nlm` — só a lógica pura + o build determinístico."""
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

TEMPLATE = R.TEMPLATE_BUNDLED
FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def _docx_text(p):
    import re
    import html
    xml = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8")
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<w:p[ >]", "\n", xml)))


MINUTA_1 = """- CIDADE_VARA: Araraquara
- NUMERO_PROCESSO: 0010123-45.2026.5.15.0079
- NOME_RECLAMANTE: FULANO DE TAL
- NOME_RECLAMADA: EMPRESA X LTDA
- IMPUGNANTES: Reclamada (Id. abc123)

---
ESCLARECIMENTOS SOLICITADOS PELA RECLAMADA

A reclamada alega que o ruído não foi medido corretamente. [1] Conforme o laudo, seguiu a NHO-01.

1- O ruído foi avaliado com dosímetro calibrado?
Resposta: Conforme descrito no laudo pericial, sim (item 6.1).

Pelo exposto, espero ter eliminado quaisquer dúvidas remanescentes, concluindo assim, que o laudo está baseado em dados colhidos "in loco", demonstrando a veracidade dos fatos que se encontram documentados.
Em razão de todo o exposto, ratifico a conclusão do laudo pericial."""

MINUTA_2 = """CIDADE_VARA: Sumaré
NUMERO_PROCESSO: 0011276-93.2025.5.15.0071
NOME_RECLAMANTE: BELTRANO
NOME_RECLAMADA: INDUSTRIA Y SA
IMPUGNANTES: Reclamante (Id. rec111); Reclamada (Id. rda222)

ESCLARECIMENTOS SOLICITADOS PELA RECLAMANTE
1- Calor descartado indevidamente?
Resposta: Conforme avaliado in loco, IBUTG abaixo do limite.

ESCLARECIMENTOS SOLICITADOS PELA RECLAMADA
1- Periculosidade por inflamáveis?
Resposta: Não, conforme o laudo, volume inferior ao da NR-16.

Em razão de todo o exposto, ratifico a conclusão do laudo pericial."""


def t_parse_uma_parte():
    print("T1 — parse 1 parte: campos, INTRO singular, fecho e citação cortados")
    scal, esc, flags = R.parse_minuta(MINUTA_1, "0010123-45.2026.5.15.0079")
    check(scal["CIDADE_VARA"] == "Araraquara", "CIDADE_VARA")
    check(scal["INTRO_IMPUGNANTE"] ==
          "para a impugnação protocolada pelo Ilustre Patrono do(a) Reclamada conforme Id. abc123",
          "INTRO singular composto")
    check(all("[1]" not in e for e in esc), "citação [1] removida do corpo")
    check(not any(R._sem_acento(e).startswith(("pelo exposto", "em razao de todo")) for e in esc),
          "fecho fixo cortado (não duplica)")
    check(esc[0].upper().startswith("ESCLARECIMENTOS SOLICITADOS"), "1º item é o título")
    check(flags == [], "sem flags (tudo localizado)")


def t_parse_duas_partes():
    print("T2 — parse 2 partes: INTRO plural com os 2 Ids, 2 títulos no corpo")
    scal, esc, flags = R.parse_minuta(MINUTA_2, "qualquer")
    check(scal["INTRO_IMPUGNANTE"].startswith("para as impugnações protocoladas pelos Ilustres Patronos"),
          "INTRO no plural")
    check("do(a) Reclamante conforme Id. rec111" in scal["INTRO_IMPUGNANTE"] and
          "do(a) Reclamada conforme Id. rda222" in scal["INTRO_IMPUGNANTE"], "os 2 Ids na INTRO")
    titulos = [e for e in esc if e.upper().startswith("ESCLARECIMENTOS SOLICITADOS")]
    check(len(titulos) == 2, "2 blocos de título no corpo")


def t_fallbacks():
    print("T3 — fallbacks: nº pela pasta e partes pelos títulos quando IMPUGNANTES falta")
    txt = ("ESCLARECIMENTOS SOLICITADOS PELA RECLAMANTE\n1- Q?\nResposta: R.")
    scal, esc, flags = R.parse_minuta(txt, "Proc 0022222-33.2026.5.15.0002")
    check(scal["NUMERO_PROCESSO"] == "0022222-33.2026.5.15.0002", "nº veio do nome da pasta")
    check("do(a) Reclamante conforme Id. ____" in scal["INTRO_IMPUGNANTE"],
          "parte derivada do título (sem header IMPUGNANTES)")
    check(any("não localizado" in f or "não localizada" in f for f in flags), "flag de campo ausente")


def t_prompt_extractor():
    print("T4 — ler_prompt_impugnacao pega só o bloco de Impugnação")
    md = ("# PARTE 1\n```\nprompt da parte 1\n```\n"
          "# Prompt de Impugnação\n```\nINSTRUCAO IMPUGNACAO AQUI\n```\n")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(md); path = fh.name
    got = R.ler_prompt_impugnacao(path)
    check(got == "INSTRUCAO IMPUGNACAO AQUI", "extraiu o bloco de impugnação, não o da Parte 1")


def t_build_end_to_end():
    print("T5 — parse → build: docx sem marcador residual, fecho único, negrito")
    scal, esc, _ = R.parse_minuta(MINUTA_2, "x")
    data = {"perito_nome": "Irineu de Freitas Branco Junior", "scalars": scal, "esclarecimentos": esc}
    with tempfile.TemporaryDirectory() as d:
        jp = Path(d) / "data.json"; jp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        op = Path(d) / "out.docx"
        ok = B.build(str(TEMPLATE), str(jp), str(op))
        check(ok is True, "build retornou True")
        t = _docx_text(op)
        check("{{" not in t, "sem marcador residual")
        check(t.count("ratifico a conclusão do laudo pericial") == 1, "fecho fixo aparece 1x (não duplicou)")
        check("para as impugnações protocoladas pelos Ilustres Patronos" in t, "INTRO plural no docx")


if __name__ == "__main__":
    t_parse_uma_parte(); t_parse_duas_partes(); t_fallbacks()
    t_prompt_extractor(); t_build_end_to_end()
    print()
    if FALHAS:
        print("FALHOU (%d): %s" % (len(FALHAS), "; ".join(FALHAS))); sys.exit(1)
    print("OK — todos os testes do responde_impugnacao passaram"); sys.exit(0)
