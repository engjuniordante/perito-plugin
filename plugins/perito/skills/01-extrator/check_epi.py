#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_epi.py — guarda determinístico da classificação de EPI no formulário de campo.

Lê a TABELA de fichas de EPI do formulário do extrator (Markdown:
`| Data de Entrega | Quantidade | Descrição do EPI | C.A. |`) e classifica cada
entrega PELO C.A. — nunca pelo nome comercial, que engana (ex.: creme "Luz Negra"
não é UV/radiação; é químico dérmico An.13). Crava no próprio .md um bloco
autoritativo de VERIFICAÇÃO que alimenta o quadro-resumo de EPI.

  1) LOOKUP por C.A. (prioridade):
     a. CA-dicionario.json (override curado do perito) — vence tudo.
     b. caepi.sqlite (base OFICIAL do MTE) — agente/anexo derivado da fonte.
  2) REGRA ABSOLUTA (C.A. fora de a/b): creme/pomada = Químico dérmico (An.13).
     Exceção: "protetor solar" (não é EPI — NT 146/2015 §4).
  3) CA VENCIDO (NT 146/2015): compara a data da ENTREGA (col. 1) com a VALIDADE
     do C.A. (caepi). entrega > validade → 🚩 (indício de aquisição sem CA válido;
     o perito decide). CA vencido HOJE é irrelevante.
  4) MARCA 🚩 o que só o C.A. resolve e lista 📇 C.A. não catalogados.
  5) Avisa se o índice CAEPI tiver > 90 dias (re-baixar do MTE).

Lookup no script (não na prosa) = à prova do modelo contornar. sqlite3/stdlib, zero pip.
Idempotente: re-rodar substitui o bloco anterior. NÃO dá veredicto de neutralização
(isso é do perito, in loco) — só classifica o agente pelo C.A.

uso: python3 check_epi.py <form.md> [<caepi.sqlite>] [<CA-dicionario.json>] [<base_dir>]
  Sem extras, resolve sozinho a partir de ../assets/04-EPIs/ ao lado deste script.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

# Piso 3.9 (anotações builtin) + stdout/err UTF-8: no Windows a saída capturada cai em
# cp1252 (Python <3.15) e um emoji do relatório mataria o script com UnicodeEncodeError.
if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

MARK = '## 🚩 VERIFICAÇÃO AUTOMÁTICA DE EPI'

RAD = ('radiaç', 'radiac', 'rni', 'não ioniz', 'nao ioniz', 'ultraviolet',
       'luz negra', 'an.7', 'an. 7', 'anexo 7')
QUIM = ('quím', 'quim', 'an.13', 'an. 13', 'anexo 13', 'dérm', 'derm', 'óleo',
        'oleo', 'graxa', 'álcali', 'alcali', 'solvente')
UMID = ('umidade', 'an.10', 'an. 10', 'anexo 10')
MASK = ('máscara', 'mascara', 'lente', 'viseira', 'escudo',
        'solda', 'soldad', 'capuz')
AN13 = 'Químico dérmico (An.13)'
AN11 = 'Químico inalável (An.11)'
AN7 = 'Radiação não-ionizante (An.7)'
AN1 = 'Ruído (An.1)'
IMPLAUSIBLE_EPI_HINTS = (
    'cinto', 'capacete', 'sapato', 'botina', 'calcado', 'calçado'
)
# C.A. = "CA <dígitos>" (exige o rótulo CA antes do número) — evita pegar números soltos
# da descrição ou "NBR 15292" (NBR não é C.A.). Mesma regra do plugin perito.
CA_TOKEN_RE = re.compile(r'c\.?\s?a\.?[\s:nº.\-]*([0-9][0-9./\s-]{0,20})', re.I)
DATE_RE = re.compile(r'\b(\d{2})/(\d{2})/(\d{4})\b')
# Linha da FICHA começa com a data (após bullet): "• 25/02/2023 · …". O 1º campo DEVE
# começar com a data — exclui cabeçalho, divisória ▼ e linhas do EPI — RESUMO.
ROW_START_RE = re.compile(r'^[\s\-–—•·*]*\d{2}/\d{2}/\d{4}')
# Descrição da ficha NUNCA pode ser o agente/anexo (ex.: "Químico dérmico (An.13)").
# A descrição é o NOME DO PRODUTO, literal. Se a descrição traz "(An.N)", foi renomeada.
AGENTE_NA_DESC_RE = re.compile(r'\(\s*an\.?\s*\d', re.I)


# Rótulos de override do dicionário que significam "PERITO DIZ: SEM agente NR-15"
# — correção de FALSO-POSITIVO (ex.: luva de tecido/helanca = risco mecânico; a base
# chutou An.10). Tratados como agente vazio E AUTORITATIVO: silencia no quadro 🔧 (como
# óculos/botina) e NÃO cai no CAEPI por baixo. Vence a base, igual a um override de agente.
SEM_AGENTE_NR15 = {
    '', '-', '—', 'sem agente nr-15', 'sem agente nr-15 (mecânico/geral)',
    'sem agente nr-15 (mecanico/geral)', 'epi geral sem agente nr-15 definido',
    'mecânico', 'mecanico', 'não é epi', 'nao e epi',
}


def cadict_agente(cadict, ca):
    """(agente, overridden) do CA-dicionario. overridden=True quando o C.A. está no
    dicionário (vence o CAEPI). agente=None quando o perito catalogou 'sem agente NR-15'
    — sinaliza ao guard pra silenciar o item E não buscar agente no CAEPI."""
    if ca and ca in cadict:
        ag = (cadict[ca].get('agente') or '').strip()
        return (None if ag.lower() in SEM_AGENTE_NR15 else ag), True
    return None, False


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
        self.has_vu = False
        self.has_status = False
        self.has_conf = False
        if path and os.path.exists(path):
            try:
                # as_uri() (file:///C:/... percent-encoded) — 'file:%s' com path Windows
                # (C:\...) sai fora do formato de URI que o SQLite documenta
                self.con = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro',
                                           uri=True)
                row = self.con.execute("SELECT v FROM meta WHERE k='build_date'").fetchone()
                self.build_date = row[0] if row else None
                cols = [r[1] for r in self.con.execute('PRAGMA table_info(ca)').fetchall()]
                self.has_vu = 'vida_util_meses' in cols
                self.has_status = 'status' in cols
                self.has_conf = 'confianca' in cols and 'anexo_sec' in cols
            except Exception:
                self.con = None

    def get(self, ca):
        if not self.con:
            return None
        sel = 'agente, validade_iso, validade_br, situacao, equipamento'
        if self.has_vu:
            sel += ', vida_util_meses'
        if self.has_status:
            sel += ', status'
        if self.has_conf:
            sel += ', confianca, anexo_sec'
        try:
            r = self.con.execute('SELECT %s FROM ca WHERE ca=?' % sel, (ca,)).fetchone()
        except Exception:
            return None
        if not r:
            return None
        d = {'agente': r[0], 'validade_iso': r[1], 'validade_br': r[2], 'situacao': r[3],
             'equipamento': r[4]}
        i = 5
        if self.has_vu:
            d['vida_util_meses'] = r[i]; i += 1
        if self.has_status:
            d['status'] = r[i]; i += 1
        if self.has_conf:
            d['confianca'] = r[i]; d['anexo_sec'] = r[i + 1]; i += 2
        return d

    def age_days(self):
        if not self.build_date:
            return None
        try:
            return (date.today() - date.fromisoformat(self.build_date)).days
        except Exception:
            return None


def split_row(line):
    """Linha da ficha (formato Notas) -> células. Campos separados por ' · ':
    "• 25/02/2023 · 1un · DESCRIÇÃO · CA 26149"."""
    return [c.strip() for c in line.split(' · ')]


def is_data_row(cells):
    """Linha de DADOS da ficha: ≥3 campos e o 1º começa com a data. O date-gate exclui
    sozinho cabeçalho, separador, divisória ▼ e linhas do EPI — RESUMO (sem data no início)."""
    return len(cells) >= 3 and bool(ROW_START_RE.match(cells[0]))


def _normalize_ca_token(token):
    raw = (token or '').strip()
    if not raw:
        return None
    if re.search(r'\d{4,}\s*/\s*\d{4,}', raw):
        return None
    head = raw.split('/')[0]
    parts = re.findall(r'\d+', head)
    if not parts:
        return None
    if '.' in head and len(parts) >= 2 and len(parts[-1]) == 3 and len(''.join(parts)) <= 6:
        return ''.join(parts)
    return parts[0]


def extract_ca(line):
    m = CA_TOKEN_RE.search(line)
    return _normalize_ca_token(m.group(1)) if m else None


