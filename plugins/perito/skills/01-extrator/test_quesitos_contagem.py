#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_quesitos_contagem.py — B6 e B7: o quesito que se perde SEM o bloco ficar vazio.

O B5 só enxerga o bloco ZERADO ("o formulário diz que não há e o bundle tem"). Os dois modos
de perda que ele NÃO vê, medidos no 0011183-33 (22/08/2026):

  B6 — o bloco foi transcrito pela METADE. Devia ter 30, saiu com 22. Mesma forma do bug da
       ficha de EPI: razão agregada não enxerga perda parcial, tem de medir na granularidade
       em que a perda acontece (aqui, a linha numerada).
  B7 — o modelo DESCARTOU um capítulo inteiro por causa do rótulo, e declarou o descarte no
       próprio bundle ("não pertinente ao perito técnico … 30 quesitos"). Formulário e bundle
       conferiam perfeitamente — a perda foi ANTES do bundle, onde nenhum check olhava.

O eixo que custa não é fazer disparar; é NÃO disparar no legítimo. Dois alarmes falsos reais
estão guardados aqui: o bloco de perícia MÉDICA (descarte correto) e o capítulo "XIII —
QUESITOS À PERÍCIA MÉDICA E FUNCIONAL", que o modelo rotulou de "médica/ergonômica" na prosa
embora seja clínico de ponta a ponta. Alarme falso em gate diário ensina o perito a ignorar
o gate — custa mais que o bug que o gate pegaria (régua do bug 6).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_form as vf  # noqa: E402

falhas = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


def contagem(form, bundle):
    f = []
    vf.validate_quesitos_contagem(form, bundle, f)
    return f


def descarte(bundle):
    f = []
    vf.validate_bloco_descartado(bundle, f)
    return f


def bundle_com(n, primeiro=1):
    linhas = '\n'.join('%d. Pergunta número %d?' % (i, i)
                       for i in range(primeiro, primeiro + n))
    return ('### ▶ PROCESSO E EMPRESA\n- Nº: 0010094-14.2026.5.15.0079\n\n'
            '### ▶ QUESITOS DO JUÍZO\nNão houve.\n\n'
            '### ▶ QUESITOS DO RECLAMANTE\n%s\n\n'
            '### ▶ QUESITOS DA RECLAMADA\nNão houve.\n' % linhas)


def form_com(n, primeiro=1):
    linhas = '\n'.join('%d. Pergunta número %d?' % (i, i)
                       for i in range(primeiro, primeiro + n))
    return ('## ▶ QUESITOS\n\n### Quesitos do Juízo\nNão houve.\n\n'
            '### Quesitos do Reclamante\n%s\n\n'
            '### Quesitos da Reclamada\nNão houve.\n' % linhas)


# ── B6.1 — o caso que motivou o check: 30 no bundle, 22 no formulário ────────────────
f = contagem(form_com(22), bundle_com(30))
check(len(f) == 1 and '8 perdido' in f[0],
      'déficit de 8 quesitos não foi acusado: %r' % f)
check('Quesitos do Reclamante' in (f[0] if f else ''),
      'o achado tem de dizer QUAL bloco')

# ── B6.2 — contagem igual não acusa (o eixo que importa) ─────────────────────────────
check(contagem(form_com(30), bundle_com(30)) == [],
      'FALSO POSITIVO: contagem igual gerou achado')

# ── B6.3 — SOBRA não acusa: é o perito completando à mão, que é o trabalho dele ──────
check(contagem(form_com(35), bundle_com(30)) == [],
      'FALSO POSITIVO: formulário com MAIS quesitos que o bundle foi acusado')

# ── B6.4 — bundle sem numeração não é mensurável (não inventar régua) ────────────────
sem_num = bundle_com(3).replace('1. Pergunta número 1?', 'a) Quais foram as funções?') \
                       .replace('2. Pergunta número 2?', 'b) Quais foram os setores?') \
                       .replace('3. Pergunta número 3?', 'c) Havia EPI?')
check(contagem(form_com(0), sem_num) == [],
      'FALSO POSITIVO: bloco em prosa/alfabético foi medido')

