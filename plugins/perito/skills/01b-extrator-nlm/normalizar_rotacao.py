#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
normalizar_rotacao.py — "assa" a rotação declarada das páginas no conteúdo do PDF.

## Por que existe, e por que NÃO liga sozinho

A recomendação de origem era "corrigir a orientação das páginas antes de extrair". Medido no
acervo real do Irineu, o quadro é mais estreito do que parece:

- Na contestação do 0010094-14, **78 das 163 páginas têm `/Rotate 90`** — e, renderizadas,
  elas saem **CORRETAS**: são cartões-ponto em paisagem, e o `/Rotate` é metadado CERTO.
  Apagar ou "corrigir" essa rotação QUEBRA a página. Não é defeito.
- Para página COM camada de texto, rotação não atrapalha a extração: o `pdftotext` lê a
  página girada inteira (4281 chars na pág. 24, contra 1499 numa página normal).
- O caso que a recomendação descreve — scan de cabeça para baixo — só machuca quem lê por
  VISÃO, e só é detectável por OCR. Sem OCR não há como saber, e chutar seria pior.

Sobra um ganho real e estreito: **um leitor que IGNORE o `/Rotate` lê a página deitada.**
Assar a rotação no conteúdo deixa o PDF sem ambiguidade para qualquer leitor — o que um
leitor correto vê não muda (conferido: a página renderiza idêntica antes e depois).

Como não está provado que o Gemini Notebook ignora `/Rotate`, este script **não roda
sozinho**: o `extrai_processo.py` apenas AVISA quando a ficha tem páginas giradas, e quem
decide rodar é o perito. Ligar por padrão em cima de hipótese não medida é como se troca um
problema conhecido por um desconhecido.

## Dependência

Precisa do `pypdf` (não é stdlib — o resto da skill é). Sem ele, o script explica e para,
no mesmo padrão do Pandoc na skill 06. Nada no fluxo depende disto.

uso:
  python normalizar_rotacao.py <ficha.pdf>                  # só o diagnóstico
  python normalizar_rotacao.py <ficha.pdf> -o <saida.pdf>   # grava a cópia normalizada
"""
import argparse
import re
import sys
import zlib
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

_ROTATE_RE = re.compile(rb'/Rotate\s+(-?\d+)')
_PAGE_RE = re.compile(rb'/Type\s*/Page[^sA-Za-z]')
_STREAM_RE = re.compile(rb'stream\r?\n(.*?)endstream', re.S)


def diagnostico(pdf_path):
    """(paginas, giradas) sem depender do pypdf — stdlib, para o extrai_processo poder
    AVISAR mesmo onde o pypdf não está instalado."""
    try:
        raw = Path(pdf_path).read_bytes()
    except Exception:
        return 0, 0
    if not raw[:1024].lstrip().startswith(b'%PDF'):
        return 0, 0
    todo = [raw]
    for m in _STREAM_RE.finditer(raw):
        for tenta in (zlib.decompress, lambda x: zlib.decompressobj().decompress(x)):
            try:
                todo.append(tenta(m.group(1)))
                break
            except Exception:
                continue
    blob = b'\n'.join(todo)
    pags = len(_PAGE_RE.findall(blob))
    giradas = sum(1 for v in _ROTATE_RE.findall(blob) if int(v) % 360 != 0)
    return pags, giradas


def normalizar(entrada, saida):
    """Assa o /Rotate no conteúdo de cada página. Devolve quantas páginas mudaram.

    `transfer_rotation_to_content()` aplica a rotação ao conteúdo e zera o /Rotate; a
    MediaBox acompanha (595x842 vira 842x595). Conferido visualmente: a página renderizada
    fica IDÊNTICA — é o mesmo documento, dito de um jeito que não depende do leitor honrar
    um campo de metadado.
    """
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        sys.exit('ERRO: este script precisa do pypdf (não é stdlib, como o resto da skill).\n'
                 '      Instale com:  python -m pip install --user pypdf\n'
                 '      Nada do fluxo de extração depende dele — é uma ferramenta à parte.')
    leitor = PdfReader(str(entrada))
    escritor = PdfWriter()
    mudadas = 0
    for pg in leitor.pages:
        if int(pg.get('/Rotate') or 0) % 360 != 0:
            pg.transfer_rotation_to_content()
            mudadas += 1
        escritor.add_page(pg)
    with open(saida, 'wb') as f:
        escritor.write(f)
    return mudadas


def main():
    ap = argparse.ArgumentParser(description='Assa a rotação declarada das páginas no conteúdo.')
    ap.add_argument('pdf')
    ap.add_argument('-o', '--output', help='PDF de saída (sem isto, só diagnostica)')
    args = ap.parse_args()

    entrada = Path(args.pdf)
    if not entrada.exists():
        sys.exit('ERRO: arquivo não encontrado: %s' % entrada)

    pags, giradas = diagnostico(entrada)
    print('%s: %d página(s), %d com rotação declarada.' % (entrada.name, pags, giradas))
    if not giradas:
        print('Nada a normalizar. ⚠ Isto NÃO quer dizer que as páginas estão em pé: um scan '
              'de cabeça para baixo com /Rotate 0 não deixa rastro no PDF, e detectá-lo '
              'exigiria OCR. Se a leitura vier ruim, confira a olho.')
        return 0
    print('⚠ Rotação declarada NÃO é defeito por si: no acervo do Irineu as 78 páginas '
          'giradas da contestação do 0010094-14 são cartões-ponto em paisagem, e renderizam '
          'CERTAS. Normalizar só ajuda se quem lê o PDF ignorar o campo /Rotate.')
    if not args.output:
        print('(diagnóstico apenas — passe -o <saida.pdf> para gravar a cópia normalizada)')
        return 0

    saida = Path(args.output)
    if saida.resolve() == entrada.resolve():
        sys.exit('ERRO: a saída não pode ser o próprio arquivo de entrada — o original dos '
                 'autos não se sobrescreve.')
    mudadas = normalizar(entrada, saida)
    print('✓ %d página(s) normalizada(s) → %s' % (mudadas, saida))
    print('  O original fica intacto. Confira uma página girada antes e depois (o conteúdo '
          'tem de ficar IDÊNTICO) antes de usar a cópia numa extração.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
