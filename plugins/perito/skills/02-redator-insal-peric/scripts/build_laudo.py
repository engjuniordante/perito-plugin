# -*- coding: utf-8 -*-
"""
build_laudo.py — monta o laudo .docx do Irineu a partir de um JSON de conteúdo.
Uso:  python3 build_laudo.py <template.docx> <laudo-data.json> <saida.docx>

O MODELO (skill) produz só o JSON (dados do formulário + análises).
Este script faz toda a manipulação do .docx — determinístico, sem regex no LLM.

Estrutura do JSON:
{
  "perito_nome": "Irineu de Freitas Branco Junior",   // checagem de identidade
  "scalars":  { "VARA":..., "PROCESSO":..., "RECLAMANTE":..., ... },
  "blocks":   { "LISTA_PARTICIPANTES":[...], "ATIVIDADES_POR_FUNCAO":[...],
                "ANALISE_*":[...], "CONCLUSAO_ITENS":[...], "QUESITOS_RECLAMANTE":[...], ... },
  "identificacao": [ [Funcao,Setor,Inicio,Termino,Autuacao,ImprInicio,ImprTermino], ... ],
  "epi": { "anos": ["2023","2024","2025"], "linhas": [ [Desc,Agente,CA,v1,v2,v3], ... ] },
  "nr6": { "ficha":"SIM","ca":"SIM","treinamento":"SIM","adequado":"","frequencia":"NAO","fiscalizacao":"" },
  "vibracao": [ ["Trator de Transbordo","1,00","16,50"], ["Colhedora","0,60","7,90"] ]   // opcional
}
"""
import sys, json, re
from copy import deepcopy

# --- auto-provisionamento de dependências (sandbox efêmero do Cowork) ---
def _ensure(pkgs):
    import importlib.util, subprocess, sys as _sys
    falta = [pip for mod, pip in pkgs if importlib.util.find_spec(mod) is None]
    if falta:
        cmd = [_sys.executable, '-m', 'pip', 'install', *falta]
        if _sys.platform.startswith('linux'):
            cmd.append('--break-system-packages')
        subprocess.run(cmd, check=False)
_ensure([('docx', 'python-docx')])

