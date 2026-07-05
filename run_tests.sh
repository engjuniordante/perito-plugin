#!/usr/bin/env bash
# Smoke test do plugin perito — roda TODAS as suítes test_*.py (skills + paridade cross-skill).
# Uso: ./run_tests.sh   (exit 0 = tudo passou; exit 1 = alguma suíte falhou)
# Portável: bash 3.2 (macOS) e bash moderno (Linux/Cowork).
set -u
cd "$(dirname "$0")"

fail=0
run_one() {
  echo "══════════════════════════════════════════════════════════════"
  echo "▶ $1"
  echo "──────────────────────────────────────────────────────────────"
  if ! python3 "$1"; then
    fail=1
  fi
  echo
}

# paridade de helpers primeiro, depois os testes co-localizados de cada skill
run_one ./test_helper_parity.py
while IFS= read -r t; do
  run_one "$t"
done < <(find plugins -name 'test_*.py' | sort)

echo "══════════════════════════════════════════════════════════════"
if [ "$fail" -eq 0 ]; then
  echo "✅ TODAS as suítes passaram"
else
  echo "❌ Alguma suíte FALHOU (veja acima)"
fi
exit "$fail"
