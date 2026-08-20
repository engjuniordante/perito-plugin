#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_nr6_ficha_tres_estados.py — a linha NR-6 da ficha tem TRÊS estados (T3).

O achado mais grave da auditoria: qualquer tabela vazia virava "[X]Não · não foram
identificadas entregas". Metade das fichas é escaneada ou manuscrita e devolve zero entregas
por FALHA DE LEITURA, não por ausência de fato — e essa linha alimenta o teste de eliminação
da NR-6, que move o veredito. O formulário passava a afirmar que a ré não comprovou
fornecimento numa ficha que está nos autos.

Os testes usam a linha NO FORMATO QUE O MONTADOR REALMENTE GERA. Isso é metade do ponto: a
regex antiga só casava um formato que o montador não produz mais, então a função estava morta
no formulário real e o teste passava alimentando-a com o formato antigo.

    python test_nr6_ficha_tres_estados.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_epi as ce          # noqa: E402

falhas = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        falhas.append(label)


# a linha exatamente como o montar_formulario.py a escreve (e como está no formulário do Jeferson)
LINHA = "- Ficha de EPI — registro do fornecimento 🔄 — [ ] Sim  [ ] Não"
CONTROLE_SIM = "- Evidenciado controle de entrega (ficha assinada)? [X] Sim  [ ] Não"
CONTROLE_NAO = "- Evidenciado controle de entrega (ficha assinada)? [ ] Sim  [X] Não"
ENTREGA = "- 01/07/2020 · 1un · Bota PVC · CA 35223"
VAZIO = "- ____ · ____ · ____ · CA ____"


def linha_de(body):
    return next(l for l in ce.fill_nr6_ficha(body).splitlines()
                if "registro do fornecimento" in l or "registra o fornecimento" in l)


print("A — a linha do formulário REAL é alcançada pelo guard")
ok(ce.NR6_FICHA_RE.search(LINHA) is not None,
   "a regex casa a linha que o montador gera (antes NÃO casava: a função estava morta)")
ok(ce.NR6_FICHA_RE.search(
    "• Ficha registra o fornecimento (🔄) — [ ]Sim [ ]Não · obs: x") is not None,
   "…e continua casando o formato antigo (compatibilidade)")

print("\nB — estado 1: ficha lida, COM entregas → [X] Sim")
l = linha_de(CONTROLE_SIM + "\n" + LINHA + "\n" + ENTREGA)
ok("[X] Sim" in l and "[ ] Não" in l, "marca Sim: %r" % l[-90:])
ok("registra entregas" in l, "obs documental")

print("\nC — estado 2: ficha NOS AUTOS, mas NADA foi lido → EM BRANCO (o achado do T3)")
l = linha_de(CONTROLE_SIM + "\n" + LINHA + "\n" + VAZIO)
ok("[ ] Sim" in l and "[ ] Não" in l,
   "NÃO marca Não — as duas caixas ficam vazias: %r" % l[-60:])
ok("EM BRANCO PROPOSITAL" in l, "a observação diz que o branco é resposta, não omissão")
ok("NÃO é ausência de fornecimento" in l,
   "…e diz explicitamente o que o branco NÃO significa")
ok("in loco" in l, "…e termina dizendo o que fazer")

print("\nD — estado 3: ficha NÃO juntada aos autos → [X] Não (ausência de prova legítima)")
l = linha_de(CONTROLE_NAO + "\n" + LINHA)
ok("[ ] Sim" in l and "[X] Não" in l, "marca Não: %r" % l[-60:])
ok("não é falha de leitura" in l, "obs separa ausência de prova de falha de leitura")

print("\nE — o sentido inverso: sinal de AUSÊNCIA não pode virar sinal de presença")
# em processo sem ficha o montador escreve NÃO LOCALIZADO nessa mesma linha, que também é
# caractere — casar "controle de entrega" + qualquer coisa leria ausência como presença.
l = linha_de("- Evidenciado controle de entrega (ficha assinada)? [NÃO LOCALIZADO]\n" + LINHA)
ok("[X] Não" in l, "'[NÃO LOCALIZADO]' NÃO conta como ficha nos autos")
l = linha_de("- Evidenciado controle de entrega (ficha assinada)? [ ] Sim  [ ] Não\n" + LINHA)
ok("[X] Não" in l, "caixa não marcada também não conta como presença")

print("\nF — ficha lida, entregas TODAS fora do imprescrito → Sim documental")
achado = ("- ⚠ NENHUMA entrega de EPI no período imprescrito: as 5 entregas da ficha "
          "(01/01/2015–02/02/2016) são todas ANTERIORES ao início do imprescrito (03/07/2020).")
l = linha_de(LINHA + "\n" + achado)
ok("[X] Sim" in l, "a ficha foi lida e registra fornecimento: %r" % l[-70:])
ok("FORA do período imprescrito" in l, "…e a obs diz que a cobertura do período é outra linha")

print("\nG — o formulário do perito não é reformatado")
l = linha_de(CONTROLE_SIM + "\n" + LINHA + "\n" + ENTREGA)
ok(l.startswith("- Ficha de EPI — registro do fornecimento 🔄 — "),
   "prefixo e espaçamento preservados")
antigo = linha_de("• Ficha registra o fornecimento (🔄) — [ ]Sim [ ]Não · obs: velho\n" + ENTREGA)
ok("[X]Sim" in antigo and "[ ]Não" in antigo,
   "no formato antigo, o espaçamento antigo (sem espaço) também é preservado")

print()
if falhas:
    print(f"FALHOU ({len(falhas)}):")
    for f in falhas:
        print("  - " + f)
    sys.exit(1)
print("✓ tudo verde — NR-6 da ficha com três estados (T3)")