import docx
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph
from docx.shared import Pt, RGBColor
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ---------------- descaracterização-padrão por agente AUSENTE ----------------
# O modelo só emite os ANALISE_* dos agentes PRESENTES; este mapa preenche
# automaticamente os AUSENTES com a redação verbatim do Irineu (extraída dos
# laudos dele). Cada valor é a lista de parágrafos do bloco.
# ⚠ 4 entradas (RUIDO_CONTINUO, VIBRACOES, QUIM_QUALITATIVOS, PERIC_INFLAMAVEIS)
# foram derivadas do padrão (são quase sempre PRESENTES, raramente caem aqui).
_INSAL = 'Descaracterizada a insalubridade.'
_PERIC = 'Descaracterizada a periculosidade.'
_NC = 'Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a %s nos termos do Anexo nº %s da NR-%s.'
ABSENT_ANALISE = {
    # NR-15
    'ANALISE_RUIDO_CONTINUO':   [_NC % ('ruído contínuo ou intermitente', '1', '15'), _INSAL],
    'ANALISE_RUIDO_IMPACTO':    [_NC % ('ruído de impacto', '2', '15'), _INSAL],
    'ANALISE_CALOR':            ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição ao agente calor nos termos do Anexo nº 3 da NR-15.', _INSAL],
    'ANALISE_BAIXO_ILUMINAMENTO': ['O Anexo nº 4 da NR-15 (Iluminamento) foi revogado pela Portaria nº 3.751, de 23/11/1990, não sendo, portanto, objeto de análise no presente laudo.'],
    'ANALISE_RAD_IONIZANTES':   [_NC % ('radiações ionizantes', '5', '15'), _INSAL],
    'ANALISE_HIPERBARICAS':     ['Não foi constatado, nas atividades exercidas pelo(a) Reclamante, trabalho sob condições hiperbáricas nos termos do Anexo nº 6 da NR-15.', _INSAL],
    'ANALISE_RAD_NAO_IONIZANTES': ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a radiações não ionizantes em condições que se enquadrem no Anexo nº 7 da NR-15.', _INSAL],
    'ANALISE_VIBRACOES':        [_NC % ('vibrações', '8', '15'), _INSAL],
    'ANALISE_FRIO':             ['Não aplicável às atividades exercidas pelo(a) Reclamante, nos termos do Anexo nº 9 da NR-15.', _INSAL],
    'ANALISE_UMIDADE':          ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a condições de umidade que se enquadrem no Anexo nº 10 da NR-15.', _INSAL],
    'ANALISE_QUIM_QUANTITATIVOS': ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a agentes químicos sujeitos a avaliação quantitativa nos termos do Anexo nº 11 da NR-15.', _INSAL],
    'ANALISE_POEIRAS_MINERAIS': [_NC % ('poeiras minerais', '12', '15'), _INSAL],
    'ANALISE_QUIM_QUALITATIVOS': ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a agentes químicos sujeitos a avaliação qualitativa nos termos do Anexo nº 13 da NR-15.', _INSAL],
    'ANALISE_BENZENO':          ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a benzeno nos termos do Anexo nº 13-A da NR-15.', _INSAL],
    'ANALISE_AGENTES_BIOLOGICOS': [_NC % ('agentes biológicos', '14', '15'), _INSAL],
    # NR-16
    'ANALISE_PERIC_EXPLOSIVOS': [_NC % ('explosivos', '1', '16'), _PERIC],
    'ANALISE_PERIC_INFLAMAVEIS': [_NC % ('inflamáveis', '2', '16'), _PERIC],
    'ANALISE_PERIC_ROUBOS':     ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a situações de roubo ou outras espécies de violência física nos termos do Anexo nº 3 da NR-16.', _PERIC],
    'ANALISE_PERIC_ELETRICIDADE': ['Não foi constatado, nas atividades exercidas pelo(a) Reclamante, contato com instalações ou equipamentos elétricos energizados em condições que se enquadrem no Anexo nº 4 da NR-16.', _PERIC],
    'ANALISE_PERIC_MOTOCICLETA': ['Não foi constatado, nas atividades exercidas pelo(a) Reclamante, uso de motocicleta para o exercício do trabalho nos termos do Anexo nº 5 da NR-16.', _PERIC],
    'ANALISE_PERIC_RADIACOES':  ['Não foi constatada, nas atividades exercidas pelo(a) Reclamante, exposição a radiações ionizantes em condições de periculosidade nos termos da NR-16.', _PERIC],
}

# ---------------- helpers de parágrafo ----------------
def all_paragraphs(document):
    out = []
    def rec(tbls):
        for t in tbls:
            for row in t.rows:
                for cell in row.cells:
                    out.extend(cell.paragraphs); rec(cell.tables)
    out.extend(document.paragraphs); rec(document.tables)
    for sec in document.sections:
        out.extend(sec.header.paragraphs); out.extend(sec.footer.paragraphs)
    return out

def replace_scalar(document, mapping):
    for p in all_paragraphs(document):
        for run in p.runs:
            if '{{' in run.text:
                t = run.text
                for k, v in mapping.items():
                    if k in t:
                        t = t.replace(k, v)
                run.text = t

def set_block(p, lines):
    rpr = None
    if p.runs:
        el = p.runs[0]._r.find(qn('w:rPr'))
        if el is not None:
            rpr = deepcopy(el)
            u = rpr.find(qn('w:u'))            # conteúdo de corpo nunca sublinhado
            if u is not None: rpr.remove(u)
    for r in list(p.runs):
        r._r.getparent().remove(r._r)
    def add_line(par, text):
        run = par.add_run(text)
        if rpr is not None:
            ex = run._r.find(qn('w:rPr'))
            if ex is not None: run._r.remove(ex)
            run._r.insert(0, deepcopy(rpr))
    if not lines: lines = ['']
    add_line(p, lines[0]); anchor = p
    for line in lines[1:]:
        new_p = deepcopy(p._p)
        for r in new_p.findall(qn('w:r')): new_p.remove(r)
        anchor._p.addnext(new_p)
        np = Paragraph(new_p, p._parent); add_line(np, line); anchor = np

