#!/usr/bin/env python3
"""Smoke test do plugin perito — equivalente multiplataforma do run_tests.sh (Windows
não roda .sh). Roda TODAS as suítes test_*.py (paridade cross-skill + skills) e confere
que plugin.json e marketplace.json declaram a MESMA versão (o bump é em 2 lugares).

Uso: python3 run_tests.py   (exit 0 = tudo passou; exit 1 = algo falhou)
"""
import json
import subprocess
import sys
from pathlib import Path

# Piso 3.9 (anotações builtin) + stdout/err UTF-8: no Windows a saída capturada cai em
# cp1252 (Python <3.15) e um emoji do relatório mataria o script com UnicodeEncodeError.
if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')
if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)  # cabeçalhos ▶ na ordem dos filhos

ROOT = Path(__file__).resolve().parent


def versoes_em_paridade():
    plugin = json.loads((ROOT / 'plugins/perito/.claude-plugin/plugin.json')
                        .read_text(encoding='utf-8'))
    market = json.loads((ROOT / '.claude-plugin/marketplace.json')
                        .read_text(encoding='utf-8'))
    v_plugin = plugin.get('version')
    v_market = market['plugins'][0].get('version')
    ok = bool(v_plugin) and v_plugin == v_market
    print(('✓' if ok else '✗ FALHOU:') +
          ' versão em paridade — plugin.json (%s) × marketplace.json (%s)'
          % (v_plugin, v_market))
    return ok


def main():
    fail = not versoes_em_paridade()
    print()
    suites = [ROOT / 'test_helper_parity.py'] + sorted((ROOT / 'plugins').rglob('test_*.py'))
    for t in suites:
        print('═' * 62)
        print('▶ %s' % t.relative_to(ROOT))
        print('─' * 62)
        if subprocess.run([sys.executable, str(t)], cwd=ROOT).returncode != 0:
            fail = True
        print()
    print('═' * 62)
    print('❌ Alguma suíte FALHOU (veja acima)' if fail else '✅ TODAS as suítes passaram')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
