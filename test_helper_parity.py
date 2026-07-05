#!/usr/bin/env python3
"""Anti-drift dos helpers docx duplicados entre as 3 skills redatoras.

Contexto (v1.0.66): _ensure, all_paragraphs e replace_scalar são copiados nos 3
build_*.py. Não dá pra extrair pra um módulo compartilhado sem risco (set_cell_text
é legitimamente especializado na skill 03), então a garantia é este teste: se alguém
reintroduzir drift num desses helpers, o CI/rodada quebra ANTES de virar bug em produção.

Compara a AST (ignora comentário/formatação, pega só o comportamento).
set_block/replace_blocks/set_cell_text NÃO entram aqui de propósito — divergem por design.
"""
import ast, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = {
    '02': ROOT / 'plugins/perito/skills/02-redator-insal-peric/scripts/build_laudo.py',
    '03': ROOT / 'plugins/perito/skills/03-redator-ergonomico/scripts/build_laudo_ergo.py',
    '04': ROOT / 'plugins/perito/skills/04-responde-impugnacao/scripts/build_impugnacao.py',
}
# helper -> skills onde ele existe e DEVE ser idêntico
MUST_MATCH = {
    '_ensure':        ['02', '03', '04'],
    'all_paragraphs': ['02', '03', '04'],
    'replace_scalar': ['02', '03', '04'],
}

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def _fn_ast(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return ast.dump(n)
    return None


def main():
    trees = {k: ast.parse(p.read_text(encoding='utf-8')) for k, p in SCRIPTS.items()}
    print("Paridade de helpers docx (AST) entre as skills redatoras")
    for fn, skills in MUST_MATCH.items():
        dumps = {k: _fn_ast(trees[k], fn) for k in skills}
        faltando = [k for k, d in dumps.items() if d is None]
        check(not faltando, '%s presente em %s' % (fn, ', '.join(skills)))
        if faltando:
            continue
        check(len(set(dumps.values())) == 1,
              '%s idêntico entre %s (se falhar: alguém reintroduziu drift)' % (fn, ', '.join(skills)))


if __name__ == '__main__':
    main()
    print()
    if FALHAS:
        print('FALHOU (%d): %s' % (len(FALHAS), '; '.join(FALHAS))); sys.exit(1)
    print('OK — helpers duplicados seguem em paridade'); sys.exit(0)
