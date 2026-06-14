#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_epi.py — guarda determinístico da classificação de EPI no formulário de campo.

Roda SOBRE o .md recém-gerado pelo Extrator. O C.A. é a CHAVE PRIMÁRIA: o nome
comercial NUNCA define o agente. Faz, direto no arquivo:

  1) LOOKUP por C.A. no CA-dicionario.json (fonte primária): se o C.A. consta,
     reescreve o agente da linha pelo valor do dicionário — IGNORA o nome do produto.
  2) REGRA ABSOLUTA (C.A. fora do dicionário): creme/pomada = químico dérmico
     (An.13). Exceção: "protetor solar" é o caso real de solar/UV — NÃO força An.13.
  3) MARCA (🚩) o que só o C.A. resolve (EPI em radiação sem ser máscara/lente de
     solda; capa virando químico) e lista os C.A. NÃO CATALOGADOS (para entrar no
     dicionário antes de fechar o laudo).

Por que C.A. = chave: o nome engana (marca, idioma, nome técnico incomum). O C.A. é
único e estável. Lookup no script (não na prosa do modelo) = à prova do modelo
contornar a regra.

Sem dependências externas. Idempotente. Sai com código 2 quando resta 🚩.

uso: python3 check_epi.py <formulario-campo.md> [<CA-dicionario.json>]
"""
import json
import re
import sys

MARK = '## 🚩 VERIFICAÇÃO AUTOMÁTICA DE EPI'

RAD = ('radiaç', 'radiac', 'rni', 'não ioniz', 'nao ioniz', 'ultraviolet',
       'luz negra', 'an.7', 'an. 7', 'anexo 7', 'anexo nº 7', 'anexo n 7')
QUIM = ('quím', 'quim', 'an.13', 'an. 13', 'anexo 13', 'anexo nº 13', 'dérm',
        'derm', 'óleo', 'oleo', 'graxa', 'álcali', 'alcali', 'solvente')
UMID = ('umidade', 'an.10', 'an. 10', 'anexo 10')
MASK = ('máscara', 'mascara', 'lente', 'viseira', 'escudo', 'facial',
        'solda', 'soldad', 'capuz')
AN13 = 'Químico dérmico (An.13)'
CA_RE = re.compile(r'c\.?\s?a\.?', re.I)
CA_NUM_RE = re.compile(r'c\.?\s?a\.?[\s:nº.\-]*(\d{3,6})', re.I)


def load_dict(path):
    if not path:
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return {}
    out = {}
    for k, v in raw.items():
        if k.startswith('_'):
            continue
        key = re.sub(r'\D', '', str(k))
        if key:
            out[key] = v
    return out


def extract_ca(line):
    m = CA_NUM_RE.search(line)
    return m.group(1) if m else None


def is_epi_line(ll, raw):
    if 'creme' in ll or 'pomada' in ll or 'capa' in ll:
        return True
    if CA_RE.search(ll) and re.search(r'\d{3,6}', raw):
        return True
    return False


def set_agent_segment(line, new_agent):
    """Reescreve o segmento de AGENTE (o imediatamente antes do C.A.). Se só há a
    descrição antes do C.A. (sem slot de agente), INSERE. Devolve None se a
    estrutura `... · ... · C.A. nnnn · ...` não for reconhecível."""
    parts = line.split(' · ')
    if len(parts) < 2:
        return None
    ca_idx = None
    for i, p in enumerate(parts):
        if CA_RE.search(p) and re.search(r'\d{3,6}', p):
            ca_idx = i
            break
    if ca_idx is None or ca_idx < 1:
        return None
    if ca_idx >= 2:
        parts[ca_idx - 1] = new_agent      # já existe slot de agente -> sobrescreve
    else:
        parts.insert(ca_idx, new_agent)    # só a descrição antes do C.A. -> insere
    return ' · '.join(parts)


def process(lines, cadict):
    new_lines, fixes, flags = [], [], []
    nao_catalogados = []
    for raw in lines:
        ll = raw.lower()
        if not is_epi_line(ll, raw):
            new_lines.append(raw)
            continue
        trecho = raw.strip()[:120]
        line = raw
        ca = extract_ca(raw)

        # (1) LOOKUP por C.A. — fonte primária, ignora o nome
        if ca and ca in cadict:
            agente = cadict[ca].get('agente') or AN13
            fixed = set_agent_segment(raw, agente)
            if fixed is not None:
                if fixed != raw:
                    fixes.append((trecho, 'C.A. %s → %s [dicionário]' % (ca, agente)))
                line = fixed
            new_lines.append(line)
            continue

        # C.A. presente mas fora do dicionário -> catalogar
        if ca:
            nao_catalogados.append(ca)

        ll2 = line.lower()
        has_rad = any(t in ll2 for t in RAD)
        has_quim = any(t in ll2 for t in QUIM)
        is_creme = 'creme' in ll2 or 'pomada' in ll2
        is_solar = 'solar' in ll2

        # (2) REGRA ABSOLUTA — creme/pomada = An.13 (exceto protetor solar)
        if is_creme and not is_solar and (has_rad or not has_quim):
            fixed = set_agent_segment(raw, AN13)
            if fixed is not None:
                fixes.append((trecho, 'creme/pomada → %s [regra absoluta]' % AN13))
                line = fixed
            else:
                flags.append((trecho, 'creme/pomada deveria ser %s — estrutura da linha não reconhecida, corrija manualmente.' % AN13))

        # (3) MARCAÇÃO — sobre a linha já (possivelmente) corrigida
        ll3 = line.lower()
        has_rad3 = any(t in ll3 for t in RAD)
        has_quim3 = any(t in ll3 for t in QUIM)
        has_umid3 = any(t in ll3 for t in UMID)
        is_mask3 = any(t in ll3 for t in MASK)
        is_creme3 = 'creme' in ll3 or 'pomada' in ll3
        is_solar3 = 'solar' in ll3
        is_capa3 = 'capa' in ll3 or 'impermeáv' in ll3 or 'impermeav' in ll3
        if has_rad3 and not is_mask3 and not is_creme3 and not is_solar3:
            flags.append((line.strip()[:120], 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — nome comercial ≠ agente. Confira o C.A.'))
        if is_capa3 and has_quim3 and not has_umid3:
            flags.append((line.strip()[:120], 'capa/impermeável classificada como químico — vestimenta impermeável protege UMIDADE (An.10). Confirme.'))

        new_lines.append(line)

    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    return new_lines, dedup(fixes), dedup(flags), dedup(nao_catalogados)


def strip_old_block(text):
    idx = text.find(MARK)
    if idx == -1:
        return text.rstrip() + '\n'
    return text[:idx].rstrip() + '\n'


def main():
    if len(sys.argv) not in (2, 3):
        print('uso: python3 check_epi.py <formulario-campo.md> [<CA-dicionario.json>]'); sys.exit(1)
    path = sys.argv[1]
    cadict = load_dict(sys.argv[2] if len(sys.argv) == 3 else None)
    with open(path, encoding='utf-8') as f:
        text = f.read()

    new_lines, fixes, flags, nao_cat = process(text.splitlines(), cadict)
    body = strip_old_block('\n'.join(new_lines))

    if not fixes and not flags and not nao_cat:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        print('✅ check_epi: nenhuma classificação de EPI suspeita.')
        sys.exit(0)

    bloco = [MARK + ' (gerado pelo check_epi.py — C.A. é a chave, o nome NÃO classifica)\n']
    if fixes:
        bloco.append('**🔧 Classificado/corrigido automaticamente (confira mesmo assim):**')
        for trecho, msg in fixes:
            bloco.append('- `%s` → %s' % (trecho, msg))
    if flags:
        bloco.append('\n**🚩 Confira pelo C.A. (não corrigi — só o C.A. diz o certo):**')
        for trecho, msg in flags:
            bloco.append('- ⚠ `%s` → %s' % (trecho, msg))
    if nao_cat:
        bloco.append('\n**📇 C.A. NÃO CATALOGADOS** (classifique e adicione ao `CA-dicionario.json` antes de fechar o laudo): ' + ', '.join(nao_cat))
    new = body.rstrip() + '\n\n' + '\n'.join(bloco) + '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)

    if fixes:
        print('🔧 check_epi: %d classificação(ões) por C.A./regra:' % len(fixes))
        for trecho, msg in fixes:
            print('  - %s → %s' % (trecho, msg))
    if flags:
        print('🚩 check_epi: %d a confirmar pelo C.A.:' % len(flags))
        for trecho, msg in flags:
            print('  - %s → %s' % (trecho, msg))
    if nao_cat:
        print('📇 C.A. não catalogados (adicionar ao dicionário): %s' % ', '.join(nao_cat))
    sys.exit(2 if flags else 0)


if __name__ == '__main__':
    main()
