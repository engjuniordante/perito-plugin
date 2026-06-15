#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_epi.py — guarda determinístico da classificação de EPI no formulário de campo.

O C.A. é a CHAVE PRIMÁRIA; o nome comercial NUNCA classifica. Edita o próprio .md:

  1) LOOKUP por C.A. (prioridade):
     a. CA-dicionario.json (override curado do perito) — vence tudo.
     b. caepi.sqlite (base OFICIAL do MTE) — agente/anexo derivado da fonte.
     Achou → reescreve o agente da linha, IGNORANDO o nome do produto.
  2) REGRA ABSOLUTA (C.A. fora de a/b): creme/pomada = Químico dérmico (An.13).
     Exceção: "protetor solar" (não é EPI — NT 146/2015 §4).
  3) CA VENCIDO (NT 146/2015): em linhas da ficha com DATA + C.A., compara a data da
     ENTREGA com a VALIDADE do C.A. (caepi). entrega > validade → 🚩 (indício de
     aquisição sem CA válido; o perito decide). CA vencido HOJE é irrelevante.
  4) MARCA 🚩 o que só o C.A. resolve e lista 📇 C.A. não catalogados.
  5) Avisa se o índice CAEPI tiver > 90 dias (re-baixar do MTE).

Lookup no script (não na prosa) = à prova do modelo contornar. sqlite3/stdlib, zero pip.

uso: python3 check_epi.py <form.md> [<caepi.sqlite>] [<CA-dicionario.json>] [<base_dir>]
  (qualquer ordem; um diretório resolve <dir>/04-EPIs/caepi.sqlite e .../CA-dicionario.json)
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

MARK = '## 🚩 VERIFICAÇÃO AUTOMÁTICA DE EPI'

RAD = ('radiaç', 'radiac', 'rni', 'não ioniz', 'nao ioniz', 'ultraviolet',
       'luz negra', 'an.7', 'an. 7', 'anexo 7', 'anexo nº 7', 'anexo n 7')
QUIM = ('quím', 'quim', 'an.13', 'an. 13', 'anexo 13', 'anexo nº 13', 'dérm',
        'derm', 'óleo', 'oleo', 'graxa', 'álcali', 'alcali', 'solvente')
UMID = ('umidade', 'an.10', 'an. 10', 'anexo 10')
MASK = ('máscara', 'mascara', 'lente', 'viseira', 'escudo', 'facial',
        'solda', 'soldad', 'capuz')
AN13 = 'Químico dérmico (An.13)'
CA_NUM_RE = re.compile(r'c\.?\s?a\.?[\s:nº.\-]*(\d{1,6})', re.I)
DATE_RE = re.compile(r'\b(\d{2})/(\d{2})/(\d{4})\b')
# Linha da FICHA começa com a data (após bullet): "- 25/02/2023 · …". O 1º campo
# DEVE começar com a data — exclui linhas do EPI — RESUMO que citam C.A./data
# embutidos (ex.: "— Umidade An.10: capa [CA 28449, 14/08/2024] · …").
ROW_START_RE = re.compile(r'^[\s\-–—•·*]*\d{2}/\d{2}/\d{4}')
# Descrição da ficha NUNCA pode ser o agente/anexo (ex.: "Químico dérmico (An.13)").
# A descrição é o NOME DO PRODUTO, literal. Se a descrição traz "(An.N)", foi renomeada.
AGENTE_NA_DESC_RE = re.compile(r'\(\s*an\.?\s*\d', re.I)


