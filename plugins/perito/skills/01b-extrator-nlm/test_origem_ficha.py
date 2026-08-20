#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_origem_ficha.py — a origem da ficha é MEDIDA, não acreditada.

O bundle já traz `▶ ORIGEM DA FICHA: [X] PDF digital nativo · [ ] Imagem escaneada…`, mas
quem marca é o MODELO. E essa linha decide o peso de tudo o que vem depois: em ficha com
tabela legível a contagem fecha exata; em manuscrita, duas gerações do mesmo artefato deram
314 e 395 entregas.

O que se mede NÃO é "o PDF é digital?". Medido nos PDFs do Irineu, a petição inicial tem
3299 chars/página e UMA data distinta no documento inteiro — densidade de texto sozinha
chamaria a petição de ficha. A pergunta certa é "este PDF expõe uma TABELA DE ENTREGAS
legível?", e quem responde é a diversidade de datas por página.

Este arquivo tem dois níveis: as invariantes (sempre) e a calibragem contra os PDFs reais
do Drive (quando alcançáveis). Os PDFs não entram no repo — são autos de processo.
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


# ── 1. degrada com elegância: entrada ruim NUNCA vira veredicto confiante ─────────────
# 'indeterminado' é resposta legítima — quem não sabe não decide o ramo da ficha.
for entrada, rotulo in [('X:/nao/existe.pdf', 'caminho inexistente'),
                        (str(AQUI / 'extrai_processo.py'), 'arquivo que não é PDF'),
                        (str(AQUI), 'um diretório')]:
    origem, med = ep.sondar_origem_ficha(entrada)
    check(origem == 'indeterminado',
          '%s deveria dar indeterminado, deu %r' % (rotulo, origem))
    check(med == {}, '%s devolveu medidas apesar de indeterminado' % rotulo)

# PDF sintético: cabeçalho válido, uma página, sem nenhum texto → sem tabela legível.
vazio = AQUI / '_tmp_teste_pdf_vazio.pdf'
vazio.write_bytes(b'%PDF-1.4\n1 0 obj<</Type /Page>>endobj\n%%EOF\n')
try:
    origem, med = ep.sondar_origem_ficha(str(vazio))
    check(origem == 'escaneada',
          'PDF sem camada de texto deveria cair no ramo escaneada, deu %r' % origem)
    check(med.get('datas_distintas') == 0, 'PDF vazio achou datas: %r' % med)
finally:
    vazio.unlink(missing_ok=True)


def _pdf_com_datas(datas, paginas):
    """PDF mínimo, de verdade: as datas vão num stream FlateDecode, atrás de um (..)Tj —
    que é exatamente o caminho que a sonda percorre."""
    conteudo = ' '.join('(%s) Tj' % d for d in datas).encode('latin-1')
    stream = zlib.compress(conteudo)
    corpo = [b'%PDF-1.4\n']
    for _ in range(paginas):
        corpo.append(b'1 0 obj<</Type /Page>>endobj\n')
    corpo.append(b'2 0 obj<</Filter /FlateDecode>>stream\n' + stream + b'\nendstream endobj\n')
    corpo.append(b'%%EOF\n')
    return b''.join(corpo)


# ── 2. o discriminador é a DIVERSIDADE de datas, não a quantidade de texto ────────────
p = AQUI / '_tmp_teste_pdf.pdf'
try:
    # (a) tabela de entregas legível: muitas datas distintas em poucas páginas
    p.write_bytes(_pdf_com_datas(['%02d/03/2023' % d for d in range(1, 18)], 7))
    origem, med = ep.sondar_origem_ficha(str(p))
    check(origem == 'digital', 'ficha com 17 datas distintas em 7 págs deu %r (%r)' % (origem, med))

    # (b) O CASO ADVERSÁRIO, e o motivo de a régua não ser "tem texto?": 20 páginas com a
    #     MESMA data repetida — o carimbo do PJe. Tem camada de texto e não tem tabela.
    p.write_bytes(_pdf_com_datas(['11/03/2022'] * 20, 20))
    origem, med = ep.sondar_origem_ficha(str(p))
    check(origem == 'escaneada',
          'carimbo do PJe (20 págs, 1 data repetida) passou como digital: %r' % med)
    check(med['datas'] == 20 and med['datas_distintas'] == 1,
          'a sonda não separou ocorrências de distintas: %r' % med)

    # (c) fronteira: exatamente no limiar conta como legível
    n = int(ep.LIMIAR_DATAS_POR_PAGINA * 4)
    p.write_bytes(_pdf_com_datas(['%02d/03/2023' % (d + 1) for d in range(n)], 4))
    check(ep.sondar_origem_ficha(str(p))[0] == 'digital', 'fronteira do limiar não inclui o piso')
