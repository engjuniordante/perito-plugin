#!/usr/bin/env python3
"""Regressão do preparador da inbox (preparar_inbox.py).
Trava o contrato: DOCX original intacto, validação CNJ/seções e aviso de duplicado."""
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))
import preparar_inbox as pi

CNJ = '0099999-99.2099.5.99.9999'
CNJ2 = '0088888-88.2088.5.88.8888'
VALIDO = f'Processo: {CNJ}\n## 6.15 Agentes biológicos\n## 7.2 Inflamáveis\n'

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


print("T1 — validar_markdown classifica processo, seções, erros e avisos")
with tempfile.TemporaryDirectory() as td:
    md = Path(td) / 'laudo.md'
    md.write_text(VALIDO, encoding='utf-8')
    proc, sec, erros, avisos = pi.validar_markdown(md)
    check(proc == [CNJ] and sec == ['6.15', '7.2'] and not erros and not avisos, 'MD válido')

    md.write_text(f'Processo: {CNJ}\n## 6.15 Biológicos\n', encoding='utf-8')
    _, _, erros, avisos = pi.validar_markdown(md)
    check(not erros and avisos, 'laudo só de insalubridade gera aviso, não bloqueio')

    md.write_text('sem processo e sem capítulos', encoding='utf-8')
    _, _, erros, _ = pi.validar_markdown(md)
    check(len(erros) == 2, 'entrada sem processo/seções é bloqueada')

print("T2 — DOCX é convertido e o original permanece intacto")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    origem = inbox / 'laudo.docx'
    origem.write_bytes(b'original')

    def fake_converter(_origem, destino, _pandoc):
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(VALIDO, encoding='utf-8')

    with patch.object(pi.shutil, 'which', return_value='/fake/pandoc'), \
            patch.object(pi, 'converter', fake_converter):
        check(pi.preparar(inbox) == 0, 'DOCX convertido e validado')
        check(pi.preparar(inbox) == 0, 'segunda execução permanece segura (idempotente)')
    check(origem.read_bytes() == b'original', 'DOCX original permanece intacto')

print("T3 — Pandoc ausente bloqueia com orientação de instalação")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    (inbox / 'laudo.docx').write_bytes(b'original')
    saida_err = StringIO()
    with patch.object(pi.shutil, 'which', return_value=None), redirect_stderr(saida_err):
        rc = pi.preparar(inbox)
    check(rc == 2 and 'winget install' in saida_err.getvalue(),
          'Pandoc ausente bloqueia e orienta Windows')

print("T4 — duplicado intra-lote é sinalizado sem bloquear")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    (inbox / 'a.md').write_text(VALIDO, encoding='utf-8')
    (inbox / 'b.md').write_text(VALIDO, encoding='utf-8')
    saida = StringIO()
    with redirect_stdout(saida):
        rc = pi.preparar(inbox)
    check(rc == 0 and 'AVISO DUPLICADO' in saida.getvalue(), 'processo duplicado é sinalizado')

print("T5 — dois processos no mesmo arquivo bloqueiam (laudos colados)")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    (inbox / 'colado.md').write_text(VALIDO + f'\nProcesso: {CNJ2}\n', encoding='utf-8')
    saida, saida_err = StringIO(), StringIO()
    with redirect_stdout(saida), redirect_stderr(saida_err):
        rc = pi.preparar(inbox)
    check(rc == 2 and 'mais de um número de processo' in saida.getvalue(),
          'arquivo com dois processos é bloqueado')

print("T6 — inbox vazia ou inexistente não deixa passar silenciosamente")
with tempfile.TemporaryDirectory() as td:
    saida_err = StringIO()
    with redirect_stderr(saida_err):
        rc_vazia = pi.preparar(Path(td))
        rc_inexistente = pi.preparar(Path(td) / 'nao-existe')
    check(rc_vazia == 2 and rc_inexistente == 2, 'inbox vazia e inexistente retornam 2')

print("T7 — memorando do perito (prefixo _) é ignorado, não bloqueia o lote")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    (inbox / '_LAUDOS-QUE-FALTAM-pedir-ao-irineu.md').write_text(
        '# Pendências\n- pedir laudo de calor\n', encoding='utf-8')
    (inbox / 'laudo.md').write_text(VALIDO, encoding='utf-8')
    saida = StringIO()
    with redirect_stdout(saida):
        rc = pi.preparar(inbox)
    texto = saida.getvalue()
    check(rc == 0, 'lote com memorando + laudo válido passa (rc=%s)' % rc)
    check('IGNORADO (não é laudo): _LAUDOS-QUE-FALTAM-pedir-ao-irineu.md' in texto,
          'memorando aparece como IGNORADO no relatório')
    check('INVÁLIDO' not in texto, 'memorando não vira INVÁLIDO')
    check((inbox / '_LAUDOS-QUE-FALTAM-pedir-ao-irineu.md').is_file(),
          'memorando continua na inbox (a pasta não pode ficar vazia no Drive)')

print("T8 — inbox só com memorando: bloqueia dizendo que não há laudo")
with tempfile.TemporaryDirectory() as td:
    inbox = Path(td)
    (inbox / '_LAUDOS-QUE-FALTAM-pedir-ao-irineu.md').write_text('# Pendências\n', encoding='utf-8')
    saida, saida_err = StringIO(), StringIO()
    with redirect_stdout(saida), redirect_stderr(saida_err):
        rc = pi.preparar(inbox)
    check(rc == 2 and 'só arquivos ignorados' in saida_err.getvalue(),
          'sem laudo real, bloqueia com mensagem específica')

print()
if FALHAS:
    print('✗ %d verificação(ões) falharam' % len(FALHAS))
    sys.exit(1)
print('OK — testes do preparador da inbox passaram')