def first_date_iso(s):
    m = DATE_RE.search(s)
    if not m:
        return None, None
    d, mo, y = m.groups()
    try:
        return date(int(y), int(mo), int(d)).isoformat(), '%s/%s/%s' % (d, mo, y)
    except ValueError:
        return None, None


def classify_no_ca(desc):
    """C.A. desconhecido: só a regra absoluta de creme é determinística; o resto flaga."""
    d = desc.lower()
    is_creme = 'creme' in d or 'pomada' in d
    is_solar = 'solar' in d
    has_rad = any(t in d for t in RAD)
    has_quim = any(t in d for t in QUIM)
    has_umid = any(t in d for t in UMID)
    is_mask = any(t in d for t in MASK)
    is_capa = 'capa' in d or 'impermeáv' in d or 'impermeav' in d
    if is_creme and not is_solar and (has_rad or not has_quim):
        return AN13, 'regra absoluta', None
    flag = None
    if has_rad and not is_mask and not is_creme and not is_solar:
        flag = 'descrição cita radiação/UV sem ser máscara/lente/escudo de solda — confira o C.A.'
    elif is_capa and has_quim and not has_umid:
        flag = 'capa/impermeável como químico — protege UMIDADE (An.10). Confirme.'
    return None, None, flag


def _caepi_src(hit):
    """Rótulo da coluna Fonte p/ classificação vinda do CAEPI. Confiança não-alta = chute
    automático que o perito deve conferir → '⚠ CAEPI' (+ alternativa An.X quando a base
    aponta um anexo secundário). Confiança alta (auditivo/creme/solda) → 'CAEPI' liso.
    O ⚠ some sozinho quando o perito cataloga o C.A. (vira Fonte 'dicionário')."""
    conf = (hit.get('confianca') or '').lower()
    if not conf or conf == 'alta':
        return 'CAEPI'
    sec = (hit.get('anexo_sec') or '').strip()
    return '⚠ CAEPI — pode ser An.%s, confira' % sec if sec else '⚠ CAEPI — confira o contexto'


def _normalize_hit_agente(agente, desc, equipamento):
    d = (desc or '').lower()
    eq = (equipamento or '').lower()
    txt = d + ' ' + eq
    if any(k in txt for k in ('auric', 'auditiv', 'abafador', 'concha', 'plug', 'plugue')):
        return AN1, None
    if ('creme' in txt or 'pomada' in txt) and 'solar' not in txt:
        return AN13, None
    if any(k in txt for k in ('lente', 'viseira', 'escudo', 'solda', 'protetor facial')):
        return AN7, None
    if any(k in txt for k in ('mascara', 'máscara', 'respir')) and agente == AN7:
        return AN11, 'CAEPI classificou como An.7, mas a descrição é respiratória; revisar catalogação do C.A.'
    if 'luva' in txt and any(k in txt for k in ('acid', 'solvent', 'quim', 'quím', 'nitril', 'latex', 'látex', 'pvc')):
        return AN13, None
    if agente in (AN7, AN11, AN13, 'Umidade (An.10)', 'Frio (An.9)') and any(k in d for k in IMPLAUSIBLE_EPI_HINTS):
        return None, 'classificação do CAEPI parece implausível para a descrição do item; revisar o C.A. antes de usar.'
    return agente, None


def process(lines, cadict, caepi):
    classified, flags, nao_cat = [], [], []
    for raw in lines:
        cells = split_row(raw)
        if not is_data_row(cells):
            continue
        data_cell, desc = cells[0], cells[-2]
        ca = extract_ca(raw)

        # ⛔ Descrição renomeada para o AGENTE — proibido (vaza pro laudo; o perito lê a ficha)
        if AGENTE_NA_DESC_RE.search(desc):
            flags.append((desc[:80] + (' [C.A. %s]' % ca if ca else ''),
                          'DESCRIÇÃO DA FICHA SUBSTITUÍDA PELO AGENTE — restaure o NOME DO PRODUTO (literal da ficha). O agente vai só nesta verificação 🔧, NUNCA na coluna Descrição.'))
        agente = src = None
        hit = None
        known = False

        if ca:
            ov_ag, overridden = cadict_agente(cadict, ca)
            if overridden:
                agente, src, known = ov_ag, 'dicionário', True
            else:
                hit = caepi.get(ca)
                if hit is not None:
                    known = True
                    if hit.get('agente'):
                        agente, flag = _normalize_hit_agente(hit['agente'], desc, hit.get('equipamento') or '')
                        src = _caepi_src(hit) if agente else None
                        if flag:
                            flags.append((desc[:80] + (' [C.A. %s]' % ca if ca else ''), flag))
                    elif hit.get('status') == 'revisar':
                        # base canônica marcou o C.A. como ambíguo (sem agente NR-15 seguro).
                        # NÃO ficar em silêncio: pedir contexto/override ao perito. Já
                        # 'nao_correlacionar'/'nao_epi' seguem silenciosos (EPI mecânico/geral).
                        flags.append((desc[:80] + (' [C.A. %s]' % ca if ca else ''),
                                      'classificação NR-15 incerta na base (status: revisar) — definir agente pelo contexto e, se recorrente, fixar no CA-dicionario.json (skill de atualização da base).'))

        if not agente and not known:
            agente, src, flag = classify_no_ca(desc)
            if flag:
                flags.append((desc[:80] + (' [C.A. %s]' % ca if ca else ''), flag))
            if not agente and ca:
                nao_cat.append(ca)

        if agente:
            classified.append((ca or '—', desc[:80], agente, src))

        # CA vencido (NT 146/2015) — só p/ EPI que neutraliza (tem agente) e com data
        if ca and agente:
            di, dbr = first_date_iso(data_cell)
            if di:
                h = hit if hit is not None else caepi.get(ca)
                if h and h.get('validade_iso') and di > h['validade_iso']:
                    flags.append((desc[:60] + ' [C.A. %s]' % ca,
                                  'entregue em %s com C.A. VENCIDO em %s — indício de aquisição sem CA válido (NT 146/2015). Confirmar.'
                                  % (dbr, h['validade_br'])))

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    return dedup(classified), dedup(flags), dedup(nao_cat)


# ---- cobertura por TIPO (item 6.1.1 NR-6) — determinística, só na tabela do imprescrito ----
QTY_RE = re.compile(r'(\d+)')
# vida útil por TIPO de protetor auditivo (meses); per-C.A. (dicionário/CAEPI) sobrepõe.
TYPE_VU = [
    (('espuma', 'descart', 'moldáv', 'moldav'), round(1 / 21, 3), 'espuma 1 dia útil'),
    (('concha', 'abafador', 'circum'), 12.0, 'concha 12m'),
    (('plug', 'plugue', 'silicone', 'inser', 'tampão', 'tampao', 'pré-mold', 'pre-mold'), 6.0, 'plug 6m'),
]
CERTIFIABLE_HINTS = (
    'botina', 'sapato', 'calcado', 'calçado', 'oculos', 'óculos', 'protetor', 'auric',
    'capacete', 'luva', 'mascara', 'máscara', 'respir', 'avental', 'perneira', 'lente',
    'viseira', 'creme', 'capuz', 'mangote', 'jaleco', 'respirador'
)
NON_CERTIFIABLE_HINTS = (
    'camisa', 'camiseta', 'calca', 'calça', 'calca jeans', 'calça jeans', 'palmilha',
    'carneira', 'paraf', 'parafuso', 'peca', 'peça'
)


def _vida_util(ca, txt, cadict, caepi):
    if ca and ca in cadict and cadict[ca].get('vida_util_meses'):
        try:
            return float(cadict[ca]['vida_util_meses'])
        except (TypeError, ValueError):
            pass
    if ca and caepi is not None and getattr(caepi, 'has_vu', False):
        hit = caepi.get(ca)
        if hit and hit.get('vida_util_meses'):
            try:
                return float(hit['vida_util_meses'])
            except (TypeError, ValueError):
                pass
    if 'creme' in txt or 'pomada' in txt:
        return 1.0
    for kws, vu, _ in TYPE_VU:
        if any(k in txt for k in kws):
            return vu
    return None


def _is_certifiable(desc, ca):
    if ca:
        return True
    d = (desc or '').lower()
    if any(tok in d for tok in NON_CERTIFIABLE_HINTS):
        return False
    return any(tok in d for tok in CERTIFIABLE_HINTS)