finally:
    p.unlink(missing_ok=True)


# ── 3. a declaração do modelo é lida das duas formas ──────────────────────────────────
DIGITAL = '▶ ORIGEM DA FICHA: [X] PDF digital nativo (texto selecionável) · [ ] Imagem escaneada / manuscrita / OCR'
ESCANE = '▶ ORIGEM DA FICHA: [ ] PDF digital nativo (texto selecionável) · [X] Imagem escaneada / manuscrita / OCR'
check(ep.origem_declarada(DIGITAL) == 'digital', 'não leu a declaração digital')
check(ep.origem_declarada(ESCANE) == 'escaneada', 'não leu a declaração escaneada')
check(ep.origem_declarada('▶ ORIGEM DA FICHA: [ ] PDF digital · [ ] Imagem escaneada') is None,
      'nada marcado deveria dar None, não um chute')
check(ep.origem_declarada('') is None, 'resposta vazia deveria dar None')
check(ep.origem_declarada('▶ EVIDÊNCIA DE ASSINATURA: Sim') is None,
      'leu declaração de uma linha que não é a da origem')

# ── 4. o cruzamento avisa, e NUNCA levanta exceção (roda dentro da corrida) ───────────
msgs = []
ep.conferir_origem_ficha('X:/nao/existe.pdf', DIGITAL, log_fn=msgs.append)
check(any('não foi possível medir' in m for m in msgs),
      'medição impossível não foi comunicada: %r' % msgs)

p2 = AQUI / '_tmp_teste_pdf2.pdf'
try:
    p2.write_bytes(_pdf_com_datas(['11/03/2022'] * 20, 20))   # medida: escaneada
    msgs = []
    ep.conferir_origem_ficha(str(p2), DIGITAL, log_fn=msgs.append)   # declarada: digital
    junto = ' '.join(msgs)
    check('DIVERGE' in junto, 'divergência declaração×medida não foi acusada: %r' % msgs)
    check('ROTEIRO DE DILIGÊNCIA' in junto,
          'o ramo escaneado não avisou que a extração não é fonte de verdade')
    check('mantém o que o modelo escreveu' in junto,
          'o aviso não deixa claro que o bundle NÃO foi alterado')

    msgs = []
    ep.conferir_origem_ficha(str(p2), ESCANE, log_fn=msgs.append)    # concordam
    check(not any('DIVERGE' in m for m in msgs),
          'acusou divergência onde declaração e medida concordam')
finally:
    p2.unlink(missing_ok=True)

# ── 5. calibragem contra os PDFs REAIS (só quando o Drive está alcançável) ────────────
REAIS = [
    (r'G:\Meu Drive\Base Perícia Irineu\Extração-notebooklm\Processados'
     r'\0010094-14.2026.5.15.0079\3-EPI.pdf', 'digital',
     'ficha de 7 fls. que saiu ÍNTEGRA e bateu exato contra o pdftotext'),
    (r'G:\Meu Drive\Base Perícia Irineu\Extração-notebooklm\Processados'
     r'\0017000-78.2025.5.15.0071\4-ficha de epi.pdf', 'escaneada',
     'ficha sem camada de texto (7 chars no documento inteiro)'),
    (r'G:\Meu Drive\Base Perícia Irineu\Extração-notebooklm\Processados'
     r'\0010094-14.2026.5.15.0079\1-INICIAL.pdf', 'escaneada',
     'CONTROLE: petição com muito texto e nenhuma tabela de entregas — densidade de '
     'texto sozinha a chamaria de ficha'),
]
for caminho, esperado, porque in REAIS:
    if not Path(caminho).exists():
        pulados.append(Path(caminho).name)
        continue
    origem, med = ep.sondar_origem_ficha(caminho)
    check(origem == esperado,
          '%s: esperava %r, deu %r (%r) — %s' % (Path(caminho).name, esperado, origem, med, porque))

if pulados:
    print('⚠ PDFs reais não alcançáveis, calibragem pulada: %s' % ', '.join(sorted(set(pulados))))
if falhas:
    print('FALHOU:')
    for f in falhas:
        print('  ✗', f)
    sys.exit(1)
print('✓ tudo verde — origem da ficha medida, carimbo do PJe separado de tabela real')
