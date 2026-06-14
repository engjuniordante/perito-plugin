#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_epi.py — guarda determinístico da classificação de EPI no formulário de campo.

Roda SOBRE o .md recém-gerado pelo Extrator. Faz duas coisas, direto no arquivo:

  1) AUTO-CORRIGE o caso de regra ABSOLUTA: creme/pomada = sempre químico dérmico
     (An.13). Se vier em radiação/UV (ex.: creme "Luz Negra" -> An.7) ou sem classe
     química, o agente é reescrito para "Químico dérmico (An.13)" no próprio .md.
  2) MARCA (🚩) o que NÃO é regra absoluta — só o C.A. diz o certo: EPI jogado em
     radiação sem ser máscara/lente de solda, capa/impermeável virando químico, etc.

Por que corrige o creme e só marca o resto: a falha de classe é classificar pelo
NOME COMERCIAL, e a única classe 100% determinística é creme = An.13. Para os demais
o script não inventa o agente — aponta para o perito confirmar pelo C.A.

Sem dependências externas. Idempotente. Sai com código 2 quando resta algum 🚩.

uso: python3 check_epi.py <formulario-campo.md>
"""
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


def is_epi_line(ll, raw):
    """Linha provavelmente é uma classificação de EPI (limita o escopo do guard)."""
    if 'creme' in ll or 'pomada' in ll or 'capa' in ll:
        return True
    if CA_RE.search(ll) and re.search(r'\d{3,6}', raw):
        return True
    return False


def corrigir_creme(line):
    """Reescreve o segmento de AGENTE de uma linha de creme para An.13.
    Só atua quando a estrutura `... · AGENTE · C.A. nnnn · ...` é reconhecível
    (agente = segmento imediatamente antes do C.A.). Senão devolve None."""
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
    cand = parts[ca_idx - 1].lower()
    if 'creme' in cand or 'pomada' in cand:
        # segmento antes do C.A. é a própria descrição -> não há slot de agente: inserir
        parts.insert(ca_idx, AN13)
    else:
        parts[ca_idx - 1] = AN13
    return ' · '.join(parts)


def process(lines):
    """Devolve (novas_linhas, fixes, flags)."""
    new_lines, fixes, flags = [], [], []
    for raw in lines:
        ll = raw.lower()
        if not is_epi_line(ll, raw):
            new_lines.append(raw)
            continue
        has_rad = any(t in ll for t in RAD)
        has_quim = any(t in ll for t in QUIM)
        is_creme = 'creme' in ll or 'pomada' in ll
        trecho = raw.strip()[:120]
        line = raw

        # (1) AUTO-CORREÇÃO — creme/pomada = sempre An.13
        if is_creme and (has_rad or not has_quim):
            fixed = corrigir_creme(raw)
            if fixed is not None:
                fixes.append((trecho, 'creme/pomada → Químico dérmico (An.13) [regra absoluta]'))
                line = fixed
            else:
                flags.append((trecho, 'creme/pomada deveria ser Químico dérmico (An.13) — estrutura da linha não reconhecida, corrija manualmente.'))

        # (2) MARCAÇÃO — sobre a linha já (possivelmente) corrigida
        ll2 = line.lower()
        has_rad2 = any(t in ll2 for t in RAD)
        has_quim2 = any(t in ll2 for t in QUIM)
        has_umid2 = any(t in ll2 for t in UMID)
        is_mask2 = any(t in ll2 for t in MASK)
        is_creme2 = 'creme' in ll2 or 'pomada' in ll2
        is_capa2 = 'capa' in ll2 or 'impermeáv' in ll2 or 'impermeav' in ll2
        if has_rad2 and not is_mask2 and not is_creme2:
            flags.append((line.strip()[:120], 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — nome comercial ≠ agente. Confira o C.A.'))
        if is_capa2 and has_quim2 and not has_umid2:
            flags.append((line.strip()[:120], 'capa/impermeável classificada como químico — vestimenta impermeável protege UMIDADE (An.10). Confirme.'))

        new_lines.append(line)

    # dedup preservando ordem
    def dedup(xs):
        seen, out = set(), []
        for x in xs:
            if x not in seen:
                seen.add(x); out.append(x)
        return out
    return new_lines, dedup(fixes), dedup(flags)


def strip_old_block(text):
    idx = text.find(MARK)
    if idx == -1:
        return text.rstrip() + '\n'
    return text[:idx].rstrip() + '\n'


def main():
    if len(sys.argv) != 2:
        print('uso: python3 check_epi.py <formulario-campo.md>'); sys.exit(1)
    path = sys.argv[1]
    with open(path, encoding='utf-8') as f:
        text = f.read()

    new_lines, fixes, flags = process(text.splitlines())
    body = strip_old_block('\n'.join(new_lines))

    if not fixes and not flags:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(body)
        print('✅ check_epi: nenhuma classificação de EPI suspeita.')
        sys.exit(0)

    bloco = [MARK + ' (gerado pelo check_epi.py)\n']
    bloco.append('> Classificação de EPI pelo NOME COMERCIAL é proibida — vale a FUNÇÃO do C.A.\n')
    if fixes:
        bloco.append('**🔧 Corrigido automaticamente (regra absoluta — confira mesmo assim):**')
        for trecho, msg in fixes:
            bloco.append('- `%s` → %s' % (trecho, msg))
    if flags:
        bloco.append('\n**🚩 Confira pelo C.A. antes de levar a campo (não corrigi — só o C.A. diz o certo):**')
        for trecho, msg in flags:
            bloco.append('- ⚠ `%s` → %s' % (trecho, msg))
    new = body.rstrip() + '\n\n' + '\n'.join(bloco) + '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)

    if fixes:
        print('🔧 check_epi: %d correção(ões) automática(s) (creme → An.13):' % len(fixes))
        for trecho, _ in fixes:
            print('  - %s' % trecho)
    if flags:
        print('🚩 check_epi: %d classificação(ões) a confirmar pelo C.A.:' % len(flags))
        for trecho, msg in flags:
            print('  - %s → %s' % (trecho, msg))
    sys.exit(2 if flags else 0)


if __name__ == '__main__':
    main()