# Exige o ':' do CAMPO ("Período imprescrito: ★ de … até …") — assim a regex NÃO casa a
# prosa "dentro do período imprescrito (admissão … autuação DD/MM/AAAA)", que não tem ':'
# depois de "imprescrito" e pescava a data da AUTUAÇÃO como fim do imprescrito.
IMPRESCRITO_RE = re.compile(r'per[ií]odo imprescrito[^\n:]*:[^\n]*?(\d{2}/\d{2}/\d{4})[^\n]*?(\d{2}/\d{2}/\d{4})', re.I)
# "Período trabalhado: de DD/MM/AAAA até DD/MM/AAAA" — a 2ª data é o fim do contrato (demissão).
# Exige o ':' do campo (mesma defesa do IMPRESCRITO_RE contra prosa). Sem 2ª data (contrato em
# curso / campo incompleto) → não casa → sem clamp.
PERIODO_TRAB_RE = re.compile(r'per[ií]odo trabalhado[^\n:]*:[^\n]*?(\d{2}/\d{2}/\d{4})[^\n]*?(\d{2}/\d{2}/\d{4})', re.I)


def _contract_end(text):
    """Fim do período trabalhado (demissão) em ISO, ou None. A cobertura/gap de EPI NÃO pode se
    estender além do fim do contrato — não há exposição depois que o trabalhador saiu."""
    m = PERIODO_TRAB_RE.search(text)
    return first_date_iso(m.group(2))[0] if m else None


def _contract_start(text):
    """Início do período trabalhado (admissão) em ISO, ou None. O imprescrito NÃO pode começar
    antes da admissão — não há vínculo (logo, nem exposição nem EPI) antes do contrato."""
    m = PERIODO_TRAB_RE.search(text)
    return first_date_iso(m.group(1))[0] if m else None


def _clamp_impr_end(text, impr_b_iso):
    """Recorta o fim do imprescrito ao fim do contrato quando este vem ANTES (a prescrição
    quinquenal vai até a data da ação, mas a exposição acaba na demissão). Contrato ativo → intacto."""
    ce = _contract_end(text)
    return ce if (impr_b_iso and ce and ce < impr_b_iso) else impr_b_iso


def _clamp_impr_start(text, impr_a_iso):
    """Recorta o início do imprescrito ao início do contrato quando o imprescrito começa ANTES da
    admissão. Espelha _clamp_impr_end na outra ponta. A prescrição quinquenal recua até (ação−5
    anos), mas não há vínculo antes da admissão: um imprescrito-início pré-admissão (NLM aplicando
    '5 anos da data da ação' sem recortar ao pacto) infla o denominador de cobertura e cria 'gap'
    fantasma pré-emprego. Determinístico — o cálculo do imprescrito não é julgamento, é data."""
    cs = _contract_start(text)
    return cs if (impr_a_iso and cs and cs > impr_a_iso) else impr_a_iso
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
    ini = _clamp_impr_start(text, first_date_iso(m.group(1))[0])  # nunca antes da admissão
    if ini:
        try:
            ini = (date.fromisoformat(ini) - timedelta(days=IMPRESC_GRACE_DAYS)).isoformat()
        except ValueError:
            pass
    # fim recortado ao fim do contrato (sem exposição após a demissão)
    return ini, _clamp_impr_end(text, first_date_iso(m.group(2))[0])


# ---- afastamentos: descontados da exposição (não há exposição durante a ausência) ----
AFAST_HEADER_RE = re.compile(r'▶\s*AFASTAMENTOS', re.I)
DE_LINE_RE = re.compile(r'^\s*de\s*:', re.I)
FULLDATE_RE = re.compile(r'\d{2}/\d{2}/\d{4}')
TOTAL_EXCL_RE = re.compile(r'total\s+exclu[ií]do\s*:\s*~?\s*(\d+)\s*dias', re.I)


def _afastamentos(text):
    """Períodos de afastamento do bloco ▶ AFASTAMENTOS, PRESOS À SEÇÃO (do header ao próximo
    boundary) — imune ao 'De:/até:' de COVID do agente M, que fica fora da seção. Para cada linha
    'De:', as 2 primeiras datas = (início, fim). Retorna (intervalos, ok): ok=False se alguma linha
    'De:' tiver data ilegível/incompleta → o chamador NÃO desconta (degrada pro manual) e avisa.
    Linha 'De:  até:  motivo:' VAZIA (0 datas) = placeholder do template → ignorada, não conta.
    Sem seção / sem linha 'De:' → ([], True) = no-op (a maioria dos processos)."""
    lines = text.split('\n')
    h = next((i for i, l in enumerate(lines) if AFAST_HEADER_RE.search(l)), None)
    if h is None:
        return [], True
    end = _next_boundary(lines, h + 1)
    out, ok = [], True
    for l in lines[h + 1:end]:
        if not DE_LINE_RE.match(l):
            continue                       # ignora 'Total excluído:' e linhas soltas
        ds = FULLDATE_RE.findall(l)
        if len(ds) == 0:
            continue                       # 'De:  até:  motivo:' vazio = placeholder do template → ignora
        if len(ds) < 2:
            ok = False                     # afastamento de verdade com 1 data só → ilegível/incompleto → manual
            continue
        try:
            ini, fim = (date.fromisoformat(first_date_iso(ds[0])[0]),
                        date.fromisoformat(first_date_iso(ds[1])[0]))
        except (ValueError, TypeError):
            ok = False
            continue
        if (fim - ini).days > 0:
            out.append((ini, fim))
    return _merge_intervals(out), ok


def _merge_intervals(ivs):
    """Funde intervalos sobrepostos/adjacentes → soma de dias nunca conta em dobro."""
    if not ivs:
        return []
    ivs = sorted(ivs)
    merged = [ivs[0]]
    for a, b in ivs[1:]:
        la, lb = merged[-1]
        if a <= lb:
            merged[-1] = (la, max(lb, b))
        else:
            merged.append((a, b))
    return merged


def _afastamento_days_in(afast, a, b):
    """Total de dias de afastamento clipados à janela [a, b] — denominador de EXPOSIÇÃO."""
    if not (a and b):
        return 0
    total = 0
    for ini, fim in afast:
        lo, hi = max(ini, a), min(fim, b)
        if (hi - lo).days > 0:
            total += (hi - lo).days
    return total


def _subtract_intervals(wins, afast):
    """Tira de cada janela de gap a sobreposição com os afastamentos (pode partir/encurtar/zerar).
    Gap descoberto que sobra = período SEM cobertura E COM exposição. Determinístico."""
    if not afast:
        return wins
    out = []
    for a, b, _ in wins:
        segs = [(a, b)]
        for ini, fim in afast:
            nxt = []
            for s, e in segs:
                if fim <= s or ini >= e:          # sem sobreposição
                    nxt.append((s, e)); continue
                if ini > s:
                    nxt.append((s, ini))           # pedaço antes do afastamento
                if fim < e:
                    nxt.append((fim, e))           # pedaço depois do afastamento
            segs = nxt
        for s, e in segs:
            d = (e - s).days
            if d > 0:
                out.append((s, e, d))
    out.sort()
    return out