# ---------------- fontes de classificação por C.A. ----------------
def load_dict(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return {}
    out = {}
    for k, v in raw.items():
        if str(k).startswith('_'):
            continue
        key = re.sub(r'\D', '', str(k))
        if key:
            out[key] = v
    return out


class Caepi:
    def __init__(self, path):
        self.con = None
        self.build_date = None
        self.has_vu = False  # coluna vida_util_meses existe na base?
        if path and os.path.exists(path):
            try:
                self.con = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
                row = self.con.execute("SELECT v FROM meta WHERE k='build_date'").fetchone()
                self.build_date = row[0] if row else None
                cols = [r[1] for r in self.con.execute('PRAGMA table_info(ca)').fetchall()]
                self.has_vu = 'vida_util_meses' in cols
            except Exception:
                self.con = None

    def get(self, ca):
        if not self.con:
            return None
        sel = 'agente, validade_iso, validade_br, situacao, equipamento'
        if self.has_vu:
            sel += ', vida_util_meses'
        try:
            r = self.con.execute('SELECT %s FROM ca WHERE ca=?' % sel, (ca,)).fetchone()
        except Exception:
            return None
        if not r:
            return None
        d = {'agente': r[0], 'validade_iso': r[1], 'validade_br': r[2], 'situacao': r[3],
             'equipamento': r[4]}
        if self.has_vu:
            d['vida_util_meses'] = r[5]
        return d

    def age_days(self):
        if not self.build_date:
            return None
        try:
            return (date.today() - date.fromisoformat(self.build_date)).days
        except Exception:
            return None


def extract_ca(line):
    m = CA_NUM_RE.search(line)
    return m.group(1) if m else None


def first_date_iso(line):
    m = DATE_RE.search(line)
    if not m:
        return None, None
    d, mo, y = m.groups()
    try:
        return date(int(y), int(mo), int(d)).isoformat(), '%s/%s/%s' % (d, mo, y)
    except ValueError:
        return None, None


def is_epi_line(ll, raw):
    if 'creme' in ll or 'pomada' in ll or 'capa' in ll:
        return True
    if CA_NUM_RE.search(raw):
        return True
    return False


def process(lines, cadict, caepi):
    new_lines, fixes, flags = [], [], []
    nao_cat = []
    for raw in lines:
        new_lines.append(raw)            # a linha NUNCA é modificada
        # processa SÓ as linhas da TABELA de fornecimento (Data · Qtd · Descrição · C.A.).
        # Ignora EPI-RESUMO, observações e flags (citam C.A./agente legitimamente).
        _parts = [p.strip() for p in raw.split(' · ')]
        if not (len(_parts) >= 3 and ROW_START_RE.match(_parts[0])):
            continue
        ll = raw.lower()
        trecho = raw.strip()[:120]
        ca = extract_ca(raw)
        # ⛔ Descrição renomeada para o AGENTE — proibido (vaza pro laudo; o perito lê a ficha).
        if AGENTE_NA_DESC_RE.search(_parts[-2]):
            flags.append((trecho, 'DESCRIÇÃO DA FICHA SUBSTITUÍDA PELO AGENTE — restaure o NOME DO PRODUTO (literal da ficha). O agente vai só nesta verificação 🔧, NUNCA na coluna Descrição.'))
        agente = src = hit = None
        known = False  # C.A. existe no dicionário OU na base CAEPI (mesmo sem agente NR-15)
        classified = False

        # (1) LOOKUP por C.A. — override curado vence; depois CAEPI oficial
        if ca:
            if ca in cadict:
                agente, src, known = cadict[ca].get('agente'), 'dicionário', True
            else:
                hit = caepi.get(ca)
                if hit is not None:
                    known = True
                    if hit.get('agente'):
                        agente, src = hit['agente'], 'CAEPI'
        if agente:
            # SÓ reporta no bloco 🔧 — NUNCA reescreve a linha (a Descrição da ficha é intocável).
            fixes.append((trecho, 'C.A. %s → %s [%s]' % (ca, agente, src)))
            classified = True

        # C.A. conhecido na base SEM agente NR-15 (botina, óculos, luva mecânica…) =
        # não-neutralizador → silêncio: NÃO é "não catalogado", NÃO aplica heurística.
        elif not known:
            # (2) C.A. desconhecido (nem dicionário nem CAEPI): regra absoluta + flags
            has_rad = any(t in ll for t in RAD)
            has_quim = any(t in ll for t in QUIM)
            is_creme = 'creme' in ll or 'pomada' in ll
            is_solar = 'solar' in ll
            if is_creme and not is_solar and (has_rad or not has_quim):
                fixes.append((trecho, 'creme/pomada → %s [regra absoluta]' % AN13))
                agente = AN13
                classified = True
            has_umid = any(t in ll for t in UMID)
            is_mask = any(t in ll for t in MASK)
            is_capa = 'capa' in ll or 'impermeáv' in ll or 'impermeav' in ll
            if has_rad and not is_mask and not is_creme and not is_solar and not classified:
                flags.append((trecho, 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — confira o C.A.'))
            if is_capa and has_quim and not has_umid and not classified:
                flags.append((trecho, 'capa/impermeável como químico — protege UMIDADE (An.10). Confirme.'))
            if ca:
                nao_cat.append(ca)

        # (3) CA VENCIDO na ENTREGA (NT 146/2015) — só p/ EPI que neutraliza (tem agente)
        if ca and agente:
            di, dbr = first_date_iso(raw)
            if di:
                h = hit if hit is not None else caepi.get(ca)
                if h and h.get('validade_iso') and di > h['validade_iso']:
                    flags.append((trecho, 'EPI entregue em %s com C.A. %s VENCIDO em %s — indício de aquisição sem CA válido (NT 146/2015). Confirmar.'
                                  % (dbr, ca, h['validade_br'])))

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    return new_lines, dedup(fixes), dedup(flags), dedup(nao_cat)


# ---------- cobertura (item 6.1.1 NR-6): qtd × vida útil — determinística ----------
# Calcula a soma de meses cobertos por agente, para os EPI cuja vida útil é regra estável:
#   - creme/pomada: 1 unidade ≈ 1 mês (universal).
#   - protetor auditivo: vida útil POR C.A. (boletim) — lida do CA-dicionario.json
#     (campo "vida_util_meses"). Sem o campo → não calcula esse item (lista em ⓘ).
# Luva/conjuntos/demais = empírico → o perito decide (não entram no cálculo).
# Sai como SUGESTÃO: o perito confronta com os meses do imprescrito (menos afastamentos).
QTY_RE = re.compile(r'(\d+)')
# vida útil por TIPO de protetor auditivo (meses); o dado curado por C.A. (dicionário/CAEPI)
# sobrepõe sempre. Fallback p/ quando o C.A. não traz vida_util_meses — sem isto o cálculo de
# ruído nunca aparece para C.A. não-catalogado (queixa real).
TYPE_VU = [
    (('espuma', 'descart', 'moldáv', 'moldav'), round(1 / 21, 3), 'espuma 1 dia útil'),
    (('concha', 'abafador', 'circum'), 12.0, 'concha 12m'),
    (('plug', 'plugue', 'silicone', 'inser', 'tampão', 'tampao', 'pré-mold', 'pre-mold'), 6.0, 'plug 6m'),
]


def _vida_util(ca, desc_l, cadict, caepi=None):
    if 'creme' in desc_l or 'pomada' in desc_l:
        return 1, 'creme 1/mês'
    # vida útil CURADA primeiro: dicionário, senão coluna da base CAEPI.
    v = None
    if ca and ca in cadict:
        v = cadict[ca].get('vida_util_meses')
    if v is None and ca and caepi is not None:
        hit = caepi.get(ca)
        if hit:
            v = hit.get('vida_util_meses')
    if v:
        try:
            return float(v), 'C.A. %s' % ca  # float: aceita espuma (1 dia útil ≈ 0,05 mês)
        except (TypeError, ValueError):
            return None, None
    # fallback por TIPO (plug 6m · concha 12m · espuma 1 dia útil) — o C.A. não traz vida útil
    for kws, vu, label in TYPE_VU:
        if any(k in desc_l for k in kws):
            return vu, label
    return None, None


def _is_protetor_aud(desc_l):
    return (('protet' in desc_l or 'auric' in desc_l or 'auditiv' in desc_l)
            and 'solar' not in desc_l)


def _agent_of(ca, cadict, caepi):
    """Agente classificado pelo C.A. (dicionário → CAEPI). Mesma ordem do process()."""
    if ca and ca in cadict and cadict[ca].get('agente'):
        return cadict[ca]['agente']
    if ca and caepi is not None:
        hit = caepi.get(ca)
        if hit and hit.get('agente'):
            return hit['agente']
    return None


IMPRESCRITO_RE = re.compile(r'per[ií]odo imprescrito.*?(\d{2}/\d{2}/\d{4}).*?(\d{2}/\d{2}/\d{4})', re.I)
# EPI de admissão é entregue 0–poucos dias ANTES do início do imprescrito (= início do
# pacto, quando o contrato é recente e cabe inteiro na prescrição). Essa janela resgata
# a entrega de admissão sem readmitir histórico de função/período anterior — que, quando
# a prescrição corta o meio do contrato, fica MESES/ANOS antes de impr_a, fora da janela.
IMPRESC_GRACE_DAYS = 31


def _imprescrito_range(text):
    """Início/fim do imprescrito a partir do campo 'Período imprescrito' do formulário (ISO).
    Recorta a cobertura pela DATA — não depende do modelo marcar a divisória ▼.
    O início vem recuado IMPRESC_GRACE_DAYS para abarcar o EPI de admissão (véspera do pacto)."""
    m = IMPRESCRITO_RE.search(text)
    if not m:
        return None, None
    ini = first_date_iso(m.group(1))[0]
    if ini:
        try:
            ini = (date.fromisoformat(ini) - timedelta(days=IMPRESC_GRACE_DAYS)).isoformat()
        except ValueError:
            pass
    return ini, first_date_iso(m.group(2))[0]


def cobertura(lines, cadict, caepi=None):
    """Σ(qtd × vida útil) por agente, SÓ nas entregas do imprescrito. Recorte por DATA
    (campo 'Período imprescrito'); fallback divisória ▼/▲; fallback ficha inteira. Classifica
    pelo AGENTE do C.A. (não pelo texto da descrição, que pode ter sido renomeado):
      - Ruído (An.1) → protetor auditivo → vida útil por C.A. (dicionário/CAEPI).
      - Creme/pomada (desc OU equipamento do CAEPI) → An.13, 1 mês/unidade.
    Luva/conjunto/demais = perito. Retorna (resultados, faltou_vu, tem_divisoria)."""
    impr_a, impr_b = _imprescrito_range('\n'.join(lines))
    tem_divisoria = any('▼' in l for l in lines)
    use_date = impr_a is not None          # preferível: recorta pela DATA do imprescrito
    in_impr = use_date or (not tem_divisoria)
    buckets, faltou_vu = {}, []
    for raw in lines:
        if not use_date:
            if '▼' in raw:
                in_impr = True
                continue
            if '▲' in raw:                  # fim do imprescrito → parar de contar
                in_impr = False
                continue
        if not in_impr:
            continue
        ll = raw.lower()
        parts = [p.strip() for p in raw.split(' · ')]
        # só linhas da TABELA de fornecimento (Data · Qtd · Descrição · C.A.) — o date-gate
        # já exclui cabeçalhos (#), notas (>), resumo e obs (sem data no 1º campo).
        if not (len(parts) >= 3 and ROW_START_RE.match(parts[0])):
            continue
        if use_date:                        # recorte por data: só entregas dentro do imprescrito
            di = first_date_iso(parts[0])[0]
            if di is None or di < impr_a or (impr_b and di > impr_b):
                continue
        mq = QTY_RE.search(parts[1])
        if not mq:
            continue
        qtd = int(mq.group(1))
        if qtd > 500:                       # quantidade irreal = parse errado → ignorar
            continue
        ca = extract_ca(raw)
        agente = _agent_of(ca, cadict, caepi)
        equip = ''
        if ca and caepi is not None:
            hit = caepi.get(ca)
            equip = (hit.get('equipamento') or '').lower() if hit else ''
        if 'solar' in ll and ('creme' in ll or 'pomada' in ll or 'protet' in ll):
            continue                        # protetor solar não é EPI (NT 146/2015 §4) — fora da cobertura
        is_creme = 'creme' in ll or 'pomada' in ll or 'creme' in equip or 'pomada' in equip
        if is_creme:
            bucket, vu = AN13, 1.0
        elif agente == 'Ruído (An.1)':
            bucket = 'Ruído (An.1)'
            vu, _ = _vida_util(ca, ll, cadict, caepi)
            if vu is None:
                faltou_vu.append(ca or (parts[2][:30] if len(parts) > 2 else ll[:30]))
                continue
        else:
            continue  # luva/conjunto/demais → perito decide
        b = buckets.setdefault(bucket, [0.0, 0])
        b[0] += qtd * vu
        b[1] += 1
    res = ['%s: %d entregas → ~%s meses cobertos (Σ qtd × vida útil)' % (a, n, ('%g' % round(m, 1)))
           for a, (m, n) in buckets.items()]
    return res, _dedup_simple(faltou_vu), (use_date or tem_divisoria)


def _dedup_simple(xs):
    seen, out = set(), []
    for x in xs:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out


# Fronteira de seção (próxima seção depois do EPI — RESUMO). Cobre os 2 formatos:
# markdown (## / ### / ---) e Notas do iPhone (▶ / ━━━). O bloco do guard NUNCA
# contém linhas assim → delimita com segurança onde o bloco começa/termina.
SECTION_BOUNDARY_RE = re.compile(r'^(#{2,}\s|▶\s|━{2,}|-{3,}\s*$)')


def _next_boundary(lines, start):
    for j in range(start, len(lines)):
        if SECTION_BOUNDARY_RE.match(lines[j]):
            return j
    return len(lines)


def insert_block(body, block_text):
    """Injeta o bloco logo APÓS a seção 'EPI — RESUMO' (onde o perito decide a
    neutralização), antes da próxima seção. Sem essa seção → anexa no fim (fallback)."""
    lines = body.split('\n')
    start = next((i for i, ln in enumerate(lines) if 'EPI — RESUMO' in ln), None)
    if start is None:
        return body.rstrip() + '\n\n' + block_text + '\n'
    end = _next_boundary(lines, start + 1)
    head = '\n'.join(lines[:end]).rstrip()
    tail = '\n'.join(lines[end:]).strip('\n')
    if not tail:
        return head + '\n\n' + block_text + '\n'
    return head + '\n\n' + block_text + '\n\n' + tail + '\n'


def strip_old_block(text):
    """Remove o bloco anterior ONDE ELE ESTIVER (fim OU meio do arquivo) — do MARK
    até a próxima fronteira de seção. Idempotência mesmo com o bloco injetado no meio."""
    idx = text.find(MARK)
    if idx == -1:
        return text.rstrip() + '\n'
    lines = text.split('\n')
    mstart = next((i for i, ln in enumerate(lines) if ln.startswith(MARK)), None)
    if mstart is None:
        return text[:idx].rstrip() + '\n'
    mend = _next_boundary(lines, mstart + 1)
    kept = lines[:mstart] + lines[mend:]
    return '\n'.join(kept).rstrip() + '\n'


def resolve_paths(args):
    caepi_p = dicio_p = None
    for a in args:
        if os.path.isdir(a):
            caepi_p = caepi_p or os.path.join(a, '04-EPIs', 'caepi.sqlite')
            dicio_p = dicio_p or os.path.join(a, '04-EPIs', 'CA-dicionario.json')
        elif a.endswith(('.sqlite', '.db')):
            caepi_p = a
        elif a.endswith('.json'):
            dicio_p = a
    return caepi_p, dicio_p


def main():
    if len(sys.argv) < 2:
        print('uso: python3 check_epi.py <form.md> [<caepi.sqlite>] [<CA-dicionario.json>] [<base_dir>]')
        sys.exit(1)
    path = sys.argv[1]
    caepi_p, dicio_p = resolve_paths(sys.argv[2:])
    cadict = load_dict(dicio_p)
    caepi = Caepi(caepi_p)

    with open(path, encoding='utf-8') as f:
        text = f.read()
    stripped = strip_old_block(text)          # remove bloco anterior ANTES de processar (idempotência)
    src_lines = stripped.splitlines()
    new_lines, fixes, flags, nao_cat = process(src_lines, cadict, caepi)
    cob_res, faltou_vu, scoped = cobertura(src_lines, cadict, caepi)
    body = '\n'.join(new_lines)

    age = caepi.age_days()
    stale = age is not None and age > 90

    if not fixes and not flags and not nao_cat and not stale and not cob_res and not faltou_vu:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        print('✅ check_epi: nenhuma classificação de EPI suspeita.')
        sys.exit(0)

    bloco = [MARK + ' (C.A. é a chave — fonte: CA-dicionario + base oficial CAEPI; o nome NÃO classifica)\n']
    if fixes:
        bloco.append('**🔧 Classificado pelo C.A. (referência — a Descrição da ficha NÃO é alterada; use no quadro-resumo):**')
        for trecho, msg in fixes:
            bloco.append('- `%s` → %s' % (trecho, msg))
    if flags:
        bloco.append('\n**🚩 Conferir:**')
        for trecho, msg in flags:
            bloco.append('- ⚠ `%s` → %s' % (trecho, msg))
    if nao_cat:
        bloco.append('\n**📇 C.A. NÃO CATALOGADOS** (nem no dicionário nem na base CAEPI — verificar e catalogar): ' + ', '.join(nao_cat))
    if cob_res:
        bloco.append('\n**📐 Cobertura (sugestão — só creme e protetor auditivo; confronte com os meses do imprescrito menos afastamentos, e o boletim do C.A.):**')
        for r in cob_res:
            bloco.append('- %s' % r)
        if not scoped:
            bloco.append('- ⚠ sem campo "Período imprescrito" nem divisória ▼ — cobertura sobre TODA a ficha (pode incluir histórico anterior ao imprescrito).')
    if faltou_vu:
        bloco.append('\nⓘ Vida útil não cadastrada (cobertura não calculada) p/ C.A./item: ' + ', '.join(faltou_vu)
                     + ' — cataloque `vida_util_meses` no CA-dicionario.json.')
    if stale:
        bloco.append('\n**⏰ Base CAEPI com %d dias** (build %s) — re-baixe o RelatorioCA do MTE e rode `build_caepi_index.py`.' % (age, caepi.build_date))
    new = insert_block(body, '\n'.join(bloco))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)

    for trecho, msg in fixes:
        print('🔧 %s → %s' % (trecho, msg))
    for trecho, msg in flags:
        print('🚩 %s → %s' % (trecho, msg))
    if nao_cat:
        print('📇 não catalogados: %s' % ', '.join(nao_cat))
    for r in cob_res:
        print('📐 %s' % r)
    if faltou_vu:
        print('ⓘ vida útil não cadastrada: %s' % ', '.join(faltou_vu))
    if stale:
        print('⏰ CAEPI desatualizado (%d dias)' % age)
    sys.exit(2 if flags else 0)


if __name__ == '__main__':
    main()
