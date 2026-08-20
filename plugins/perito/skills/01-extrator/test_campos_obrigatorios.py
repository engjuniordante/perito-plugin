#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_campos_obrigatorios.py — T16.2: o gate acusa campo obrigatório vazio.

Antes disto, `VALIDAÇÃO OK` só olhava sanidade do imprescrito, identidade do processo e
carimbo do guard — um formulário praticamente em branco passava, desde que o nº do processo
sobrevivesse.

O eixo que custa NÃO é fazer o aviso disparar; é ele NÃO disparar no formulário legítimo.
Boa parte do formulário do Irineu vem em branco DE PROPÓSITO (medição, citações, papel dos
participantes, "Neutraliza?") — cada um desses é um alarme falso em potencial, e alarme falso
em gate diário é o jeito mais rápido de ensinar o perito a ignorar o gate.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_form as vf  # noqa: E402

falhas = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


def achou(findings, agulha):
    return any(agulha.lower() in f.lower() for f in findings)


# ── um formulário LEGÍTIMO, no formato que o montar_formulario escreve ────────────────
# Repare no que vem vazio de propósito: citações, papel do 2º participante e medição.
FORM_OK = """# FORMULÁRIO DE PERÍCIA — Eng. Irineu de Freitas Branco Junior

## ▶ TIPO DE LAUDO ★
- [ ] Insalubridade → `template-insalubridade.docx`
- [ ] Periculosidade → `template-periculosidade.docx`
- [X] Insalubridade + Periculosidade → `template-insal-peric.docx`
- [ ] Ergonomia → `template-ergonomico.docx`

## ▶ LAUDO BASE (opcional)
Laudo Base:

## ▶ PROCESSO
- Nº: 0010094-14.2026.5.15.0079
- Vara: 2ª Vara do Trabalho de Araraquara
- Data da diligência: 17/05/2026
- Horário: 13h00min
- Local: Usina Santa Cruz - Américo Brasiliense
- **Data de entrega do laudo:**  *(prazo da ata — controle do perito; NÃO vai ao laudo)*
- **Data da autuação / ação:** 26/01/2026

## ▶ PARTICIPANTES
Nome: Jeferson Souza de Oliveira
Papel: Reclamante
Nome:
Papel:

## ▶ RECLAMANTE
- Reclamante: Jeferson Souza de Oliveira
- Reclamada: São Martinho S.A.

## ▶ CITAÇÕES / DEPOIMENTOS
- Reclamante disse:
- Reclamada disse:

## ▶ AGENTES — INSALUBRIDADE (NR-15)
### A. RUÍDO (Anexos 1 e 2)
- Medição (dB(A)):
- Neutraliza?

## ▶ QUESITOS

### Quesitos do Juízo
Não houve.

### Quesitos do Reclamante
a) Quais foram as funções exercidas pelo reclamante?
b) Quais foram os setores onde trabalhou?

### Quesitos da Reclamada
1) Escopo e método — delimitar postos e período.
"""

BUNDLE_OK = """### ▶ PROCESSO E EMPRESA
- Nº: 0010094-14.2026.5.15.0079

### ▶ QUESITOS DO JUÍZO
Não houve.

### ▶ QUESITOS DO RECLAMANTE
a) Quais foram as funções exercidas pelo reclamante?
b) Quais foram os setores onde trabalhou?

### ▶ QUESITOS DA RECLAMADA
1) Escopo e método — delimitar postos e período.
"""


def campos(form, bundle=BUNDLE_OK):
    f = []
    vf.validate_campos_obrigatorios(form, f)
    return f


def quesitos(form, bundle=BUNDLE_OK):
    f = []
    vf.validate_quesitos(form, bundle, f)
    return f


# ── 1. o formulário legítimo NÃO gera achado (o eixo que importa) ─────────────────────
f = campos(FORM_OK)
check(f == [], 'FALSO POSITIVO no formulário legítimo: %r' % f)
check(quesitos(FORM_OK) == [], 'FALSO POSITIVO nos quesitos do formulário legítimo')

# Campo em branco por desenho nunca é acusado, mesmo nomeado explicitamente.
for proibido in ('Reclamante disse', 'Reclamada disse', 'Medição', 'Neutraliza',
                 'Papel', 'Laudo Base', 'Data de entrega'):
    check(not achou(campos(FORM_OK), proibido),
          'campo de preenchimento in loco virou achado: %s' % proibido)

# ── 2. cada campo crítico vazio dispara, e diz por que importa ────────────────────────
for rotulo, marca in [('- Nº: 0010094-14.2026.5.15.0079', 'Nº'),
                      ('- Reclamante: Jeferson Souza de Oliveira', 'Reclamante'),
                      ('- Reclamada: São Martinho S.A.', 'Reclamada'),
                      ('- **Data da autuação / ação:** 26/01/2026', 'Data da autuação')]:
    vazio = FORM_OK.replace(rotulo, rotulo.split(':')[0] + ':')
    check(achou(campos(vazio), marca), '%s vazio não foi acusado' % marca)