def cobertura(lines, cadict, caepi):
    """Σ(qtd × vida útil) por agente, SÓ nas entregas do imprescrito. Recorte por DATA
    (campo 'Período imprescrito'); fallback divisória ▼/▲; fallback ficha inteira.
    Vida útil por TIPO (plug 6m · concha 12m · espuma 1 dia útil · creme 1/mês) + override por C.A.
    Classifica pelo AGENTE do C.A. (não pela descrição, que pode ter sido renomeada). Ruído e creme;
    luva/conjunto = perito. Retorna (resultados, faltou_vu)."""
    buckets, faltou, events = {}, [], {}
    text = '\n'.join(lines)
    impr_a, impr_b = _imprescrito_range(text)
    # lookback p/ detecção de gap: uma entrega até ~500 dias ANTES do imprescrito pode ainda
    # estar cobrindo o início (ex.: concha 12m), sobretudo quando a prescrição corta o meio do
    # contrato. Coletada como EVENTO de gap (herda cobertura), mas NÃO entra na soma Σ.
    gaplo = None
    if impr_a:
        try:
            gaplo = (date.fromisoformat(impr_a) - timedelta(days=500)).isoformat()
        except ValueError:
            gaplo = impr_a
    tem_div = any('▼' in l for l in lines)
    use_date = impr_a is not None          # preferível: recorta pela DATA do imprescrito
    in_impr = use_date or (not tem_div)    # date mode: filtra por linha; ▼ mode: alterna; nenhum: tudo
    for raw in lines:
        if not use_date:
            if '▼' in raw:
                in_impr = True
                continue
            if '▲' in raw:
                in_impr = False
                continue
        if not in_impr:
            continue
        cells = split_row(raw)
        # só linhas de DADOS da tabela (is_data_row exclui cabeçalho/separador/divisória
        # e linhas do EPI — RESUMO; o bloco 🔧 anterior já foi removido por strip_old_block)
        if not is_data_row(cells):
            continue
        di = first_date_iso(cells[0])[0]
        in_sum = True                      # entra na SOMA Σ só se dentro do imprescrito
        if use_date:
            if di is None:
                continue
            if di < impr_a or (impr_b and di > impr_b):
                in_sum = False             # fora do imprescrito → não soma (mas pode virar evento de gap)
            if gaplo and di < gaplo:        # antes até do lookback → não cobre o início, ignora de vez
                continue
        mq = QTY_RE.search(cells[1])
        if not mq:
            continue
        qtd = int(mq.group(1))
        if qtd > 500:                      # quantidade irreal = parse errado → ignorar
            continue
        desc = cells[-2]
        ca = extract_ca(raw)
        agente, equip = None, ''
        ov_ag, overridden = cadict_agente(cadict, ca)
        if overridden:
            agente = ov_ag
        if ca and caepi is not None:
            hit = caepi.get(ca)
            if hit:
                if not overridden:                 # override (inclui 'sem agente') vence o CAEPI
                    agente = hit.get('agente')
                equip = (hit.get('equipamento') or '').lower()
        txt = desc.lower() + ' ' + equip
        if 'solar' in txt and ('creme' in txt or 'pomada' in txt or 'protet' in txt):
            continue                       # protetor solar não é EPI (NT 146/2015 §4) — fora da cobertura
        is_creme = 'creme' in txt or 'pomada' in txt
        # "protet" sozinho pesca "Protetor facial" (An.7) — exigir auric/auditiv;
        # o agente Ruído (do C.A.) continua sendo o caminho autoritativo.
        is_prot = (agente == 'Ruído (An.1)') or any(k in txt for k in ('auric', 'auditiv'))
        if not (is_creme or is_prot):
            continue
        vu = _vida_util(ca, txt, cadict, caepi)
        if vu is None:
            if in_sum:
                faltou.append(ca or desc[:30])
            continue
        bucket = AN13 if is_creme else 'Ruído (An.1)'
        if in_sum:
            b = buckets.setdefault(bucket, [0.0, 0])
            b[0] += qtd * vu
            b[1] += 1
        if di:                             # evento de gap (inclui o lookback pré-janela p/ herdar cobertura)
            try:
                events.setdefault(bucket, []).append((date.fromisoformat(di), qtd, vu))
            except ValueError:
                pass
    # impr_a vem recuado IMPRESC_GRACE_DAYS (p/ capturar EPI de admissão no FILTRO); para a
    # ÂNCORA do gap de abertura, desfaz o recuo → início REAL do imprescrito.
    impr_a_d = date.fromisoformat(impr_a) if impr_a else None
    if impr_a_d:
        impr_a_d += timedelta(days=IMPRESC_GRACE_DAYS)
    impr_b_d = date.fromisoformat(impr_b) if impr_b else None
    window_days = (impr_b_d - impr_a_d).days if (impr_a_d and impr_b_d) else None
    # Afastamentos: durante a ausência NÃO há exposição → descontados da janela (denominador de
    # EXPOSIÇÃO) E das janelas de gap. Se a leitura do bloco for suspeita (afast_ok=False), NÃO
    # desconta (degrada pro manual, como antes) e avisa — nunca subtrai número duvidoso em silêncio.
    afast, afast_ok = _afastamentos(text)
    afast = afast if afast_ok else []
    afast_days = _afastamento_days_in(afast, impr_a_d, impr_b_d) if window_days else 0
    expo_days = (window_days - afast_days) if window_days else None
    den_label = 'exposição (imprescrito − afastamento)' if afast else 'imprescrito'
    res, cov_by_agent, gaps_by_agent = [], {}, {}
    for a, (m, n) in buckets.items():
        wins = _subtract_intervals(_clipped_windows(events.get(a, []), impr_a_d, impr_b_d), afast)
        if expo_days and expo_days > 0:
            # cobertura CONTÍNUA = exposição − soma dos buracos (já sem os trechos de afastamento).
            covered = max(0.0, (expo_days - sum(d for _, _, d in wins))) / 30.44
            cov_by_agent[a] = covered
            gaps_by_agent[a] = _gap_status(wins)   # gatilho p/ o slot do RESUMO (mesma régua do 📐)
            res.append('%s: %d entregas · cobertura contínua ~%.1f de ~%.1f meses de %s'
                       % (a, n, covered, expo_days / 30.44, den_label))
        else:                                  # sem janela (modo ▼) → não dá p/ continuidade; Σ de fallback
            cov_by_agent[a] = m
            res.append('%s: %d entregas → ~%s meses (Σ qtd × vida útil — sem janela p/ continuidade)'
                       % (a, n, ('%g' % round(m, 1))))
        res.extend(_coverage_gaps(a, wins))

    # Frase clara da conta + ECO dos períodos descontados (perito confere contra a ficha/PPP) —
    # só quando houve desconto e há cobertura a contextualizar.
    if afast and buckets and window_days:
        res.append('Exposição = ~%.1fm imprescrito − ~%.1fm afastamento (%d período%s) = ~%.1fm'
                   % (window_days / 30.44, afast_days / 30.44, len(afast),
                      '' if len(afast) == 1 else 's', max(0, expo_days) / 30.44))
        res.append('afastamentos descontados: '
                   + ' · '.join('%s–%s' % (i.strftime('%d/%m/%Y'), f.strftime('%d/%m/%Y'))
                                for i, f in afast))
        # autoconferência: a soma do guard vs a linha "Total excluído: N dias" (preenchida pelo
        # modelo, caminho independente). Divergência > 15d = bandeira pro perito.
        mt = TOTAL_EXCL_RE.search(text)
        if mt:
            decl = int(mt.group(1))
            if abs(afast_days - decl) > 15:
                res.append('⚠ soma do guard (%dd) ≠ "Total excluído" do formulário (%dd) — confira o bloco AFASTAMENTOS'
                           % (afast_days, decl))
    if not afast_ok:
        res.append('⚠ bloco AFASTAMENTOS com data ilegível/incompleta — NÃO descontado automaticamente; confira e abata manualmente')

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x and x not in seen:
                seen.add(x); out.append(x)
        return out
    return res, dedup(faltou), (use_date or tem_div), cov_by_agent, gaps_by_agent


def _clipped_windows(events, win_lo, win_hi):
    """TODOS os buracos de cobertura (qualquer tamanho ≥1d) clipados a [win_lo, win_hi]. events
    inclui lookback pré-janela (herda cobertura). Cada entrega cobre [data, data+qtd×vida útil];
    o buraco é o intervalo entre o fim de uma cobertura e a próxima entrega. Cobre abertura, meio
    e cauda. Clipar evita falso-positivo quando o imprescrito corta o MEIO do contrato. Base tanto
    da cobertura contínua (janela − Σ buracos) quanto do display de períodos descobertos."""
    if not events:
        return []
    evs = sorted(events, key=lambda e: e[0])
    raw, cover_end = [], None
    for di, qtd, vu in evs:
        if cover_end is not None and di > cover_end:
            raw.append((cover_end, di))                  # buraco entre o fim da cobertura e a próxima entrega
        ce = di + timedelta(days=int(round(qtd * vu * 30.44)))
        if cover_end is None or ce > cover_end:
            cover_end = ce
    if win_lo and evs[0][0] > win_lo:                    # nenhuma entrega no/antes do início → abertura
        raw.append((win_lo, evs[0][0]))
    if win_hi and cover_end and cover_end < win_hi:      # cobertura acaba antes do fim → cauda
        raw.append((cover_end, win_hi))
    wins = []
    for a, b in raw:                                     # clipa à janela [win_lo, win_hi]
        if win_lo and a < win_lo:
            a = win_lo
        if win_hi and b > win_hi:
            b = win_hi
        if (b - a).days > 0:
            wins.append((a, b, (b - a).days))
    wins.sort()
    return wins


# Régua de materialidade de gap — FONTE ÚNICA (usada pela prova 📐 E pelo flag do slot do
# EPI — RESUMO, p/ decisão e auditoria NUNCA divergirem).
#   WINDOW_FLOOR (15d): janela mínima p/ contar — absorve jitter de reposição/estimativa de vida útil.
#   MATERIAL (30d): só alerta se a MAIOR janela OU o TOTAL somado atingir ~1 mês.
WINDOW_FLOOR = 15
MATERIAL = 30


def _material_windows(wins):
    """Janelas que CONTAM pela régua de materialidade (≥ WINDOW_FLOOR e, no conjunto, atingindo
    MATERIAL isolada ou somada). [] = imaterial. Base comum do 📐 e do flag do slot."""
    wins = [w for w in wins if w[2] >= WINDOW_FLOOR]
    if not wins:
        return []
    total = sum(d for _, _, d in wins)
    if max(d for _, _, d in wins) < MATERIAL and total < MATERIAL:
        return []                                        # nada atinge ~1 mês (isolado nem somado) → imaterial
    return wins


