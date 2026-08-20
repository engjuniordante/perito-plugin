#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_multileitura_ca.py — T14: mais de uma leitura de C.A. no mesmo campo.

Dois eixos, e o segundo é o que custa:
  1) a leitura múltipla é RELATADA, com o que a base responde a cada candidato;
  2) ela NÃO é inventada em campo de uma leitura só — quantidade entre parênteses,
     validade colada e palavra depois do número são os três jeitos de virar falso positivo.

Invariante de método: o guard NÃO escolhe. extract_ca continua elegendo a 1ª leitura e a
classificação não muda — o T14 só acrescenta aviso.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_epi as c  # noqa: E402

AQUI = Path(__file__).resolve().parent
CAEPI = AQUI / 'assets' / '04-EPIs' / 'caepi.sqlite'
CADICT = AQUI / 'assets' / '04-EPIs' / 'CA-dicionario.json'

falhas = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


def linha(campo_ca, desc='LUVA NITRILICA QUIMICA', data='10/03/2022'):
    return '- %s · 1un · %s · %s' % (data, desc, campo_ca)


# ── 1. o varredor devolve TODAS as leituras, nas formas que o modelo escreve ──────────
for campo, esperado in [
    ('CA 5244 ou 5774',          ['5244', '5774']),
    ('CA 5244 5774',             ['5244', '5774']),
    ('CA 5244, 5774',            ['5244', '5774']),
    ('CA 5244 (ou 5774)',        ['5244', '5774']),
    ('CA 5244/5774',             ['5244', '5774']),
    ('CA 11512/5745',            ['11512', '5745']),
    ('CA 5244 e 5774',           ['5244', '5774']),
    ('CA 5244 ou 5774 ou 39342', ['5244', '5774', '39342']),
]:
    got = c.extract_ca_candidates(linha(campo))
    check(got == esperado, 'candidatos de %r: %r != %r' % (campo, got, esperado))

# ── 2. campo de UMA leitura não vira leitura múltipla (os falsos positivos) ───────────
for campo, esperado in [
    ('CA 35708',            ['35708']),
    ('CA 26206 (1x)',       ['26206']),    # quantidade entre parênteses
    ('CA 35708 (12x)',      ['35708']),    # ...com dois dígitos, que passaria no filtro
    ('CA 26149 venc 2025',  ['26149']),    # palavra encerra a varredura
    ('CA 1.720',            ['1720']),     # 3 casas decimais = UMA unidade (regra do T7.1)
    ('CA 1234/2025',        []),           # validade colada: UM C.A. mal transcrito
    ('CA Não se Aplica',    []),
    ('CA não informado',    []),
]:
    got = c.extract_ca_candidates(linha(campo))
    check(got == esperado, 'FALSO POSITIVO em %r: %r != %r' % (campo, got, esperado))

# A descrição nunca contribui candidato — o campo do C.A. é a última célula, só ela.
got = c.extract_ca_candidates(
    '- 24/05/2024 · 1un · LUVA PROT. C/RESIST. MECÂNICA E AO CORTE MOD.48705 T.9 · CA 35708')
check(got == ['35708'], 'descrição vazou candidato: %r' % got)

# Linha sem as 3 células (não é linha de dados da ficha) não produz candidato.
check(c.extract_ca_candidates('C.A. do protetor auditivo: 11512 / 5745') == [],
      'linha de prosa produziu candidatos')

# ── 3. o aviso, contra a base REAL do MTE (evidência da auditoria, 12/08) ─────────────
if not CAEPI.exists():
    print('⚠ caepi.sqlite ausente — eixos 3 e 4 pulados (varredor já validado acima)')
else:
    caepi = c.Caepi(str(CAEPI))
    cadict = c.load_dict(str(CADICT))

    # Cada um dos três casos reais foi pego por um EIXO DIFERENTE da base: existência,
    # família/parte do corpo e validade na data da entrega.
    casos = [
        ('CA 5244 ou 5774',   'LUVA NITRILICA QUIMICA', 'NÃO CONSTA'),
        ('CA 42712 ou 42717', 'OCULOS DE PROTECAO',     'VESTIMENTA'),
        ('CA 39392 ou 39342', 'MANGOTE',                'parte do corpo'),
    ]
    for campo, desc, marca in casos:
        _, flags, _ = c.process([linha(campo, desc)], cadict, caepi)
        msgs = [m for _, m in flags]
        multi = [m for m in msgs if 'MAIS DE UMA LEITURA' in m]
        check(len(multi) == 1, '%s: esperava 1 aviso de leitura múltipla, veio %d' % (desc, len(multi)))
        if multi:
            check(marca in multi[0], '%s: a base não respondeu %r no aviso' % (desc, marca))
            # os DOIS candidatos aparecem, e o eleito vem marcado
            for cand in campo.replace('CA ', '').split(' ou '):
                check(cand in multi[0], '%s: candidato %s ausente do aviso' % (desc, cand))
            check('(usado)' in multi[0], '%s: o aviso não marca qual foi usado' % desc)
            check('CONFIRA' in multi[0], '%s: o aviso não termina dizendo o que fazer' % desc)
        # T9 não repete a divergência que o aviso já traz inline
        check(len([m for m in msgs if 'não protege a mesma parte do corpo que a descrição da ficha' in m]) == 0,
              '%s: T9 duplicou o aviso na mesma linha' % desc)

    # ── 4. o guard NÃO escolhe: a classificação segue a 1ª leitura, como antes ────────
    cl, _, _ = c.process([linha('CA 39392 ou 39342', 'MANGOTE')], cadict, caepi)
    usados = [ca for ca, _, _, _ in cl]
    check(usados == [] or usados == ['39392'],
          'o T14 mudou a eleição do C.A. (deveria seguir a 1ª): %r' % usados)

    # ── 5. campo de leitura única não ganha aviso novo ────────────────────────────────
    _, flags_u, _ = c.process([linha('CA 39342', 'MANGOTE')], cadict, caepi)
    check(not [m for _, m in flags_u if 'MAIS DE UMA LEITURA' in m],
          'leitura única disparou aviso de leitura múltipla')

    # ── 6. validade colada mantém o aviso de ILEGÍVEL (não vira leitura múltipla) ─────
    _, flags_v, _ = c.process([linha('CA 1234/2025', 'PROTETOR AURICULAR')], cadict, caepi)
    msgs_v = [m for _, m in flags_v]
    check(any('ILEGÍVEL' in m for m in msgs_v), 'validade colada perdeu o aviso de ilegível')
    check(not any('MAIS DE UMA LEITURA' in m for m in msgs_v),
          'validade colada virou leitura múltipla')

    # ── 7. duas leituras, nenhuma usável: um aviso só, e ele diz que saiu da conta ────
    _, flags_s, _ = c.process([linha('CA 5244/5774')], cadict, caepi)
    msgs_s = [m for _, m in flags_s]
    multi_s = [m for m in msgs_s if 'MAIS DE UMA LEITURA' in m]
    check(len(multi_s) == 1, 'esperava 1 aviso p/ 5244/5774, veio %d' % len(multi_s))
    check(multi_s and 'FORA da classificação' in multi_s[0],
          'o aviso não diz que a entrega ficou fora da conta')
    check(not any('ILEGÍVEL' in m for m in msgs_s),
          'aviso de ilegível duplicou o de leitura múltipla')

if falhas:
    print('FALHOU:')
    for f in falhas:
        print('  ✗', f)
    sys.exit(1)
print('✓ tudo verde — leitura múltipla de C.A. relatada sem escolher pelo perito (T14)')
