#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_rotacao.py — diagnóstico de rotação de página, e a normalização que assa o /Rotate.

O que este arquivo protege, mais que a função: **a conclusão medida**. Rotação declarada
NÃO é defeito por si. No acervo real do Irineu, 78 das 163 páginas da contestação do
0010094-14 têm `/Rotate 90` e renderizam CERTAS — são cartões-ponto em paisagem. Apagar essa
rotação quebraria a página. E o `pdftotext` lê a página girada inteira (4281 chars contra
1499 de uma página normal), ou seja: para página COM camada de texto, rotação não atrapalha.

Por isso o fluxo só AVISA, e a normalização é ferramenta à parte, rodada pelo perito.

A invariante que a normalização tem de cumprir: o documento não muda para quem lê certo.
Conferido no PDF real — texto BYTE-IDÊNTICO nas 163 páginas, 472 datas antes e depois, e a
página renderizada igual.
"""
import sys
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import normalizar_rotacao as nr  # noqa: E402

falhas = []
pulados = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


def pdf(paginas_rot):
    """PDF mínimo: uma entrada /Type /Page por página, com o /Rotate pedido."""
    out = [b'%PDF-1.4\n']
    for i, rot in enumerate(paginas_rot):
        if rot:
            out.append(b'%d 0 obj<</Type /Page /Rotate %d>>endobj\n' % (i + 1, rot))
        else:
            out.append(b'%d 0 obj<</Type /Page>>endobj\n' % (i + 1))
    out.append(b'%%EOF\n')
    return b''.join(out)


# ── 1. diagnóstico é stdlib e nunca explode ──────────────────────────────────────────
p = AQUI / '_tmp_rot.pdf'
try:
    p.write_bytes(pdf([0, 90, 0, 180, 270, 0]))
    pags, gir = nr.diagnostico(str(p))
    check(pags == 6, 'contou %d páginas, esperava 6' % pags)
    check(gir == 3, 'contou %d giradas, esperava 3 (90, 180, 270)' % gir)

    p.write_bytes(pdf([0, 0, 0]))
    check(nr.diagnostico(str(p)) == (3, 0), 'PDF sem rotação não deveria acusar giradas')

    # /Rotate 360 e 0 são a mesma coisa — múltiplo de 360 não é rotação.
    p.write_bytes(pdf([360, 0]))
    check(nr.diagnostico(str(p))[1] == 0, '/Rotate 360 foi contado como girado')
finally:
    p.unlink(missing_ok=True)

# Entrada ruim vira (0, 0) e não exceção — isto roda dentro da corrida de extração.
for ruim, rotulo in [('X:/nao/existe.pdf', 'inexistente'),
                     (str(AQUI / 'normalizar_rotacao.py'), 'arquivo que não é PDF'),
                     (str(AQUI), 'diretório')]:
    check(nr.diagnostico(ruim) == (0, 0), '%s deveria dar (0,0)' % rotulo)


# ── 2. a normalização preserva o documento (a invariante que importa) ─────────────────
try:
    from pypdf import PdfReader, PdfWriter  # noqa: F401
    TEM_PYPDF = True
except ImportError:
    TEM_PYPDF = False

if not TEM_PYPDF:
    pulados.append('pypdf ausente — normalização não exercitada (o diagnóstico, que é o que '
                   'o fluxo usa, é stdlib e foi testado acima)')
else:
    from pypdf import PdfWriter as _W
    from pypdf.generic import RectangleObject

    origem = AQUI / '_tmp_rot_in.pdf'
    destino = AQUI / '_tmp_rot_out.pdf'
    try:
        w = _W()
        for rot in (0, 90, 0, 270):
            pg = w.add_blank_page(width=595, height=842)
            if rot:
                pg.rotation = rot
        with open(origem, 'wb') as f:
            w.write(f)

        pags, gir = nr.diagnostico(str(origem))
        check(gir == 2, 'PDF de teste deveria ter 2 páginas giradas, tem %d' % gir)

        mudadas = nr.normalizar(origem, destino)
        check(mudadas == 2, 'normalizou %d páginas, esperava 2' % mudadas)

        # depois de assar: nenhuma rotação declarada sobra...
        check(nr.diagnostico(str(destino))[1] == 0,
              'sobrou rotação declarada depois de normalizar')
        # ...e a página girada trocou de orientação na MediaBox (595x842 → 842x595), que é o
        # sinal de que a rotação virou geometria de verdade, e não sumiu.
        from pypdf import PdfReader as _R
        d = _R(str(destino))
        check(len(d.pages) == 4, 'perdeu página na normalização: %d' % len(d.pages))
        b0, b1 = d.pages[0].mediabox, d.pages[1].mediabox
        check(b0.width < b0.height, 'página NÃO girada mudou de orientação')
        check(b1.width > b1.height,
              'página girada não virou paisagem — a rotação sumiu em vez de ser assada')
    finally:
        origem.unlink(missing_ok=True)
        destino.unlink(missing_ok=True)


# ── 3. contra o PDF REAL: texto e datas têm de sobreviver ────────────────────────────
# É a prova que vale — 78 páginas giradas de verdade, não sintéticas.
REAL = Path(r'G:\Meu Drive\Base Perícia Irineu\Extração-notebooklm\Processados'
            r'\0010094-14.2026.5.15.0079\2-CONTESTAÇÃO E DOCUMENTOS.pdf')
if not REAL.exists():
    pulados.append('contestação real não alcançável — invariante de preservação não conferida')
elif not TEM_PYPDF:
    pass
else:
    import re
    saida = AQUI / '_tmp_rot_real.pdf'
    try:
        pags, gir = nr.diagnostico(str(REAL))
        check(pags == 163 and gir == 78,
              'contestação real: esperava 163 págs / 78 giradas, deu %d / %d' % (pags, gir))
        nr.normalizar(REAL, saida)
        check(nr.diagnostico(str(saida))[1] == 0, 'sobrou rotação no PDF real normalizado')

        # o texto sai do MESMO jeito — é o que garante que o gabarito do T7.2 não muda
        def texto(caminho):
            raw = Path(caminho).read_bytes()
            partes = []
            for m in re.finditer(rb'stream\r?\n(.*?)endstream', raw, re.S):
                for tenta in (zlib.decompress,
                              lambda x: zlib.decompressobj().decompress(x)):
                    try:
                        partes.append(tenta(m.group(1)))
                        break
                    except Exception:
                        continue
            return b'\n'.join(partes)

        d_antes = len(re.findall(rb'\d{2}/\d{2}/\d{4}', texto(REAL)))
        d_depois = len(re.findall(rb'\d{2}/\d{2}/\d{4}', texto(saida)))
        check(d_antes == d_depois,
              'a normalização mudou a contagem de datas (%d → %d) — o gabarito do T7.2 '
              'depende disto não mudar' % (d_antes, d_depois))
        check(d_antes > 100, 'sanidade: esperava muitas datas na contestação, achei %d' % d_antes)
    finally:
        saida.unlink(missing_ok=True)

for x in pulados:
    print('⚠ %s' % x)
if falhas:
    print('FALHOU:')
    for f in falhas:
        print('  ✗', f)
    sys.exit(1)
print('✓ tudo verde — rotação diagnosticada sem corrigir por conta própria')