def _gap_status(wins):
    """Status curto de gap p/ o slot 'cobre X/Y meses' do EPI — RESUMO (ao lado do checkbox do
    perito), com a MESMA régua do 📐. 'contínuo, sem gap' se imaterial; senão
    '⚠ N janela(s) ~X.Xm (ver 📐)'. As datas exatas ficam no 📐 — aqui é só o gatilho."""
    mats = _material_windows(wins)
    if not mats:
        return 'contínuo, sem gap'
    n = len(mats)
    total_m = sum(d for _, _, d in mats) / 30.44
    return '⚠ %d janela%s ~%.1fm (ver 📐)' % (n, '' if n == 1 else 's', total_m)


def _coverage_gaps(agente, wins):
    """Display dos PERÍODOS DESCOBERTOS a partir das janelas clipadas (_clipped_windows),
    pela régua ÚNICA de materialidade (_material_windows — mesma do flag do slot)."""
    wins = _material_windows(wins)
    if not wins:
        return []
    total = sum(d for _, _, d in wins)
    if len(wins) == 1:
        a, b, d = wins[0]
        return ['⚠ %s — PERÍODO DESCOBERTO: %s → %s (~%d dias / ~%.1f meses sem reposição)'
                % (agente, a.strftime('%d/%m/%Y'), b.strftime('%d/%m/%Y'), d, d / 30.44)]
    out = ['⚠ %s — DESCOBERTO ~%.1f meses no TOTAL, em %d janelas (cada ≥%dd) no imprescrito:'
           % (agente, total / 30.44, len(wins), WINDOW_FLOOR)]
    for a, b, d in wins[:5]:
        out.append('   • %s → %s (~%d dias)' % (a.strftime('%d/%m/%Y'), b.strftime('%d/%m/%Y'), d))
    if len(wins) > 5:
        out.append('   • (+%d janelas menores)' % (len(wins) - 5))
    return out


def _imprescrito_months(text):
    """Meses de EXPOSIÇÃO para o denominador do slot 'cobre X/Y meses' = span do imprescrito
    (clampado ao fim do contrato) MENOS os afastamentos. ~30,44 dias/mês. Mesma régua do
    denominador da cobertura() → o slot e o 📐 nunca divergem."""
    m = IMPRESCRITO_RE.search(text)
    if not m:
        return None
    a, b = first_date_iso(m.group(1))[0], first_date_iso(m.group(2))[0]
    a = _clamp_impr_start(text, a)        # denominador não conta meses antes da admissão
    b = _clamp_impr_end(text, b)          # denominador não conta meses após a demissão
    if not (a and b):
        return None
    try:
        ad, bd = date.fromisoformat(a), date.fromisoformat(b)
    except ValueError:
        return None
    days = (bd - ad).days
    afast, afast_ok = _afastamentos(text)
    if afast_ok and afast:                # desconta a ausência (só se a leitura foi confiável)
        days -= _afastamento_days_in(afast, ad, bd)
    return max(0, days) / 30.44


# slot do EPI — RESUMO: "… cobre __/__ meses …" OU um valor já preenchido. O guard é a fonte
# autoritativa da cobertura do quadro-resumo; portanto ele DEVE sobrescrever números/stati
# anteriores para impedir divergência entre o slot e o bloco 📐.
# O grupo de status (⚠…) termina em caractere NÃO-espaço (`[^·\n\s]`) p/ NÃO engolir o espaço
# antes do "· [ ]✓" seguinte — senão a função não seria idempotente (re-rodar drenava 1 espaço,
# fazendo o validador acusar divergência falsa entre o slot do guard e o recálculo).
SLOT_RE = re.compile(
    r'(cobre\s+)(?:_+|[\d.,]+)\s*/\s*(?:_+|[\d.,]+)(\s+meses)(?:\s+·\s+(?:⚠[^·\n]*[^·\n\s]|cont[ií]nuo,\s*sem\s*gap))?',
    re.I)


def _agent_for_resumo_line(line):
    l = line.lower()
    if 'ruído' in l or 'ruido' in l or 'an.1)' in l:
        return 'Ruído (An.1)'
    if 'an.13' in l or 'óleo' in l or 'oleo' in l or 'álcali' in l or 'alcali' in l or 'creme' in l:
        return AN13
    return None


def fill_inline_coverage(body, cov_by_agent, gaps_by_agent, impr_months):
    """Preenche o slot 'cobre __/__ meses' das linhas do EPI — RESUMO: numerador = cobertura
    calculada do agente; denominador = meses do imprescrito; e ANEXA o status de gap
    (gaps_by_agent) logo após 'meses', ao lado do checkbox — DECISÃO CARREGA O GATILHO. O
    checkbox de veredicto fica intocado (decisão do perito). O guard sobrescreve sempre o
    trecho 'cobre X/Y meses · status' para impedir drift entre resumo e bloco 📐."""
    if not cov_by_agent:
        return body
    gaps_by_agent = gaps_by_agent or {}
    den = ('%g' % round(impr_months)) if impr_months else '__'
    out = []
    for line in body.split('\n'):
        if SLOT_RE.search(line):
            ag = _agent_for_resumo_line(line)
            if ag and ag in cov_by_agent:
                num = '%g' % round(cov_by_agent[ag], 1)
                status = gaps_by_agent.get(ag)
                line = SLOT_RE.sub(
                    lambda mm: '%s%s/%s%s%s' % (mm.group(1), num, den, mm.group(2),
                                                (' · ' + status if status else '')),
                    line)
        out.append(line)
    return '\n'.join(out)


# ---- EPI — RESUMO: quantidade·CA·material por slot (guard autoritativo, v1.34) ----
# O Step 2 (script) deixa os slots vazios (`__un · CA__`, `__potes`, `__pares · __material`…);
# o guard consolida as entregas do IMPRESCRITO por item e crava quantidade/CA/(material|PFF).
# NÃO toca o segmento "cobre X/Y meses" (dono = fill_inline_coverage) — o regex de A) só
# substitui o trecho ANTES de " · cobre". Idempotente: recomputa do zero e o regex casa tanto o
# placeholder quanto um valor já preenchido. Quem NÃO tem entrega no slot fica com o placeholder.

def _resumo_entregas(lines, cadict, caepi):
    """Entregas do imprescrito → [(ca, desc, qtd, agente, txt_lower)]. Recorte por DATA (igual
    cobertura): campo 'Período imprescrito'; fallback divisória ▼/▲; fallback ficha inteira."""
    text = '\n'.join(lines)
    impr_a, impr_b = _imprescrito_range(text)
    tem_div = any('▼' in l for l in lines)
    use_date = impr_a is not None
    in_impr = use_date or (not tem_div)
    out = []
    for raw in lines:
        if not use_date:
            if '▼' in raw:
                in_impr = True; continue
            if '▲' in raw:
                in_impr = False; continue
        if not in_impr:
            continue
        cells = split_row(raw)
        if not is_data_row(cells):
            continue
        if use_date:
            di = first_date_iso(cells[0])[0]
            if di is None or di < impr_a or (impr_b and di > impr_b):
                continue
        mq = QTY_RE.search(cells[1])
        qtd = int(mq.group(1)) if mq else 1
        if qtd > 500:                                   # quantidade irreal = parse errado
            continue
        desc = cells[-2]
        ca = extract_ca(raw)
        agente, equip = None, ''
        ov_ag, overridden = cadict_agente(cadict, ca)
        if overridden:
            agente = ov_ag
        if ca and caepi is not None:
            hit = caepi.get(ca)
            if hit:
                if not overridden:                 # override (inclui 'sem agente') vence o CAEPI
                    agente = hit.get('agente')
                equip = (hit.get('equipamento') or '').lower()
        out.append((ca, desc, qtd, agente, desc.lower() + ' ' + equip))
    return out


def _resumo_short(desc):
    return re.sub(r'\s+', ' ', desc).strip()[:24]


def _resumo_group(items, unit='un'):
    """Agrupa por C.A.: soma qtd, guarda 1 desc curta. Mantém ordem de 1ª aparição.
    → 'Σqtd<unit> CA <ca> (<short>) + … [+ Σqtd<unit> <short> sem CA]'."""
    order, agg = [], {}
    for ca, desc, qtd, ag, txt in items:
        key = ca if (ca and ca != '—') else None
        if key not in agg:
            agg[key] = [0, _resumo_short(desc)]
            order.append(key)
        agg[key][0] += qtd
    parts = []
    for key in order:
        q, short = agg[key]
        if key:
            parts.append('%d%s CA %s%s' % (q, unit, key, (' (%s)' % short if short else '')))
        else:
            parts.append('%d%s %s sem CA' % (q, unit, short or 'item'))
    return ' + '.join(parts)