def replace_blocks(document, blocks):
    for marker, lines in blocks.items():
        mk = '{{%s}}' % marker if not marker.startswith('{{') else marker
        for p in [p for p in all_paragraphs(document) if mk in p.text]:
            set_block(p, lines)

def fill_absent_analises(document):
    """Qualquer {{ANALISE_*}} que o modelo NÃO enviou (agente ausente) recebe a
    descaracterização-padrão por agente. Devolve a lista de marcadores preenchidos."""
    filled = []
    for p in all_paragraphs(document):
        m = re.search(r'\{\{(ANALISE_[A-Z0-9_]+)\}\}', p.text)
        if m and m.group(1) in ABSENT_ANALISE:
            set_block(p, ABSENT_ANALISE[m.group(1)])
            filled.append(m.group(1))
    return filled

def set_cell_text(cell, text, bold=None):
    p = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r._r.getparent().remove(r._r)
    else:
        p.add_run(text)
    if bold is not None:
        for r in p.runs: r.bold = bold

# ---------------- localizar tabelas por conteúdo ----------------
def find_table(doc, needle):
    for t in doc.tables:
        for r in t.rows:
            for c in r.cells:
                if needle in c.text:
                    return t
    return None

# ---------------- main ----------------
def build(template_path, data_path, out_path):
    data = json.load(open(data_path, encoding='utf-8'))
    doc = docx.Document(template_path)
    warnings = []

    # blocos (multi-parágrafo) primeiro, depois escalares
    replace_blocks(doc, data.get('blocks', {}))
    # agentes AUSENTES que o modelo não enviou -> descaracterização-padrão automática
    auto = fill_absent_analises(doc)
    if auto:
        print('Agentes ausentes preenchidos pelo script (%d): %s' % (len(auto), ', '.join(a.replace('ANALISE_', '') for a in auto)))

    scalars = dict(data.get('scalars', {}))
    # anos do EPI no cabeçalho
    anos = data.get('epi', {}).get('anos', [])
    for i in range(3):
        scalars['{{EPI_ANO_%d}}' % (i+1)] = anos[i] if i < len(anos) else ''
    # legendas de foto são sempre manuais -> limpar marcador
    for i in range(1, 11):
        scalars.setdefault('{{LEGENDA_FOTO_%d}}' % i, '')
    # normalizar chaves para {{...}}
    scalars = {(k if k.startswith('{{') else '{{%s}}' % k): v for k, v in scalars.items()}
    replace_scalar(doc, scalars)

    # tabela de identificação
    t0 = find_table(doc, '{{FUNCAO}}')
    if t0 is not None and data.get('identificacao'):
        tmpl = t0.rows[-1]._tr
        for row_vals in data['identificacao']:
            new_tr = deepcopy(tmpl); t0._tbl.append(new_tr)
            row = t0.rows[-1]
            for ci, val in enumerate(row_vals[:len(row.cells)]):
                set_cell_text(row.cells[ci], str(val), bold=False)
        t0._tbl.remove(tmpl)

    # tabela de EPI (resumo por agente) — tolerante: cada linha preenche TODAS as células
    # (desc, agente, ca, v1, v2, v3); campo faltante -> '' (nunca deixa {{EPI_*}} residual).
    t2 = find_table(doc, '{{EPI_DESC}}')
    if t2 is not None:
        tmpl = t2.rows[-1]._tr
        for row_vals in (data.get('epi', {}).get('linhas') or []):
            new_tr = deepcopy(tmpl); t2._tbl.append(new_tr)
            row = t2.rows[-1]
            for ci in range(len(row.cells)):
                val = row_vals[ci] if ci < len(row_vals) else ''
                set_cell_text(row.cells[ci], str(val))
        t2._tbl.remove(tmpl)   # remove a linha-modelo (some os {{EPI_*}} mesmo sem dados)

    # NR-6
    t3 = find_table(doc, 'NR-6 EQUIPAMENTO')
    if t3 is not None and data.get('nr6'):
        rowmap = {'ficha':3,'ca':4,'treinamento':5,'adequado':6,'frequencia':7,'fiscalizacao':8}
        for key, ri in rowmap.items():
            v = (data['nr6'].get(key) or '').strip().upper()
            col = 1 if v == 'SIM' else (2 if v in ('NAO','NÃO') else None)
            if col is not None and ri < len(t3.rows):
                set_cell_text(t3.rows[ri].cells[col], 'X')

    # tabela de vibração (substitui @@TABELA_VIBRACAO@@)
    if data.get('vibracao'):
        build_vibracao_table(doc, data['vibracao'])

    # ---- validações ----
    full = '\n'.join(p.text for p in all_paragraphs(doc))
    residual = sorted(set(re.findall(r'\{\{[^}]+\}\}', full)))
    if residual:
        warnings.append('MARCADORES RESIDUAIS: ' + ', '.join(residual))
    perito = data.get('perito_nome', 'Irineu de Freitas Branco Junior')
    if perito not in full:
        warnings.append('IDENTIDADE: nome do perito (%s) não encontrado no documento' % perito)
    for bad in list(data.get('nomes_proibidos', [])) + ['@@TABELA']:
        if bad in full:
            warnings.append('VAZAMENTO: "%s" presente no documento' % bad)

    # guard determinístico: classificação de EPI por agente (não confia na prosa)
    epi_flags = epi_classification_flags(data.get('epi', {}).get('linhas') or [])

    doc.save(out_path)

    # --- relatório autossuficiente: tudo que dispensa reabrir o .docx ---
    n_paras = len([p for p in all_paragraphs(doc) if p.text.strip()])
    n_tbls = len(doc.tables)
    ident_rows = len(data.get('identificacao', []) or [])
    epi_rows = len(data.get('epi', {}).get('linhas', []) or [])
    vib_rows = len(data.get('vibracao', []) or [])
    print('OK ->', out_path)
    print('CONTEÚDO: %d parágrafos não-vazios | %d tabelas (identificação=%d linhas, EPI=%d linhas, vibração=%d linhas)'
          % (n_paras, n_tbls, ident_rows, epi_rows, vib_rows))
    if auto:
        print('Agentes AUSENTES preenchidos pelo script: %d/%d' % (len(auto), 21))
    if warnings:
        print('\n⚠ AVISOS (corrija o JSON e rode de novo):')
        for w in warnings: print('  -', w)
    if epi_flags:
        print('\n🚩 EPI — CONFERIR CLASSIFICAÇÃO PELO C.A. (classificação por nome comercial é proibida):')
        for trecho, msg in epi_flags:
            print('  - %s → %s' % (trecho, msg))
    if not warnings and not epi_flags:
        print('✅ VALIDAÇÃO OK: sem marcador residual, identidade do perito presente, sem vazamento.')
        print('✅ DOCUMENTO COMPLETO E VÁLIDO — verificação encerrada. NÃO reabra/dumpe o .docx: ele é render determinístico do JSON já conferido.')
    elif not warnings and epi_flags:
        print('\n⚠ DOCUMENTO GERADO, mas há classificação(ões) de EPI a confirmar pelo C.A. acima — revise ANTES de assinar.')
    return not warnings

