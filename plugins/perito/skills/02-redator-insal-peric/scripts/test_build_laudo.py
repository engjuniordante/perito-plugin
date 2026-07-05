#!/usr/bin/env python3
"""Regressão do redator insal/peric (build_laudo.py).
Trava os fixes v1.0.66: ntpath.basename (path do Drive Windows) e str() no replace_scalar."""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docx
import build_laudo as bl

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def t_resolve_windows():
    print("T1 — _resolve_template com path do Drive Windows cai no BUNDLED")
    win = r'G:\Meu Drive\pericias\template-insalubridade.docx'
    r = bl._resolve_template(win)
    check(os.path.isfile(r), 'resolveu para arquivo existente')
    check(os.path.basename(r) == 'template-insalubridade.docx', 'basename correto (ntpath isolou o nome)')

    posix = '/caminho/inexistente/template-periculosidade.docx'
    r2 = bl._resolve_template(posix)
    check(os.path.basename(r2) == 'template-periculosidade.docx', 'path POSIX inexistente tambem cai no bundled')

    try:
        bl._resolve_template(r'G:\x\template-que-nao-existe.docx')
        check(False, 'basename inexistente deveria abortar (SystemExit)')
    except SystemExit:
        check(True, 'basename inexistente aborta — nao substitui por outro template')


def t_gate_tipo_windows():
    print("T2 — _gate_tipo aceita basename de path Windows (fix da linha 107)")
    doc = docx.Document(os.path.join(bl._BUNDLED_TEMPLATES, 'template-insalubridade.docx'))
    win = r'G:\Meu Drive\pericias\template-insalubridade.docx'
    errs, _tipo, _intent = bl._gate_tipo(doc, win, 'insalubridade')
    tipo_errs = [e for e in errs if 'TEMPLATE PEDIDO' in e]
    check(not tipo_errs, 'sem falso "TIPO x TEMPLATE PEDIDO" (ntpath.basename == template esperado)')


def t_replace_scalar_nao_str():
    print("T3 — replace_scalar coage valor nao-str sem crash (bug 1)")
    d = docx.Document()
    p = d.add_paragraph('{{EPI_ANO_1}}')
    try:
        bl.replace_scalar(d, {'{{EPI_ANO_1}}': 2021})  # int, como o JSON pode emitir
        crashed = False
    except TypeError:
        crashed = True
    check(not crashed, 'nao crasha com int no mapping')
    check('2021' in p.text and '{{EPI_ANO_1}}' not in p.text, 'substituiu pelo str do numero')


if __name__ == '__main__':
    t_resolve_windows(); t_gate_tipo_windows(); t_replace_scalar_nao_str()
    print()
    if FALHAS:
        print('FALHOU (%d): %s' % (len(FALHAS), '; '.join(FALHAS))); sys.exit(1)
    print('OK — todos os testes do build_laudo passaram'); sys.exit(0)