# ── B6.5 — bloco zerado é achado do B5, não do B6 (um alarme por defeito) ────────────
check(contagem(form_com(0), bundle_com(30)) == [],
      'B6 duplicou o alarme do B5 no bloco vazio')

# ── B6.6 — a numeração REINICIA a cada capítulo: contar LINHAS, não números únicos ───
# XIII (1..3) + XIV (1..3) = 6 linhas. Contar distintos daria 3 e esconderia a perda de
# um capítulo inteiro, que é exatamente o defeito que este check existe para pegar.
dois_caps = bundle_com(3).replace(
    '3. Pergunta número 3?',
    '3. Pergunta número 3?\n\n#### XIV — OUTRO CAPÍTULO\n'
    '1. Outra pergunta 1?\n2. Outra pergunta 2?\n3. Outra pergunta 3?')
f = contagem(form_com(3), dois_caps)
check(len(f) == 1 and '3 perdido' in f[0],
      'capítulo inteiro perdido com numeração reiniciada não foi acusado: %r' % f)

# ── B7.1 — o caso real: capítulo XIV descartado, com a quantidade declarada ──────────
BUNDLE_XIV = ('### ▶ QUESITOS DO RECLAMANTE\n'
              '- Bloco de perícia ergonômica/acidentária — não pertinente ao perito técnico. '
              '*(Refere-se ao capítulo "XIV – QUESITOS TÉCNICOS DE SEGURANÇA, ERGONOMIA E '
              'RECONSTITUIÇÃO DO ACIDENTE", fls. 11/13, composto por 30 quesitos voltados à '
              'dinâmica do acidente de trabalho, segurança de máquinas sob a NR-12 e análise '
              'postural sob a NR-17).*\n')
f = descarte(BUNDLE_XIV)
check(len(f) == 1, 'descarte do capítulo XIV não foi acusado: %r' % f)
check('30 quesitos declarados' in (f[0] if f else ''),
      'o achado tem de trazer a quantidade que o próprio bundle declarou')
check('XIV' in (f[0] if f else ''), 'o achado tem de nomear o capítulo')

# ── B7.2 — descarte de bloco MÉDICO é legítimo e não pode acusar ─────────────────────
check(descarte('* Bloco de perícia médica — não pertinente ao perito técnico.\n') == [],
      'FALSO POSITIVO: descarte de bloco médico simples foi acusado')
check(descarte('- Bloco de perícia médica — não pertinente ao perito técnico. *(Refere-se ao '
               'capítulo "QUESITOS MÉDICOS", fls. 356/357, composto por 15 quesitos '
               'elaborados pelo assistente médico).*\n') == [],
      'FALSO POSITIVO: capítulo "QUESITOS MÉDICOS" foi acusado')

# ── B7.3 — o alarme falso CARO, medido no bundle real: prosa diz "médica/ergonômica",
#           mas o capítulo citado é clínico de ponta a ponta. Vale o TÍTULO, não a prosa.
check(descarte('- Bloco de perícia médica/ergonômica — não pertinente ao perito técnico. '
               '*(Refere-se ao capítulo "XIII – QUESITOS À PERÍCIA MÉDICA E FUNCIONAL", '
               'fls. 8/10, composto por 30 quesitos direcionados exclusivamente à avaliação '
               'clínica/sequelar).*\n') == [],
      'FALSO POSITIVO: capítulo clinicamente médico acusado por causa da prosa do rótulo')

# ── B7.4 — sem título citado, cai na linha inteira (senão o descarte escapa) ─────────
f = descarte('- Bloco de perícia ergonômica — não pertinente ao perito técnico.\n')
check(len(f) == 1, 'descarte sem título citado escapou: %r' % f)

# ── B7.5 — bundle sem nenhuma linha de descarte não gera nada ────────────────────────
check(descarte(bundle_com(30)) == [], 'FALSO POSITIVO: bundle limpo gerou achado de descarte')

if falhas:
    print('FALHOU:')
    for x in falhas:
        print('  ✗', x)
    sys.exit(1)
print('✓ tudo verde — B6 (quesito pela metade) e B7 (bloco descartado por rótulo), sem alarme falso')