def build_vibracao_table(doc, linhas):
    ph = None
    for p in doc.paragraphs:
        if '@@TABELA_VIBRACAO@@' in p.text:
            ph = p; break
    if ph is None:
        return
    header = ('Equipamento', 'AREN\nLT = 1,1 m/s²', 'VDVR\nLT = 21,0')
    rows = [header] + [tuple(r) for r in linhas]
    tbl = doc.add_table(rows=len(rows), cols=3)
    tbl.style = doc.styles['Table Grid']
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for ri, rowvals in enumerate(rows):
        for ci, val in enumerate(rowvals):
            cell = tbl.rows[ri].cells[ci]
            para = cell.paragraphs[0]; para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for li, line in enumerate(str(val).split('\n')):
                run = para.add_run(line); run.font.name = 'Arial'; run.font.size = Pt(10.5)
                if ri == 0:
                    run.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                if li < len(str(val).split('\n')) - 1:
                    run.add_break()
            if ri == 0:
                tcPr = cell._tc.find(qn('w:tcPr'))
                if tcPr is None:
                    tcPr = OxmlElement('w:tcPr'); cell._tc.insert(0, tcPr)
                shd = OxmlElement('w:shd'); shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto'); shd.set(qn('w:fill'), '4472C4')
                tcPr.append(shd)
    ph._p.addprevious(tbl._tbl)
    ph._p.getparent().remove(ph._p)