# Luva "imperm." = só barreira química/umidade (An.10/An.13). Raspa/vaqueta/malha = proteção
# mecânica (não entram neste slot; aparecem na TABELA EPI completa).
_IMPERM_KW = ('látex', 'latex', 'nitríl', 'nitril', 'pvc', 'hycron', 'neoprene',
              'borracha', 'banh', 'tricoflex', 'vinil', 'impermeá', 'impermea')


def _resumo_an7_note(items):
    """Nota seca de discrepância: respirador/PFF que o CAEPI classifica como An.7 (radiação).
    O perito decide; a prosa de contexto fina vive no CA-dicionario (override curado)."""
    cas = []
    for ca, desc, qtd, ag, txt in items:
        if ca and ca != '—' and ag and 'An.7' in ag and ca not in cas:
            cas.append(ca)
    if cas:
        return ' · ⚠ CA %s = An.7 no CAEPI — perito decide' % '/'.join(cas)
    return ''


# A) slots COM cobertura: substitui só o trecho entre "label: " e " · cobre" (não toca cobertura)
_RES_PROT_RE = re.compile(r'(•\s*Protetor\s*\(ru[ií]do\):\s*).*?(\s*·\s*cobre)', re.I)
_RES_CREME_RE = re.compile(r'(•\s*Creme[^:]*:\s*).*?(\s*·\s*cobre)', re.I)
# B) slots SEM cobertura: substitui o valor até o fim da linha
_RES_LUVA_RE = re.compile(r'(•\s*Luva\s+imperm\.:\s*).*$', re.I | re.M)
_RES_MASK_RE = re.compile(r'(•\s*M[aá]scara/resp\.:\s*).*$', re.I | re.M)
# C) conjunto — marca peça presente na ficha (perito confirma adequação). Só Defensivo An.13 +
# Umidade An.10 por ora (validados em caso real de pulverização); Solda/Frio = follow-up.
_RES_DEF_RE = re.compile(r'(•\s*Defensivo An\.13:\s*).*$', re.I | re.M)
_RES_UMI_RE = re.compile(r'(•\s*Umidade An\.10:\s*).*$', re.I | re.M)
_RES_FRIO_RE = re.compile(r'(•\s*Frio An\.9:\s*).*$', re.I | re.M)


def fill_resumo_items(body, lines, cadict, caepi):
    """Crava quantidade/CA/material nos slots do EPI — RESUMO a partir das entregas do imprescrito.
    Idempotente; só preenche slots com entrega; preserva o segmento de cobertura."""
    entregas = _resumo_entregas(lines, cadict, caepi)
    if not entregas:
        return body
    prot, creme, luva, mask = [], [], [], []
    for e in entregas:
        ca, desc, qtd, ag, txt = e
        if 'solar' in txt and any(k in txt for k in ('creme', 'pomada', 'protet')):
            continue                                    # protetor solar não é EPI
        if 'creme' in txt or 'pomada' in txt:
            creme.append(e)
        elif ('luva' in txt and any(k in txt for k in _IMPERM_KW)
              and not any(k in txt for k in ('conjunto', 'macacão', 'macacao'))):
            luva.append(e)               # luva AVULSA impermeável (conjunto vai pro bloco C)
        elif any(k in txt for k in ('máscara', 'mascara', 'respirador', 'respiratór',
                                    'pff', 'semifacial', 'semi-facial')):
            mask.append(e)
        elif ag == 'Ruído (An.1)' or 'auric' in txt or 'auditiv' in txt:
            prot.append(e)

    if prot:
        body = _RES_PROT_RE.sub(lambda m: m.group(1) + _resumo_group(prot) + m.group(2), body, count=1)
    if creme:
        body = _RES_CREME_RE.sub(lambda m: m.group(1) + _resumo_group(creme, unit=' potes') + m.group(2), body, count=1)
    if luva:
        mats = [k for k in ('látex', 'latex', 'nitríl', 'nitril', 'pvc', 'vaqueta', 'raspa')
                if any(k in e[4] for e in luva)]
        matlabel = (' · ' + ' '.join('[X]%s' % m for m in mats)) if mats else ''
        fill = _resumo_group(luva) + matlabel
        body = _RES_LUVA_RE.sub(lambda m: m.group(1) + fill, body, count=1)
    if mask:
        pff = [p.upper() for p in ('pff1', 'pff2', 'pff3') if any(p in e[4] for e in mask)]
        cart = any(('cartucho' in e[4] or 'vapor' in e[4]) for e in mask)
        marks = ' '.join('[X]%s' % p for p in pff) + (' [X]cartucho VO' if cart else '')
        marklabel = (' · ' + marks.strip()) if marks.strip() else ''
        fill = _resumo_group(mask) + marklabel + _resumo_an7_note(mask)
        body = _RES_MASK_RE.sub(lambda m: m.group(1) + fill, body, count=1)

    # ---- Conjunto C (Defensivo An.13 + Umidade An.10) — marca peça presente + CA ----
    # Só preenche quando há um item de CONJUNTO na ficha (conjunto/macacão/pulverização/
    # hidrorepelente) — sinal forte do kit de pulverização/umidade; evita marcar a partir de peça
    # solta. Mesma luva/bota/resp servem aos dois agentes (perito decide qual aplica).
    def _find(*kws):
        for e in entregas:
            if any(k in e[4] for k in kws):
                return (e[0] if e[0] and e[0] != '—' else True)   # CA, ou True (achou sem CA)
        return None

    def _pc(label, *kws):
        hit = _find(*kws)
        ca = (' (CA %s)' % hit) if (hit and hit is not True) else ''
        return '%s[%s]%s' % (label, 'X' if hit else ' ', ca)

    def _pc_luva():
        for e in entregas:
            if 'luva' in e[4] and any(k in e[4] for k in _IMPERM_KW) and 'conjunto' not in e[4]:
                ca = (' (CA %s)' % e[0]) if (e[0] and e[0] != '—') else ''
                return 'luva[X]%s' % ca
        return 'luva[ ]'

    if _find('conjunto', 'macacão', 'macacao', 'pulveriz', 'hidrorepel'):
        defv = ' '.join([
            _pc('conjunto/pulveriz.', 'conjunto', 'macacão', 'macacao', 'pulveriz', 'hidrorepel'),
            _pc('bota', 'bota'), _pc_luva(),
            _pc('resp/PFF2', 'respirador', 'máscara', 'mascara', 'pff', 'respiratór'),
            _pc('viseira', 'viseira'),
            _pc('touca árabe', 'touca', 'árabe', 'arabe', 'capuz'),
        ])
        body = _RES_DEF_RE.sub(lambda m: m.group(1) + defv, body, count=1)
        umi = ' '.join([_pc('bota', 'bota'), _pc('avental', 'avental'), _pc_luva()])
        body = _RES_UMI_RE.sub(lambda m: m.group(1) + umi, body, count=1)

    # Frio An.9 — só com item de frio cold-specific (japona/balaclava). calça/luva/bota só contam
    # com contexto térmico/frio E excluindo 'altas temperaturas' (que é proteção a CALOR, não frio).
    _COLD = ('térmic', 'termic', 'frio', 'frigor')
    if _find('japona', 'balaclava'):
        def _frio(label, must, need_cold=False):
            for e in entregas:
                t = e[4]
                if must not in t or 'alta' in t:            # 'altas temperaturas' = calor, fora
                    continue
                if need_cold and not any(c in t for c in _COLD):
                    continue
                ca = (' (CA %s)' % e[0]) if (e[0] and e[0] != '—') else ''
                return '%s[X]%s' % (label, ca)
            return '%s[ ]' % label
        fri = ' '.join([
            _frio('japona', 'japona'), _frio('calça', 'calça', need_cold=True),
            _frio('luva', 'luva', need_cold=True), _frio('balaclava', 'balaclava'),
            _frio('bota', 'bota', need_cold=True),
        ])
        body = _RES_FRIO_RE.sub(lambda m: m.group(1) + fri, body, count=1)
    return body


# Linhas NR-6 guard-owned: o guard recalcula e reescreve. group(1) leva tudo até o "— ";
# group(2)=espaço entre Sim/Não; group(3)=" · obs:"; o resto é descartado.
NR6_FREQ_RE = re.compile(
    r'(Frequ[eê]ncia regular de fornecimento[^\n]*?[—-]\s*)\[[ X]\]Sim(\s+)\[[ X]\]N[aã]o(\s*·\s*obs:)[^\n]*$',
    re.I | re.M)
