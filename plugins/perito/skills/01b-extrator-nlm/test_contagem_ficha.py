#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contagem_ficha.py — T7.2 (gabarito contra o documento) e T7.3 (entregas por página).

Até aqui não existia NENHUMA conferência independente da CONTAGEM: o check_epi classifica
por C.A. o que já está na tabela, e o checklist da skill é o modelo conferindo o bundle
contra o próprio bundle. Conferência que fecha com ela mesma não pega nada — o motor gêmeo
declarou 240, listou 240, e faltavam 15. Zero alarme.

⚠ O eixo que manda neste arquivo: **a ficha de EPI não tem layout único**. Cada empregador
imprime a sua, e aparecem modelos novos o tempo todo. Por isso a régua conta UMA data por
linha, a primeira, onde quer que ela esteja — e por isso metade dos testes abaixo é a MESMA
ficha em layouts diferentes.
"""
import sys
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import extrai_processo as ep  # noqa: E402

falhas = []
pulados = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


def pdf_com_linhas(linhas, paginas=1):
    """PDF mínimo mas de verdade: cada linha vira (texto)Tj separado por T* (quebra de linha
    do PDF), num stream FlateDecode — o caminho exato que a sonda percorre."""
    corpo = []
    for ln in linhas:
        txt = ln.replace('\\', '').replace('(', '').replace(')', '')
        corpo.append(('(%s) Tj T*' % txt).encode('latin-1', 'replace'))
    stream = zlib.compress(b'BT ' + b' '.join(corpo) + b' ET')
    out = [b'%PDF-1.4\n']
    for _ in range(paginas):
        out.append(b'1 0 obj<</Type /Page>>endobj\n')
    out.append(b'2 0 obj<</Filter /FlateDecode>>stream\n' + stream + b'\nendstream endobj\n')
    out.append(b'%%EOF\n')
    return b''.join(out)


def com_pdf(linhas, paginas=1):
    p = AQUI / '_tmp_contagem.pdf'
    p.write_bytes(pdf_com_linhas(linhas, paginas))
    return p


DATAS = ['%02d/03/2023' % d for d in range(1, 21)]        # 20 entregas


# ── 1. LAYOUT: a mesma ficha de 20 entregas, escrita de cinco jeitos ──────────────────
# Este é o teste que a variedade de modelos exige. Se algum layout zerar o gabarito, a
# conferência daquela ficha vira silêncio — e silêncio aqui parece concordância.
LAYOUTS = {
    'data no início':        [d + ' BOTINA VAQ PR CA 26149' for d in DATAS],
    'nº de item antes':      ['%03d  %s  BOTINA VAQ PR  26149' % (i + 1, d) for i, d in enumerate(DATAS)],
    'código de produto antes': ['SKU-4871 %s BOTINA VAQ PR CA 26149' % d for d in DATAS],
    'tabela com pipes':      ['| %s | 1 | BOTINA VAQ PR | 26149 |' % d for d in DATAS],
    'validade do C.A. junto': ['%s BOTINA CA 26149 val. 31/12/2027' % d for d in DATAS],
}
for nome, linhas in LAYOUTS.items():
    p = com_pdf(linhas, paginas=2)
    try:
        datas, pags = ep.gabarito_entregas(str(p))
        check(len(datas) == 20,
              'layout %r: gabarito deu %d, esperava 20 — um modelo de ficha que a régua não '
              'lê vira conferência silenciosa' % (nome, len(datas)))
    finally:
        p.unlink(missing_ok=True)

# A linha com DUAS datas conta UMA vez, e é a de ENTREGA (a primeira) — numa das fichas
# medidas a segunda data era a validade do C.A., e contar todas inflava o gabarito.
p = com_pdf(LAYOUTS['validade do C.A. junto'])
try:
    datas, _ = ep.gabarito_entregas(str(p))
    check(len(datas) == 20, 'linha com validade do C.A. contou duas vezes: %d' % len(datas))
    check('31/12/2027' not in datas, 'a régua pegou a validade do C.A. em vez da entrega')
finally:
    p.unlink(missing_ok=True)


# ── 2. contar o que o modelo transcreveu ─────────────────────────────────────────────
TABELA = '\n'.join('| %s | 1 | BOTINA | 26149 |' % d for d in DATAS)
check(ep.contar_entregas_transcritas(TABELA) == 20,
      'não contou as 20 linhas da tabela markdown')
BULLETS = '\n'.join('- %s · 1un · BOTINA · CA 26149' % d for d in DATAS)
check(ep.contar_entregas_transcritas(BULLETS) == 20,
      'não contou o formato de bullet do montador')
check(ep.contar_entregas_transcritas('') == 0, 'resposta vazia deveria contar 0')
check(ep.contar_entregas_transcritas('Data da Autuação: 26/01/2026') == 0,
      'linha de prosa com data virou entrega')


# ── 3. T7.2 — a contagem que não fecha ───────────────────────────────────────────────
p = com_pdf(LAYOUTS['data no início'], paginas=2)
try:
    # (a) leitura íntegra: 20 de 20 → confere, sem alarme
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'digital', log_fn=msgs.append)
    junto = ' '.join(msgs)
    check('confere' in junto and 'NÃO FECHA' not in junto,
          'leitura íntegra gerou alarme: %r' % msgs)

    # (b) COLAPSO: o modelo devolveu 5 de 20 — o modo de falha que motivou o T7
    curta = '\n'.join('| %s | 1 | BOTINA | 26149 |' % d for d in DATAS[:5])
    msgs = []
    ep.conferir_contagem(str(p), curta, 'digital', log_fn=msgs.append)
    junto = ' '.join(msgs)
    check('NÃO FECHA' in junto, 'colapso 5/20 não foi acusado: %r' % msgs)
    check('Faltam' in junto, 'o aviso não diz quantas faltam')
    check('TETO aproximado' in junto,
          'o aviso não avisa que o gabarito é aproximado — dar número exato aqui é mentira')

    # (c) diferença pequena NÃO alarma: o gabarito pega cabeçalho junto, e alarme falso em
    #     gate diário ensina o perito a ignorar o gate.
    quase = '\n'.join('| %s | 1 | BOTINA | 26149 |' % d for d in DATAS[:17])   # 85%
    msgs = []
    ep.conferir_contagem(str(p), quase, 'digital', log_fn=msgs.append)
    check('NÃO FECHA' not in ' '.join(msgs), '17/20 (85%%) deu alarme falso: %r' % msgs)
finally:
    p.unlink(missing_ok=True)


# ── 4. T7.3 — entregas por página, o sinal que vale sem gabarito nenhum ───────────────
p = com_pdf(LAYOUTS['data no início'], paginas=20)      # 20 págs
try:
    msgs = []
    curta = '\n'.join('| %s | 1 | BOTINA | 26149 |' % d for d in DATAS[:5])   # 0,25/pág
    ep.conferir_contagem(str(p), curta, 'digital', log_fn=msgs.append)
    check(any('LEITURA COLAPSADA' in m for m in msgs),
          '0,25 entrega/página não disparou o piso do T7.3: %r' % msgs)
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'digital', log_fn=msgs.append)       # 1,0/pág
    check(not any('LEITURA COLAPSADA' in m for m in msgs),
          '1,0 entrega/página disparou o piso (o piso é 0,5)')
finally:
    p.unlink(missing_ok=True)


# ── 5. ficha REIMPRESSA: não comparar é a resposta certa ─────────────────────────────
# O PDF traz o mesmo histórico duas vezes, com rodapés de emissão em datas distintas. A
# contagem sai em dobro e a guarda acusaria datas que estão certas.
reimpressa = (LAYOUTS['data no início'] + ['Emissao: 10/01/2024']
              + LAYOUTS['data no início'] + ['Emissao: 22/07/2025'])
p = com_pdf(reimpressa, paginas=4)
try:
    check(len(ep.ficha_reimpressa(str(p))) == 2,
          'não achou os dois rodapés de emissão: %r' % ep.ficha_reimpressa(str(p)))
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'digital', log_fn=msgs.append)
    junto = ' '.join(msgs)
    check('REIMPRESSA' in junto, 'ficha reimpressa não foi sinalizada: %r' % msgs)
    check('NÃO FECHA' not in junto,
          'comparou apesar da reimpressão — é exatamente o alarme falso a evitar')
finally:
    p.unlink(missing_ok=True)

# Uma emissão só não é reimpressão.
p = com_pdf(LAYOUTS['data no início'] + ['Emissao: 10/01/2024'], paginas=2)
try:
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'digital', log_fn=msgs.append)
    check('REIMPRESSA' not in ' '.join(msgs), 'uma emissão só virou reimpressão')
finally:
    p.unlink(missing_ok=True)


# ── 6. quando NÃO dá para conferir, dizer isso — silêncio parece concordância ─────────
# (a) layout que a régua não leu: gabarito menor que o transcrito
p = com_pdf(['BOTINA VAQ PR CA 26149'] * 20, paginas=2)      # nenhuma data legível
try:
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'digital', log_fn=msgs.append)
    junto = ' '.join(msgs)
    check('não leu o layout' in junto or 'não consegui montar gabarito' in junto,
          'gabarito cego passou calado: %r' % msgs)
    check('Não é sinal de que está certo' in junto or 'sem conferência automática' in junto,
          'o aviso deixa parecer que a contagem foi conferida')
finally:
    p.unlink(missing_ok=True)

# (b) ramo escaneado: não há gabarito possível, e isso tem de ser dito
p = com_pdf(LAYOUTS['data no início'], paginas=2)
try:
    msgs = []
    ep.conferir_contagem(str(p), TABELA, 'escaneada', log_fn=msgs.append)
    junto = ' '.join(msgs)
    check('SEM conferência automática' in junto,
          'ramo escaneado não avisou que não há conferência: %r' % msgs)
    check('NÃO FECHA' not in junto and 'confere' not in junto,
          'ramo escaneado comparou com um gabarito que não vale ali')
finally:
    p.unlink(missing_ok=True)


# ── 7. calibragem contra a ficha REAL (quando o Drive está alcançável) ────────────────
REAL = Path(r'G:\Meu Drive\Base Perícia Irineu\Extração-notebooklm\Processados'
            r'\0010094-14.2026.5.15.0079\3-EPI.pdf')
if REAL.exists():
    datas, pags = ep.gabarito_entregas(str(REAL))
    check(pags == 7, 'ficha real: esperava 7 páginas, deu %d' % pags)
    check(40 <= len(datas) <= 50,
          'ficha real: gabarito %d fora da faixa medida (~45 p/ 38 entregas reais)' % len(datas))
    # 38 é a contagem REAL de entregas desta ficha (a extração dela saiu íntegra e bateu
    # exato contra o pdftotext). Não pode dar alarme.
    msgs = []
    transcrito = '\n'.join('| %s | 1 | X | 1 |' % d for d in datas[:38])
    ep.conferir_contagem(str(REAL), transcrito, 'digital', log_fn=msgs.append)
    check('NÃO FECHA' not in ' '.join(msgs),
          'ALARME FALSO na ficha real (38 entregas verdadeiras): %r' % msgs)
    check(not any('COLAPSADA' in m for m in msgs),
          'ficha real (38 entregas em 7 págs) disparou o piso do T7.3')
else:
    pulados.append(REAL.name)

if pulados:
    print('⚠ PDF real não alcançável, calibragem pulada: %s' % ', '.join(pulados))
if falhas:
    print('FALHOU:')
    for f in falhas:
        print('  ✗', f)
    sys.exit(1)
print('✓ tudo verde — contagem conferida contra o documento em 5 layouts de ficha (T7.2/T7.3)')
