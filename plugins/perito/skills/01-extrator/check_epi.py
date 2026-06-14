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
from datetime import date

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
        sel = 'agente, validade_iso, validade_br, situacao'
        if self.has_vu:
            sel += ', vida_util_meses'
        try:
            r = self.con.execute('SELECT %s FROM ca WHERE ca=?' % sel, (ca,)).fetchone()
        except Exception:
            return None
        if not r:
            return None
        d = {'agente': r[0], 'validade_iso': r[1], 'validade_br': r[2], 'situacao': r[3]}
        if self.has_vu:
            d['vida_util_meses'] = r[4]
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


def set_agent_segment(line, new_agent):
    parts = line.split(' · ')
    if len(parts) < 2:
        return None
    ca_idx = None
    for i, p in enumerate(parts):
        if CA_NUM_RE.search(p):
            ca_idx = i
            break
    if ca_idx is None or ca_idx < 1:
        return None
    if ca_idx >= 2:
        parts[ca_idx - 1] = new_agent
    else:
        parts.insert(ca_idx, new_agent)
    return ' · '.join(parts)


def process(lines, cadict, caepi):
    new_lines, fixes, flags = [], [], []
    nao_cat = []
    for raw in lines:
        ll = raw.lower()
        if not is_epi_line(ll, raw):
            new_lines.append(raw)
            continue
        trecho = raw.strip()[:120]
        line = raw
        ca = extract_ca(raw)
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
            fixed = set_agent_segment(raw, agente)
            if fixed is not None:
                if fixed != raw:
                    fixes.append((trecho, 'C.A. %s → %s [%s]' % (ca, agente, src)))
                line = fixed
            classified = True

        # C.A. conhecido na base SEM agente NR-15 (botina, óculos, luva mecânica…) =
        # não-neutralizador → silêncio: NÃO é "não catalogado", NÃO aplica heurística.
        elif not known:
            # (2) C.A. desconhecido (nem dicionário nem CAEPI): regra absoluta + flags
            l2 = line.lower()
            has_rad = any(t in l2 for t in RAD)
            has_quim = any(t in l2 for t in QUIM)
            is_creme = 'creme' in l2 or 'pomada' in l2
            is_solar = 'solar' in l2
            if is_creme and not is_solar and (has_rad or not has_quim):
                fixed = set_agent_segment(raw, AN13)
                if fixed is not None:
                    fixes.append((trecho, 'creme/pomada → %s [regra absoluta]' % AN13))
                    line = fixed
                    agente = AN13
                    classified = True
                else:
                    flags.append((trecho, 'creme/pomada deveria ser %s — estrutura não reconhecida, corrija manual.' % AN13))
            l3 = line.lower()
            has_rad3 = any(t in l3 for t in RAD)
            has_quim3 = any(t in l3 for t in QUIM)
            has_umid3 = any(t in l3 for t in UMID)
            is_mask3 = any(t in l3 for t in MASK)
            is_creme3 = 'creme' in l3 or 'pomada' in l3
            is_solar3 = 'solar' in l3
            is_capa3 = 'capa' in l3 or 'impermeáv' in l3 or 'impermeav' in l3
            if has_rad3 and not is_mask3 and not is_creme3 and not is_solar3 and not classified:
                flags.append((line.strip()[:120], 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — confira o C.A.'))
            if is_capa3 and has_quim3 and not has_umid3 and not classified:
                flags.append((line.strip()[:120], 'capa/impermeável como químico — protege UMIDADE (An.10). Confirme.'))
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

        new_lines.append(line)

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


def _vida_util(ca, desc_l, cadict, caepi=None):
    if 'creme' in desc_l or 'pomada' in desc_l:
        return 1, 'creme 1/mês'
    # vida útil só é dado CURADO: dicionário primeiro; senão coluna da base CAEPI.
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
    return None, None


def _is_protetor_aud(desc_l):
    return (('protet' in desc_l or 'auric' in desc_l or 'auditiv' in desc_l)
            and 'solar' not in desc_l)


def cobertura(lines, cadict, caepi=None):
    """Σ(qtd × vida útil) por agente (creme→An.13, protetor auditivo→Ruído). Só as entregas
    do imprescrito (abaixo da divisória ▼, se houver). Vida útil: dicionário ou coluna do
    CAEPI. Retorna (resultados, faltou_vu, tem_divisoria)."""
    tem_divisoria = any('▼' in l for l in lines)
    in_impr = not tem_divisoria  # sem divisória → considera todas
    buckets, faltou_vu = {}, []
    for raw in lines:
        if '▼' in raw:
            in_impr = True
            continue
        if not in_impr:
            continue  # entregas anteriores ao imprescrito
        ll = raw.lower()
        if not is_epi_line(ll, raw):
            continue
        parts = [p.strip() for p in raw.split(' · ')]
        if len(parts) < 2:
            continue
        mq = QTY_RE.search(parts[1])
        if not mq:
            continue
        qtd = int(mq.group(1))
        is_creme = 'creme' in ll or 'pomada' in ll
        if not (is_creme or _is_protetor_aud(ll)):
            continue  # luva/conjunto/etc → perito decide
        ca = extract_ca(raw)
        vu, _ = _vida_util(ca, ll, cadict, caepi)
        if vu is None:
            faltou_vu.append(ca or (parts[2][:30] if len(parts) > 2 else ll[:30]))
            continue
        agente = AN13 if is_creme else 'Ruído (An.1)'
        b = buckets.setdefault(agente, [0, 0])
        b[0] += qtd * vu
        b[1] += 1
    res = ['%s: %d entregas → ~%s meses cobertos (Σ qtd × vida útil)' % (a, n, ('%g' % round(m, 1)))
           for a, (m, n) in buckets.items()]
    return res, _dedup_simple(faltou_vu), tem_divisoria


def _dedup_simple(xs):
    seen, out = set(), []
    for x in xs:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out


def strip_old_block(text):
    idx = text.find(MARK)
    if idx == -1:
        return text.rstrip() + '\n'
    return text[:idx].rstrip() + '\n'


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
    new_lines, fixes, flags, nao_cat = process(text.splitlines(), cadict, caepi)
    cob_res, faltou_vu, _ = cobertura(text.splitlines(), cadict, caepi)
    body = strip_old_block('\n'.join(new_lines))

    age = caepi.age_days()
    stale = age is not None and age > 90

    if not fixes and not flags and not nao_cat and not stale and not cob_res and not faltou_vu:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        print('✅ check_epi: nenhuma classificação de EPI suspeita.')
        sys.exit(0)

    bloco = [MARK + ' (C.A. é a chave — fonte: CA-dicionario + base oficial CAEPI; o nome NÃO classifica)\n']
    if fixes:
        bloco.append('**🔧 Classificado/corrigido automaticamente (confira pelo C.A.):**')
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
    if faltou_vu:
        bloco.append('\nⓘ Vida útil não cadastrada (cobertura não calculada) p/ C.A./item: ' + ', '.join(faltou_vu)
                     + ' — cataloque `vida_util_meses` no CA-dicionario.json.')
    if stale:
        bloco.append('\n**⏰ Base CAEPI com %d dias** (build %s) — re-baixe o RelatorioCA do MTE e rode `build_caepi_index.py`.' % (age, caepi.build_date))
    new = body.rstrip() + '\n\n' + '\n'.join(bloco) + '\n'
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
