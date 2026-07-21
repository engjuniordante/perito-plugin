#!/usr/bin/env python3
"""Prepara os laudos da 09-Inbox (.docx/.md) para a leitura da skill Povoar Base.

Converte DOCX em Markdown com Pandoc (GFM, sem quebra de linha) em
09-Inbox/.convertidos-md/ e valida o mínimo que um laudo precisa ter para virar
texto-padrão: nº CNJ do processo e ao menos uma seção 6.x (NR-15) ou 7.x (NR-16).
Também aponta duplicados intra-lote pelo nº do processo.

O DOCX original é imutável: nada é sobrescrito, apagado ou movido daqui.
Este script NÃO grava na base de conhecimento e NÃO arquiva laudos — isso é o
segundo passo do fluxo, e só depois do OK do perito.

Uso: python preparar_inbox.py "<base_conhecimento>/09-Inbox"
     (exit 0 = pronto para análise; exit 2 = bloqueado)
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Piso 3.9 (anotações builtin) + stdout/err UTF-8: no Windows a saída capturada cai em
# cp1252 (Python <3.15) e um acento do relatório mataria o script com UnicodeEncodeError.
if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

PROCESSO_RE = re.compile(r'\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b')
SECAO_RE = re.compile(r'(?<!\d)([67])\s*[.]\s*(\d{1,2})(?!\d)')


def validar_markdown(path: Path):
    """Devolve (processos, seções, erros, avisos) do laudo em Markdown."""
    texto = path.read_text(encoding='utf-8', errors='replace')
    processos = sorted(set(PROCESSO_RE.findall(texto)))
    secoes = sorted(set(f'{a}.{int(b)}' for a, b in SECAO_RE.findall(texto)))
    erros = []
    avisos = []
    if not processos:
        erros.append('número CNJ do processo não localizado')
    if not secoes:
        erros.append('nenhuma seção 6.x da NR-15 ou 7.x da NR-16 localizada')
    else:
        # Faltar um dos grupos é normal (laudo só de insalubridade ou só de
        # periculosidade) — avisa para o perito confirmar, mas não bloqueia.
        if not any(s.startswith('6.') for s in secoes):
            avisos.append('sem seção 6.x; confirmar se o laudo é somente de periculosidade')
        if not any(s.startswith('7.') for s in secoes):
            avisos.append('sem seção 7.x; confirmar se o laudo é somente de insalubridade')
    return processos, secoes, erros, avisos


def converter(docx: Path, destino: Path, pandoc: str):
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [pandoc, str(docx), '-t', 'gfm', '--wrap=none', '-o', str(destino)],
        check=True,
        capture_output=True,
        text=True,
    )


def preparar(inbox: Path):
    if not inbox.is_dir():
        print(f'ERRO: inbox não encontrada: {inbox}', file=sys.stderr)
        return 2

    # ~$ = lock file do Word aberto; não é laudo.
    docx_files = sorted(p for p in inbox.glob('*.docx') if not p.name.startswith('~$'))
    md_files = sorted(inbox.glob('*.md'))
    if not docx_files and not md_files:
        print(f'ERRO: nenhum .docx ou .md em {inbox}', file=sys.stderr)
        return 2

    pandoc = shutil.which('pandoc')
    if docx_files and not pandoc:
        print('ERRO: Pandoc não instalado. Instale-o e rode novamente.', file=sys.stderr)
        print('Windows: winget install --id JohnMacFarlane.Pandoc', file=sys.stderr)
        print('macOS: brew install pandoc', file=sys.stderr)
        return 2

    preparados = list(md_files)
    intermediarios = []
    for origem in docx_files:
        destino = inbox / '.convertidos-md' / f'{origem.stem}.md'
        try:
            converter(origem, destino, pandoc)
        except subprocess.CalledProcessError as exc:
            detalhe = (exc.stderr or exc.stdout or '').strip()
            print(f'ERRO: falha ao converter {origem.name}: {detalhe}', file=sys.stderr)
            return 2
        preparados.append(destino)
        intermediarios.append((origem, destino))
        print(f'CONVERTIDO: {origem.name} -> {destino.relative_to(inbox)}')

    falhas = []
    vistos = {}
    for md in preparados:
        processos, secoes, erros, avisos = validar_markdown(md)
        if len(processos) > 1:
            erros.append('mais de um número de processo localizado: ' + ', '.join(processos))
        if processos:
            for processo in processos:
                vistos.setdefault(processo, []).append(md)
        if erros:
            falhas.append((md, erros))
            print(f'INVÁLIDO: {md.name} — ' + '; '.join(erros))
        else:
            print(f'VALIDADO: {md.name} — processo {processos[0]} — '
                  f'{len(secoes)} seções 6.x/7.x localizadas')
            for aviso in avisos:
                print(f'AVISO: {md.name} — {aviso}')

    duplicados = {p: arquivos for p, arquivos in vistos.items() if len(arquivos) > 1}
    for processo, arquivos in duplicados.items():
        nomes = ', '.join(a.name for a in arquivos)
        print(f'AVISO DUPLICADO: processo {processo} aparece em: {nomes}')

    if falhas:
        print('BLOQUEADO: corrija os arquivos inválidos antes de atualizar ou mover a base.',
              file=sys.stderr)
        return 2

    print(f'OK: {len(preparados)} Markdown(s) pronto(s) para análise; originais preservados.')
    if intermediarios:
        print('Os Markdown intermediários estão em 09-Inbox/.convertidos-md/.')
    print('PRÓXIMO PASSO: analisar e mostrar o diff; não gravar na base sem confirmação do perito.')
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='Converte DOCX da 09-Inbox em Markdown e valida o conteúdo mínimo.')
    parser.add_argument('inbox', type=Path, help='caminho da pasta 09-Inbox')
    args = parser.parse_args()
    return preparar(args.inbox.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