# ---------------- guard de classificação de EPI por agente ----------------
# Mesma regra dura do extrator (check_epi.py): a falha perigosa é classificar o
# EPI pelo NOME COMERCIAL (creme "Luz Negra" -> UV/An.7), tirando-o do An.13.
_EPI_RAD = ('radiaç', 'radiac', 'rni', 'não ioniz', 'nao ioniz', 'ultraviolet',
            'luz negra', 'an.7', 'an. 7', 'anexo 7')
_EPI_QUIM = ('quím', 'quim', 'an.13', 'an. 13', 'anexo 13', 'dérm', 'derm',
             'óleo', 'oleo', 'graxa', 'álcali', 'alcali', 'solvente')
_EPI_UMID = ('umidade', 'an.10', 'an. 10', 'anexo 10')
_EPI_MASK = ('máscara', 'mascara', 'lente', 'viseira', 'escudo', 'facial',
             'solda', 'soldad', 'capuz')

def epi_classification_flags(linhas):
    """linhas = [[desc, agente, ca, ...], ...]. Devolve [(trecho, msg)]."""
    flags = []
    for row in linhas:
        desc = str(row[0]).lower() if len(row) > 0 else ''
        ag = str(row[1]).lower() if len(row) > 1 else ''
        trecho = ('%s · %s' % (str(row[0]) if len(row) > 0 else '',
                               str(row[1]) if len(row) > 1 else '')).strip(' ·')[:120]
        has_rad = any(t in ag for t in _EPI_RAD)
        has_quim = any(t in ag for t in _EPI_QUIM)
        has_umid = any(t in ag for t in _EPI_UMID)
        is_creme = 'creme' in desc or 'pomada' in desc
        is_capa = 'capa' in desc or 'impermeáv' in desc or 'impermeav' in desc
        is_mask = any(t in desc for t in _EPI_MASK)
        if is_creme and has_rad:
            flags.append((trecho, 'creme/pomada em radiação/UV — creme protetor é QUÍMICO DÉRMICO (An.13), nunca An.7. Confira o C.A.'))
        elif is_creme and not has_quim:
            flags.append((trecho, 'creme/pomada sem classificação química — creme protetor é An.13. Confirme pelo C.A.'))
        elif has_rad and not is_mask:
            flags.append((trecho, 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — nome comercial ≠ agente. Confira o C.A.'))
        if is_capa and has_quim and not has_umid:
            flags.append((trecho, 'capa/impermeável como químico — vestimenta impermeável protege UMIDADE (An.10). Confirme.'))
    seen, out = set(), []
    for f in flags:
        if f not in seen:
            seen.add(f); out.append(f)
    return out

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print('uso: python3 build_laudo.py <template.docx> <laudo-data.json> <saida.docx>'); sys.exit(1)
    ok = build(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if ok else 2)