NR6_CA_RE = re.compile(
    r'(Anota[cç][aã]o do C\.A\., s[oó] EPI certific[aá]vel[^\n]*?[—-]\s*)\[[ X]\]Sim(\s+)\[[ X]\]N[aã]o(\s*·\s*obs:)[^\n]*$',
    re.I | re.M)


def fill_nr6_frequencia(body, cov_by_agent, gaps_by_agent):
    """Crava a linha NR-6 'Frequência regular de fornecimento' a partir da cobertura do guard
    (mesma fonte do slot 'cobre X/Y meses'): janela descoberta material → [X]Não + resumo do gap;
    cobertura contínua → [X]Sim. SEM dado de cobertura (sem protetor/creme na ficha) → não toca
    (perito decide). Step 2 NÃO preenche esta linha — deixa intacta do template; o guard a crava.
    Idempotente: recalcula a linha inteira a cada run; o guard é o dono desta linha."""
    if not cov_by_agent:
        return body
    gaps_by_agent = gaps_by_agent or {}
    gapped = {ag: st for ag, st in gaps_by_agent.items() if st and st.lstrip().startswith('⚠')}
    if gapped:
        mark_sim, mark_nao = ' ', 'X'
        obs = 'gap na ficha — ' + '; '.join(
            '%s: %s' % (ag, st.lstrip('⚠ ').strip()) for ag, st in gapped.items())
    else:
        mark_sim, mark_nao = 'X', ' '
        obs = 'cobertura contínua na ficha do imprescrito (ver 📐) — confirmar adequação in loco'

    def repl(m):
        return '%s[%s]Sim%s[%s]Não%s %s' % (
            m.group(1), mark_sim, m.group(2), mark_nao, m.group(3), obs)

    return NR6_FREQ_RE.sub(repl, body, count=1)


def fill_nr6_ca(body):
    """Crava a linha NR-6 'Anotação do C.A.' com base na ficha.

    Item certificável sem C.A. derruba a linha; item complementar/não-certificável sem C.A.
    não derruba. O guard é o dono desta linha.
    """
    rows = []
    for raw in body.splitlines():
        cells = split_row(raw)
        if not is_data_row(cells):
            continue
        rows.append((cells[-2], extract_ca(raw)))

    if not rows:
        return body

    cert_with_ca = []
    cert_missing_ca = []
    noncert_missing_ca = []
    for desc, ca in rows:
        if _is_certifiable(desc, ca):
            if ca:
                cert_with_ca.append((desc, ca))
            else:
                cert_missing_ca.append(desc)
        elif not ca:
            noncert_missing_ca.append(desc)

    if not cert_with_ca and not cert_missing_ca:
        return body

    if cert_missing_ca:
        mark_sim, mark_nao = ' ', 'X'
        exemplos = '; '.join(cert_missing_ca[:3])
        if len(cert_missing_ca) > 3:
            exemplos += '; ...'
        obs = ('há EPI certificável sem C.A. informado na ficha; conferir itens como: %s'
               % exemplos)
    else:
        mark_sim, mark_nao = 'X', ' '
        if noncert_missing_ca:
            exemplos = '; '.join(noncert_missing_ca[:4])
            if len(noncert_missing_ca) > 4:
                exemplos += '; ...'
            obs = ('C.A.s registrados nos EPIs certificáveis; itens sem C.A. remanescentes '
                   'aparecem como não-certificáveis/complementares (ex.: %s)' % exemplos)
        else:
            obs = 'C.A.s registrados nos EPIs certificáveis da ficha.'

    def repl(m):
        return '%s[%s]Sim%s[%s]Não%s %s' % (
            m.group(1), mark_sim, m.group(2), mark_nao, m.group(3), obs)

    return NR6_CA_RE.sub(repl, body, count=1)


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


# --- garantia do ROTEIRO de áudio no fim do formulário (boilerplate estático) ---
# O modelo às vezes DROPA a seção final "OBSERVAÇÕES GERAIS / ROTEIRO" ao montar o
# formulário (parece instrução, não conteúdo). Como é boilerplate fixo, garantimos de
# forma determinística — lendo do PRÓPRIO template (fonte única, sem drift). Marcador de
# idempotência: "Mnemônica: Agente" (só existe quando o ROTEIRO está completo).
ROTEIRO_MARK = 'Mnemônica: Agente'
OBS_HEADER = '▶ OBSERVAÇÕES GERAIS / IMPRESSÕES IN LOCO'
SEP = '━' * 20


def _roteiro_do_template():
    """Seção OBSERVAÇÕES GERAIS + ROTEIRO extraída do template (do header até o fim)."""
    tpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', 'prompts', 'template-formulario.md')
    try:
        with open(tpath, encoding='utf-8') as f:
            t = f.read()
    except OSError:
        return None
    i = t.find(OBS_HEADER)
    if i == -1:
        return None
    return SEP + '\n' + t[i:].rstrip('\n')


def ensure_roteiro_tail(body):
    """Garante que o formulário termine com OBSERVAÇÕES GERAIS + ROTEIRO. Se já está completo
    (marcador presente), não toca. Senão, descarta uma seção OBSERVAÇÕES parcial que tenha
    sobrado (header sem o ROTEIRO) e anexa o bloco canônico do template."""
    if ROTEIRO_MARK in body:
        return body
    bloco = _roteiro_do_template()
    if not bloco:
        return body
    lines = body.split('\n')
    cut = next((i for i, ln in enumerate(lines) if OBS_HEADER in ln), None)
    if cut is not None:                    # remove o header parcial + separador de abertura acima
        while cut > 0 and (not lines[cut - 1].strip() or set(lines[cut - 1].strip()) <= {'━'}):
            cut -= 1
        body = '\n'.join(lines[:cut])
    return body.rstrip() + '\n\n' + bloco + '\n'


# --- linha de EPI dentro da seção FLAGS PARA O PERITO (determinística) ---
# O Step 2 monta o FLAGS ANTES deste guard rodar → o modelo não tem o período descoberto
# (calculado aqui) na hora de preencher. Então o guard, dono do fato, injeta/atualiza a linha
# de EPI dentro do FLAGS. Idempotente: remove a anterior e reinsere logo após o cabeçalho.
FLAGS_HEADER = '🚩 FLAGS PARA O PERITO'
FLAGS_EPI_MARK = '↳ EPI (guard):'


def inject_flags_epi(body, summary):
    lines = body.split('\n')
    lines = [l for l in lines if not l.lstrip().startswith(FLAGS_EPI_MARK)]   # idempotência
    if not summary:
        return '\n'.join(lines)                  # sem gap → só limpa a linha antiga (se houver)
    h = next((i for i, l in enumerate(lines) if FLAGS_HEADER in l), None)
    if h is None:
        return '\n'.join(lines)                  # formulário sem seção FLAGS (template antigo) → no-op
    j = h                                        # insere após o separador ━ que fecha o cabeçalho
    for k in range(h + 1, min(h + 4, len(lines))):
        if lines[k].strip() and set(lines[k].strip()) <= {'━'}:
            j = k
            break
    lines.insert(j + 1, '%s %s' % (FLAGS_EPI_MARK, summary))
    return '\n'.join(lines)


def resolve_paths(args):
    # A base vem como argumento (diretório de conhecimento do perito-config.json). MAS no Cowork o
    # bash roda num sandbox que NÃO enxerga a pasta conectada do Google Drive → esse caminho não
    # existe p/ o script (item 1: mount do Cowork). Por isso mantemos uma BASE BUNDLED em
    # assets/04-EPIs (bash-visível, ao lado da skill) e caímos nela quando o caminho do --base é
    # inalcançável. No Claude Code nativo (bash vê o Drive) o --base vence e usa a base viva do perito;
    # no Cowork, a bundled assume — degradação graciosa, sem depender do mount.
    here = os.path.dirname(os.path.abspath(__file__))
    bundled_dir = os.path.join(here, 'assets', '04-EPIs')
    caepi_p = dicio_p = None
    for a in args:
        if os.path.isdir(a):
            caepi_p = caepi_p or os.path.join(a, '04-EPIs', 'caepi.sqlite')
            dicio_p = dicio_p or os.path.join(a, '04-EPIs', 'CA-dicionario.json')
        elif a.endswith(('.sqlite', '.db')):
            caepi_p = a
        elif a.endswith('.json'):
            dicio_p = a
    if not (caepi_p and os.path.exists(caepi_p)):
        fb = os.path.join(bundled_dir, 'caepi.sqlite')
        if os.path.exists(fb):
            caepi_p = fb
    if not (dicio_p and os.path.exists(dicio_p)):
        fb = os.path.join(bundled_dir, 'CA-dicionario.json')
        if os.path.exists(fb):
            dicio_p = fb
    return caepi_p, dicio_p


