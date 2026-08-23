#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_sonda_no_formulario.py — a sonda por data tem de CHEGAR ao formulário, não morrer no log.

Origem (23/08/2026, conferência do laudo do Jeferson, proc. 0010094-14): o extrator devolveu
34 das 38 entregas da ficha; as 4 perdidas estavam TODAS em 31/01/2025 — uma entrega grande
partida entre o fim da pág. 4 e o recomeço na pág. 6, com itens repetidos nos dois blocos. O
modelo tratou a repetição como engano de digitação e "limpou".

O que este arquivo trava é o elo que faltava, não a detecção: `conferir_por_data` já acusava
`31/01/2025: 6 de 10` desde a v1.5.2 — **no console do lote**. O formulário, que é o que o
perito lê na diligência, saiu limpo, e o laudo foi redigido em cima dele. Detecção que não
chega a quem decide vale zero.

⚠ Duas pontas, dois arquivos: quem ESCREVE a nota é o `extrai_processo` (01b) e quem a LÊ é o
`montar_formulario` (01). A string do marcador está duplicada — se as duas divergirem, a nota
some em silêncio, que é exatamente o defeito que este teste existe para impedir.
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / '01-extrator'))
import extrai_processo as ep          # noqa: E402
import montar_formulario as mf        # noqa: E402

falhas = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


IMPR, DEM = '26/01/2021', '08/12/2025'

# A ficha do Jeferson, reduzida ao dia que se perdeu: 31/01/2025 tem 10 linhas na ficha e o
# modelo devolveu 6 — as 4 que faltam são as repetições do segundo bloco (18069, 37089,
# colete) mais o capuz 38352.
TABELA = """| Data de Entrega | Quantidade | Descrição do EPI | C.A. |
| :--- | :---: | :--- | :---: |
| 07/02/2024 | 1 | PROTETOR AUDITIVO SILICONE PLUGUE | 11512 |
| 07/02/2024 | 1 | CREME PROT PELE G3 LUZ NEGRA 120G | 35339 |
| 31/01/2025 | 1 | OCULOS PROT POLICARB CZ ESPORT | 18069 |
| 31/01/2025 | 1 | PROTETOR AUDITIVO SILICONE PLUGUE | 5745 |
"""


def t_nota_vazia_nao_alarma():
    """Sem déficit, nada de 🚩 — gate que grita à toa é gate que o perito aprende a ignorar."""
    check(ep.nota_sonda([]) == '', 'sem déficit a nota tem de ser vazia')
    rows = mf.parse_ficha_rows(TABELA, IMPR, DEM)
    check(rows and not any('🚩' in r for r in rows), 'tabela sem nota não pode ganhar 🚩')
    check(len(rows) == 4, 'as 4 entregas continuam na tabela (saiu %d)' % len(rows))


def t_nota_traz_a_data_e_a_conta():
    nota = ep.nota_sonda([('31/01/2025', 10, 6)])
    check(nota.startswith(ep.SONDA_FICHA), 'a nota tem de começar pelo marcador')
    check('31/01/2025: 6 de 10' in nota, 'a nota tem de dizer a data e a conta: %r' % nota)
    check('~4 entrega(s)' in nota, 'a nota tem de somar o que falta: %r' % nota)
    check('repetida' in nota, 'a nota tem de dizer POR QUE se perde (linha repetida)')


def t_nota_chega_ao_topo_da_tabela():
    """O caminho inteiro: sonda → texto da P3a → bundle → parse_ficha_rows → formulário."""
    p3a = TABELA + '\n\n' + ep.nota_sonda([('31/01/2025', 10, 6)])
    rows = mf.parse_ficha_rows(p3a, IMPR, DEM)
    check(rows and rows[0].startswith('- 🚩'), 'a nota tem de vir na PRIMEIRA linha: %r' % (rows[:1],))
    check('31/01/2025: 6 de 10' in rows[0], 'a data perdida tem de aparecer no formulário')
    check(ep.SONDA_FICHA not in rows[0], 'o marcador cru não vai para o formulário: %r' % rows[0])
    entregas = [r for r in rows if '🚩' not in r]
    check(len(entregas) == 4, 'a nota não pode comer entrega (sobraram %d de 4)' % len(entregas))
    check(any('11512' in r for r in entregas), 'a entrega de 07/02/2024 continua lá')


def t_marcador_espelhado_nos_dois_lados():
    check(ep.SONDA_FICHA == mf.SONDA_FICHA,
          'marcador divergente: 01b=%r × 01=%r — a nota sumiria em silêncio'
          % (ep.SONDA_FICHA, mf.SONDA_FICHA))


def t_prompt_manda_transcrever_a_repeticao():
    """A causa-raiz é o prompt: sem essa regra o modelo continua 'limpando' a repetição."""
    p = AQUI / 'assets' / 'prompts-extracao-notebooklm.md'
    txt = p.read_text(encoding='utf-8')
    check('LINHA REPETIDA NO MESMO DIA' in txt, 'falta a regra da linha repetida na Parte 3a')
    check('MAIS DE UM BLOCO' in txt, 'falta a regra da data partida entre páginas')


for t in (t_nota_vazia_nao_alarma, t_nota_traz_a_data_e_a_conta, t_nota_chega_ao_topo_da_tabela,
          t_marcador_espelhado_nos_dois_lados, t_prompt_manda_transcrever_a_repeticao):
    print('T —', t.__doc__.splitlines()[0] if t.__doc__ else t.__name__)
    t()

if falhas:
    print('\n❌ FALHAS:')
    for f in falhas:
        print('  -', f)
    sys.exit(1)
print('\nOK — a sonda por data chega ao formulário')
