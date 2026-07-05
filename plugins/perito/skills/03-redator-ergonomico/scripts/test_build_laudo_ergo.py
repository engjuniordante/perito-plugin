#!/usr/bin/env python3
"""Regressão do redator ergonômico (build_laudo_ergo.py).
Trava o fix v1.0.66: ntpath.basename no _resolve_template (path do Drive Windows)."""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_laudo_ergo as be

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def t_resolve_windows():
    print("T1 — _resolve_template com path do Drive Windows cai no BUNDLED")
    win = r'G:\Meu Drive\pericias\template-ergonomico.docx'
    r = be._resolve_template(win)
    check(os.path.isfile(r), 'resolveu para arquivo existente')
    check(os.path.basename(r) == 'template-ergonomico.docx', 'basename correto (ntpath isolou o nome)')

    try:
        be._resolve_template(r'G:\x\template-que-nao-existe.docx')
        check(False, 'basename inexistente deveria abortar (SystemExit)')
    except SystemExit:
        check(True, 'basename inexistente aborta — nao substitui por outro template')


if __name__ == '__main__':
    t_resolve_windows()
    print()
    if FALHAS:
        print('FALHOU (%d): %s' % (len(FALHAS), '; '.join(FALHAS))); sys.exit(1)
    print('OK — todos os testes do build_laudo_ergo passaram'); sys.exit(0)