# "[NÃO LOCALIZADO]" é visível, mas em campo crítico o formulário está quebrado igual.
nl = FORM_OK.replace('- Reclamada: São Martinho S.A.', '- Reclamada: [NÃO LOCALIZADO]')
check(achou(campos(nl), 'Reclamada'), '[NÃO LOCALIZADO] em campo crítico passou batido')

# Rótulo que sumiu do formulário é diagnóstico DIFERENTE de campo vazio.
sem_rotulo = FORM_OK.replace('- Reclamada: São Martinho S.A.', '')
check(achou(campos(sem_rotulo), 'rótulo ausente'),
      'rótulo ausente não foi distinguido de campo vazio')

# ── 3. tipo de laudo sem opção marcada ────────────────────────────────────────────────
sem_tipo = FORM_OK.replace('- [X] Insalubridade + Periculosidade',
                           '- [ ] Insalubridade + Periculosidade')
check(achou(campos(sem_tipo), 'TIPO DE LAUDO'), 'tipo de laudo desmarcado não foi acusado')
# ...e a variante unicode do checkbox (T15) continua valendo como marcada.
uni = FORM_OK.replace('- [X] Insalubridade + Periculosidade',
                      '- ☑ Insalubridade + Periculosidade')
check(not achou(campos(uni), 'TIPO DE LAUDO'), 'checkbox unicode ☑ não foi reconhecido')

# ── 4. formulário degradado: o diagnóstico, não a lista de campos ─────────────────────
degradado = FORM_OK
for linha in ('- Nº: 0010094-14.2026.5.15.0079', '- Vara: 2ª Vara do Trabalho de Araraquara',
              '- Data da diligência: 17/05/2026', '- Horário: 13h00min',
              '- Local: Usina Santa Cruz - Américo Brasiliense',
              '- **Data da autuação / ação:** 26/01/2026',
              '- Reclamante: Jeferson Souza de Oliveira', '- Reclamada: São Martinho S.A.'):
    degradado = degradado.replace(linha, linha.split(':')[0] + ':')
fd = campos(degradado)
check(achou(fd, 'BUNDLE que não foi reconhecido'),
      'formulário degradado não recebeu o diagnóstico do bundle')
check(achou(fd, 'início da linha'), 'o diagnóstico não diz o que conferir')

# Um campo vazio sozinho NÃO vira "bundle não reconhecido" — são coisas diferentes.
um_so = FORM_OK.replace('- Vara: 2ª Vara do Trabalho de Araraquara', '- Vara:')
check(not achou(campos(um_so), 'BUNDLE que não foi reconhecido'),
      'um campo vazio disparou o diagnóstico de bundle degradado')
# ...e campo não-crítico sozinho não gera achado nenhum.
check(campos(um_so) == [], 'campo não-crítico vazio virou achado: %r' % campos(um_so))

# ── 5. quesitos perdidos na transcrição (a evidência que motivou o T16.2) ─────────────
perdidos = FORM_OK.replace('a) Quais foram as funções exercidas pelo reclamante?\n'
                           'b) Quais foram os setores onde trabalhou?',
                           'Não encontrado no PJE.')
fq = quesitos(perdidos)
check(achou(fq, 'Quesitos do Reclamante'), 'quesito perdido na transcrição não foi acusado')
check(achou(fq, '2 linha'), 'o aviso não diz quantas linhas o bundle trazia')

# O sentido inverso é silêncio: bundle sem quesitos + formulário dizendo que não há = certo.
bundle_sem = BUNDLE_OK.replace('a) Quais foram as funções exercidas pelo reclamante?\n'
                               'b) Quais foram os setores onde trabalhou?',
                               'Não encontrado no PJE.')
check(quesitos(perdidos, bundle_sem) == [] or
      not achou(quesitos(perdidos, bundle_sem), 'Quesitos do Reclamante'),
      'ausência legítima de quesitos virou achado')

# Bloco inteiro sumido do formulário é achado próprio.
sem_bloco = FORM_OK.replace('### Quesitos do Reclamante\n'
                            'a) Quais foram as funções exercidas pelo reclamante?\n'
                            'b) Quais foram os setores onde trabalhou?\n', '')
check(achou(quesitos(sem_bloco), 'ausente do formulário'),
      'bloco de quesito sumido não foi acusado')

# ── 6. o gate segue verde de ponta a ponta no formulário legítimo ─────────────────────
todos = []
vf.validate_process_identity(FORM_OK, BUNDLE_OK, todos)
vf.validate_campos_obrigatorios(FORM_OK, todos)
vf.validate_quesitos(FORM_OK, BUNDLE_OK, todos)
check(todos == [], 'o formulário legítimo falhou o gate: %r' % todos)

if falhas:
    print('FALHOU:')
    for x in falhas:
        print('  ✗', x)
    sys.exit(1)
print('✓ tudo verde — gate acusa campo obrigatório vazio sem alarme falso (T16.2)')