def _plugin_version():
    """Versão do plugin (de ../../.claude-plugin/plugin.json) — ecoada a cada run p/ o operador
    confirmar que está na última (o Cowork cacheia o clone, update é manual). Silencioso fora do
    layout do plugin (ex.: o squad do OS não tem plugin.json)."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(here, '..', '..', '.claude-plugin', 'plugin.json'), encoding='utf-8') as f:
            return json.load(f).get('version')
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print('uso: python3 check_epi.py <form.md> [<caepi.sqlite>] [<CA-dicionario.json>] [<base_dir>]')
        sys.exit(1)
    path = sys.argv[1]
    _v = _plugin_version()
    if _v:
        print('🔖 perito %s — confirme que é a última versão antes de confiar na extração' % _v)
    caepi_p, dicio_p = resolve_paths(sys.argv[2:])
    cadict = load_dict(dicio_p)
    caepi = Caepi(caepi_p)

    with open(path, encoding='utf-8') as f:
        text = f.read()
    body = strip_old_block(text)          # remove bloco anterior ANTES de processar (idempotência)
    src_lines = body.splitlines()
    classified, flags, nao_cat = process(src_lines, cadict, caepi)
    cob_res, faltou_vu, scoped, cov_by_agent, gaps_by_agent = cobertura(src_lines, cadict, caepi)
    # preenche o slot 'cobre __/__ meses' do EPI — RESUMO com o número + status de gap (gatilho ao
    # lado do checkbox; mesma régua do 📐), onde o perito lê e decide
    body = fill_inline_coverage(body, cov_by_agent, gaps_by_agent, _imprescrito_months(body))
    # crava quantidade/CA/material nos slots do EPI — RESUMO (Protetor/Creme/Luva/Máscara) a partir
    # das entregas do imprescrito — substitui o trabalho de consolidação que era do modelo (v1.34).
    # Não toca o segmento de cobertura preenchido acima.
    body = fill_resumo_items(body, src_lines, cadict, caepi)
    # crava a linha NR-6 'Anotação do C.A.' distinguindo EPI certificável de item complementar
    body = fill_nr6_ca(body)
    # crava a linha NR-6 'Frequência regular de fornecimento' a partir da MESMA cobertura/gaps:
    # gap material → [X]Não; contínuo → [X]Sim; sem ficha de protetor/creme → intacta (perito)
    body = fill_nr6_frequencia(body, cov_by_agent, gaps_by_agent)
    # garante o ROTEIRO de áudio no fim (o modelo às vezes dropa o boilerplate)
    body = ensure_roteiro_tail(body)
    # injeta o resumo de período descoberto na seção FLAGS (o Step 2 monta o FLAGS antes
    # deste guard calcular o gap; aqui o dado é cravado de forma determinística)
    _gap_lines = [l.lstrip() for l in cob_res if l.lstrip().startswith('⚠')]
    _gap_summary = ('; '.join(g.lstrip('⚠').strip().rstrip(':').strip() for g in _gap_lines)
                    if _gap_lines else None)
    body = inject_flags_epi(body, _gap_summary)

    age = caepi.age_days()
    stale = age is not None and age > 90

    if not classified and not flags and not nao_cat and not stale and not cob_res and not faltou_vu:
        # Ficha COM C.A. mas tudo mecânico/geral (nao_correlacionar na base) NÃO é
        # "ficha sem C.A.". É munição: a ré forneceu EPI, mas nenhum classifica p/
        # agente NR-15 (luva mecânica 8 fios, vestimenta, óculos, balaclava, botina).
        # Caso recorrente em perícia rural (An.13 agrotóxico / An.3 calor) — não enterrar.
        mecanicos = []
        for raw in src_lines:
            cells = split_row(raw)
            if is_data_row(cells) and extract_ca(raw):
                mecanicos.append(cells[-2].strip())
        if mecanicos:
            seen, exemplos = set(), []
            for d in mecanicos:
                k = d.lower()
                if k and k not in seen:
                    seen.add(k); exemplos.append(d)
            amostra = '; '.join(exemplos[:6]) + ('; …' if len(exemplos) > 6 else '')
            bloco_mec = [MARK + ' (C.A. é a chave — fonte: CA-dicionario + base oficial CAEPI; o nome NÃO classifica)\n',
                         '⚠ **%d entrega(s) com C.A. na ficha, mas NENHUMA classifica p/ agente NR-15** — todos mecânicos/gerais (%s).' % (len(mecanicos), amostra),
                         'Nenhum dos EPIs fornecidos é **barreira química (An.13)** nem **proteção térmica (An.3)**: a ré forneceu EPI, porém inadequado ao risco insalubre alegado. Confronte com os agentes presentes na diligência.']
            new_mec = insert_block(body, '\n'.join(bloco_mec))
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_mec)
            print('⚠ check_epi: %d entrega(s) com C.A., nenhuma classifica p/ agente NR-15 (todos mecânicos/gerais).' % len(mecanicos))
            sys.exit(0)
        bloco_vazio = [MARK + ' (C.A. é a chave — fonte: CA-dicionario + base oficial CAEPI; o nome NÃO classifica)\n',
                       '✅ Nenhuma entrega de EPI com C.A. na ficha — guard encerrado sem classificação.']
        new_empty = insert_block(body, '\n'.join(bloco_vazio))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_empty)
        print('✅ check_epi: nenhuma entrega de EPI com C.A. para classificar.')
        sys.exit(0)

    base_ok = caepi.con is not None
    bloco = [MARK + ' (C.A. é a chave — fonte: CA-dicionario + base oficial CAEPI; o nome NÃO classifica)\n']
    if not base_ok:
        bloco.append('🛑 **BASE EPI NÃO CARREGADA** — `caepi.sqlite` não encontrado/aberto em `%s`. '
                     'Nenhum C.A. foi classificado pela base oficial do MTE (só a regra de creme e o '
                     'dicionário curado agiram) — os "não catalogados" abaixo podem ser falso-negativo '
                     'de carga. Torne a base acessível ao script e rode de novo ANTES de fechar o laudo.\n'
                     % caepi_p)
    if classified:
        bloco.append('**🔧 Classificado pelo C.A. — use no quadro-resumo (ignora o nome comercial):**\n')
        bloco.append('| C.A. | Descrição (ficha) | Agente que protege | Fonte |')
        bloco.append('| :--- | :--- | :--- | :---: |')
        for ca, desc, agente, src in classified:
            bloco.append('| %s | %s | %s | %s |' % (ca, desc, agente, src))
    if flags:
        bloco.append('\n**🚩 Conferir:**')
        for trecho, msg in flags:
            bloco.append('- ⚠ `%s` → %s' % (trecho, msg))
    if nao_cat:
        bloco.append('\n**📇 C.A. NÃO CATALOGADOS** (nem no dicionário nem na base CAEPI — verificar e catalogar): '
                     + ', '.join(nao_cat))
    if cob_res:
        bloco.append('\n**📐 Cobertura (sugestão — só creme e protetor auditivo; confronte com os meses do imprescrito menos afastamentos, e o boletim do C.A.):**')
        for r in cob_res:
            bloco.append('- %s' % r)
        if not scoped:
            bloco.append('- ⚠ sem campo "Período imprescrito" nem divisória ▼ — cobertura sobre TODA a ficha (pode incluir histórico anterior ao imprescrito).')
    if faltou_vu:
        bloco.append('\nⓘ Vida útil não reconhecida (cobertura não calculada) p/: ' + ', '.join(faltou_vu)
                     + ' — informe o tipo (plug/concha/espuma) ou cadastre `vida_util_meses` por C.A.')
    if stale:
        bloco.append('\n**⏰ Base CAEPI com %d dias** (build %s) — re-baixe o RelatorioCA do MTE e rode `build_caepi_index.py`.'
                     % (age, caepi.build_date))
    new = insert_block(body, '\n'.join(bloco))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)

    for ca, desc, agente, src in classified:
        print('🔧 C.A. %s → %s [%s]' % (ca, agente, src))
    for trecho, msg in flags:
        print('🚩 %s → %s' % (trecho, msg))
    if nao_cat:
        print('📇 não catalogados: %s' % ', '.join(nao_cat))
    for r in cob_res:
        print('📐 %s' % r)
    if faltou_vu:
        print('ⓘ vida útil não reconhecida: %s' % ', '.join(faltou_vu))
    if stale:
        print('⏰ CAEPI desatualizado (%d dias)' % age)
    if not base_ok:
        print('🛑 check_epi: BASE EPI NÃO CARREGADA (%s) — classificação incompleta.' % caepi_p,
              file=sys.stderr)
    sys.exit(2 if flags else 0)


if __name__ == '__main__':
    main()
