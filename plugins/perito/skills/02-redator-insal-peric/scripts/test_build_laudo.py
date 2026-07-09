#!/usr/bin/env python3
"""Regressão do redator insal/peric (build_laudo.py).
Trava os fixes v1.0.66: ntpath.basename (path do Drive Windows) e str() no replace_scalar."""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docx
import build_laudo as bl

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def t_resolve_windows():
    print("T1 — _resolve_template com path do Drive Windows cai no BUNDLED")
    win = r'G:\Meu Drive\pericias\template-insalubridade.docx'
    r = bl._resolve_template(win)
    check(os.path.isfile(r), 'resolveu para arquivo existente')
    check(os.path.basename(r) == 'template-insalubridade.docx', 'basename correto (ntpath isolou o nome)')

    posix = '/caminho/inexistente/template-periculosidade.docx'
    r2 = bl._resolve_template(posix)
    check(os.path.basename(r2) == 'template-periculosidade.docx', 'path POSIX inexistente tambem cai no bundled')

    try:
        bl._resolve_template(r'G:\x\template-que-nao-existe.docx')
        check(False, 'basename inexistente deveria abortar (SystemExit)')
    except SystemExit:
        check(True, 'basename inexistente aborta — nao substitui por outro template')


def t_gate_tipo_windows():
    print("T2 — _gate_tipo aceita basename de path Windows (fix da linha 107)")
    doc = docx.Document(os.path.join(bl._BUNDLED_TEMPLATES, 'template-insalubridade.docx'))
    win = r'G:\Meu Drive\pericias\template-insalubridade.docx'
    errs, _tipo, _intent = bl._gate_tipo(doc, win, 'insalubridade')
    tipo_errs = [e for e in errs if 'TEMPLATE PEDIDO' in e]
    check(not tipo_errs, 'sem falso "TIPO x TEMPLATE PEDIDO" (ntpath.basename == template esperado)')


def t_replace_scalar_nao_str():
    print("T3 — replace_scalar coage valor nao-str sem crash (bug 1)")
    d = docx.Document()
    p = d.add_paragraph('{{EPI_ANO_1}}')
    try:
        bl.replace_scalar(d, {'{{EPI_ANO_1}}': 2021})  # int, como o JSON pode emitir
        crashed = False
    except TypeError:
        crashed = True
    check(not crashed, 'nao crasha com int no mapping')
    check('2021' in p.text and '{{EPI_ANO_1}}' not in p.text, 'substituiu pelo str do numero')


FORM = """## ▶ EPIs FORNECIDOS

### NR-6 — Comprovação
- Ficha de EPI — registro do fornecimento 🔄 — [X] Sim  [ ] Não
- Anotação do respectivo C.A. 🔄 — [ ] Sim  [X] Não
- Treinamento e orientação 🔄 — [X] Sim  [ ] Não
- Frequência regular de fornecimento 🔄 — [X] Sim  [ ] Não
- Adequado ao risco ambiental 👤 (perito) — [ ] Sim  [ ] Não
- Fiscalização do uso 👤 (perito) — [ ] Sim  [ ] Não

## ▶ AGENTES — INSALUBRIDADE (NR-15)

### A. RUÍDO (Anexos 1 e 2)
- Status: [ ] Ausente  [X] Presente
- Nível medido (dB): 97,0
- Neutralizado pelo EPI: [X] Sim  [ ] Não

### H. FRIO (Anexo 9)
- Status: [X] Ausente  [ ] Presente
"""


