#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_epi.py — guarda determinístico da classificação de EPI no formulário de campo.

Roda SOBRE o .md recém-gerado pelo Extrator. Varre as linhas de EPI e crava um
bloco "🚩 VERIFICAÇÃO AUTOMÁTICA DE EPI" DENTRO do próprio formulário quando
encontra classificação suspeita — não depende do modelo obedecer regra em prosa.

Falha de classe que isto barra (a perigosa): EPI classificado pela DIREÇÃO da
exclusão a partir do NOME COMERCIAL — ex.: creme "G3 Luz Negra" jogado em
radiação/UV (An.7), tirando-o do químico dérmico (An.13). Erro num documento que
o perito confia = laudo corrompido a jusante.

Sem dependências externas (só stdlib). Idempotente: remove o bloco anterior antes
de reescrever. Sai com código 2 quando há suspeita (para o alerta não passar batido).

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


def is_epi_line(ll, raw):
    """Linha provavelmente é uma classificação de EPI (limita o escopo do guard)."""
    if 'creme' in ll or 'pomada' in ll or 'capa' in ll:
        return True
    # menção a C.A. + dígitos = ficha/resumo de EPI
    if re.search(r'\bc\.?\s?a\.?\b', ll) and re.search(r'\d{3,6}', raw):
        return True
    return False


def analise(linhas):
    flags = []  # (trecho, mensagem)
    for raw in linhas:
        ll = raw.lower()
        if not is_epi_line(ll, raw):
            continue
        has_rad = any(t in ll for t in RAD)
        has_quim = any(t in ll for t in QUIM)
        has_umid = any(t in ll for t in UMID)
        is_creme = 'creme' in ll or 'pomada' in ll
        is_capa = 'capa' in ll or 'impermeáv' in ll or 'impermeav' in ll
        is_mask = any(t in ll for t in MASK)
        trecho = raw.strip()[:120]

        if is_creme and has_rad:
            flags.append((trecho, 'creme/pomada classificado em radiação/UV — creme protetor é QUÍMICO DÉRMICO (An.13), nunca An.7. Confira o C.A.'))
        elif is_creme and not has_quim:
            flags.append((trecho, 'creme/pomada sem classificação química explícita — creme protetor é An.13. Confirme o agente pelo C.A.'))
        elif has_rad and not is_mask:
            # radiação/UV só procede em máscara/lente/escudo de solda
            flags.append((trecho, 'EPI em radiação/UV sem ser máscara/lente/escudo de solda — nome comercial ≠ agente. Confirme o C.A.'))

        if is_capa and has_quim and not has_umid:
            flags.append((trecho, 'capa/impermeável classificada como químico — vestimenta impermeável protege UMIDADE (An.10). Confirme.'))
    # dedup preservando ordem
    seen, out = set(), []
    for f in flags:
        if f not in seen:
            seen.add(f); out.append(f)
    return out


def strip_old_block(text):
    """Remove um bloco de verificação anterior (idempotência em rerun)."""
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

    flags = analise(text.splitlines())
    text = strip_old_block(text)

    if not flags:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print('✅ check_epi: nenhuma classificação de EPI suspeita.')
        sys.exit(0)

    bloco = [MARK + ' (confira pelo C.A. antes de levar a campo)\n']
    bloco.append('> Classificação de EPI feita pelo NOME COMERCIAL é proibida — o que vale é a FUNÇÃO do C.A.\n')
    for trecho, msg in flags:
        bloco.append('- ⚠ `%s` → %s' % (trecho, msg))
    new = text.rstrip() + '\n\n' + '\n'.join(bloco) + '\n'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new)

    print('🚩 check_epi: %d classificação(ões) de EPI suspeita(s) — bloco cravado no formulário:' % len(flags))
    for trecho, msg in flags:
        print('  - %s → %s' % (trecho, msg))
    sys.exit(2)


if __name__ == '__main__':
    main()