def t_parsers_formulario():
    print("T4 — parsing do formulário (checkbox do perito)")
    check(bl.neutralizacao_por_agente(FORM) == {'ANALISE_RUIDO_CONTINUO': 'SIM',
                                                'ANALISE_RUIDO_IMPACTO': 'SIM'},
          'lê "Neutralizado: [X] Sim" do bloco A (os 2 marcadores de ruído)')
    check(bl.nr6_do_form(FORM) == {'ficha': 'SIM', 'ca': 'NAO', 'treinamento': 'SIM',
                                   'frequencia': 'SIM'},
          'NR-6: 4 linhas marcadas; as 2 do perito (branco) ficam fora')
    novo = FORM.replace('- Neutralizado pelo EPI: [X] Sim  [ ] Não',
                        '- Neutralizado pelo EPI durante TODO o imprescrito: [X] Sim  [ ] Não (nunca, ou só em parte)')
    check(bl.neutralizacao_por_agente(novo) == {'ANALISE_RUIDO_CONTINUO': 'SIM', 'ANALISE_RUIDO_IMPACTO': 'SIM'},
          'rótulo desambiguado (com sufixo) → mesmo resultado')
    parcial = FORM.replace('- Neutralizado pelo EPI: [X] Sim  [ ] Não',
                           '- Neutralizado pelo EPI durante TODO o imprescrito: [ ] Sim  [X] Não (nunca, ou só em parte)')
    check(bl.neutralizacao_por_agente(parcial) == {'ANALISE_RUIDO_CONTINUO': 'NAO', 'ANALISE_RUIDO_IMPACTO': 'NAO'},
          'cobertura parcial → NAO (o "Não" do rótulo não confunde o checkbox)')
    check(bl.gate_formulario({'blocks': {'ANALISE_RUIDO_CONTINUO': ['Caracterizada a insalubridade em grau médio '
                                                                   'de 01/2024 a 03/2024.']}, 'nr6': {}}, parcial) == [],
          'PARCIAL + conclusão insalubre no recorte → gate NÃO bloqueia (ressalva do Codex)')
    check(bl.caracteriza_insalubridade(['Atividades insalubres em grau médio.']), 'caracteriza: positivo')
    check(bl.caracteriza_insalubridade(['Caracterizada a insalubridade no período.']), 'caracteriza: "Caracterizada a insalubridade"')
    check(not bl.caracteriza_insalubridade(['Descaracterizada a insalubridade.']), 'não caracteriza: "Descaracterizada"')
    check(not bl.caracteriza_insalubridade(['Não foi caracterizada a insalubridade.']), 'não caracteriza: "Não foi caracterizada"')


def t_gate_formulario():
    print("T5 — gates 1.7/1.8: JSON não contraria checkbox do perito (bug do VICTOR)")
    base = {'blocks': {}, 'nr6': {'ficha': 'SIM', 'ca': 'NAO', 'treinamento': 'SIM',
                                  'frequencia': 'SIM', 'adequado': '', 'fiscalizacao': ''}}

    ok_data = dict(base, blocks={'{{ANALISE_RUIDO_CONTINUO}}': ['Descaracterizada a insalubridade.']})
    check(bl.gate_formulario(ok_data, FORM) == [], 'JSON fiel ao formulário → passa')

    # 1.7 — a inversão do run real
    inv = dict(base, blocks={'ANALISE_RUIDO_CONTINUO': [
        'Não houve treinamento comprovado.', 'Caracterizada a insalubridade em grau médio.']})
    errs = bl.gate_formulario(inv, FORM)
    check(len(errs) == 1 and 'ANALISE_RUIDO_CONTINUO' in errs[0], 'form "Neutralizado: Sim" + bloco caracteriza → erro')

    # 1.8 — as duas células que o modelo virou
    virado = dict(ok_data, nr6=dict(base['nr6'], treinamento='NAO', ca='SIM'))
    errs = bl.gate_formulario(virado, FORM)
    check(len(errs) == 2 and all('nr6[' in e for e in errs), 'JSON vira treinamento e C.A. contra o form → 2 erros')

    # linha que o perito deixou em branco: o modelo pode preencher
    branco = dict(ok_data, nr6=dict(base['nr6'], fiscalizacao='NAO'))
    check(bl.gate_formulario(branco, FORM) == [], 'linha em branco no form preenchida pelo modelo → não bloqueia')


if __name__ == '__main__':
    t_resolve_windows(); t_gate_tipo_windows(); t_replace_scalar_nao_str()
    t_parsers_formulario(); t_gate_formulario()
    print()
    if FALHAS:
        print('FALHOU (%d): %s' % (len(FALHAS), '; '.join(FALHAS))); sys.exit(1)
    print('OK — todos os testes do build_laudo passaram'); sys.exit(0)
