#!/usr/bin/env python3
"""Gate determinístico do formulário montado (paridade com o squad do OS).

Substitui a "auto-validação Claude-side" (que gastava token do modelo) por checagem
determinística — 0 token, falha dura (exit 2) que barra regressão silenciosa. Esta
primeira camada trava as INVARIANTES de maior risco; os checks acoplados ao conteúdo
(quesito/NR-6/cobertura inline) dependem do formato exato do montar e entram depois.

Checks:
- B1 sanidade do imprescrito: tem de caber DENTRO do contrato (início≥admissão,
  fim≤demissão, início≤fim). O montar/guard já clampam; o gate dá observabilidade e
  trava regressão do clamp ou edição manual.
- B2 identidade do processo: nº no formulário tem de bater com o do bundle (form
  montado sobre o bundle errado é catastrófico e silencioso).
- guard-block: o guard determinístico de EPI (check_epi) de fato rodou e carimbou o form.

Uso:
  python3 validate_form.py <formulario.md> <bundle.md>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Piso 3.9 (anotações builtin) + stdout/err UTF-8: no Windows a saída capturada cai em
# cp1252 (Python <3.15) e um emoji do relatório mataria o script com UnicodeEncodeError.
if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_epi as ce
from montar_formulario import _menos_cinco_anos


PROC_RE = re.compile(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}')


def validate_imprescrito_sanity(form_text: str, findings: list[str]) -> None:
    """B1 — o imprescrito tem de caber DENTRO do contrato. A prescrição quinquenal recua até
    (ação−5 anos), mas não há vínculo (logo, nem exposição nem EPI) antes da admissão nem depois
    da demissão. Sem 'Período trabalhado' (contrato em curso/incompleto) → não dá pra recortar →
    no-op. Determinístico, 0 token."""
    mi = ce.IMPRESCRITO_RE.search(form_text)
    mt = ce.PERIODO_TRAB_RE.search(form_text)
    if not (mi and mt):
        return
    impr_a, impr_b = ce.first_date_iso(mi.group(1))[0], ce.first_date_iso(mi.group(2))[0]
    adm, dem = ce.first_date_iso(mt.group(1))[0], ce.first_date_iso(mt.group(2))[0]
    if impr_a and impr_b and impr_a > impr_b:
        findings.append(f'Imprescrito invertido: início {mi.group(1)} > fim {mi.group(2)}.')
    if impr_a and adm and impr_a < adm:
        findings.append(f'Imprescrito começa ANTES da admissão (início {mi.group(1)} < admissão {mt.group(1)}) '
                        '— recorte ao contrato falhou; denominador/gap de EPI inflam.')
    if impr_b and dem and impr_b > dem:
        findings.append(f'Imprescrito termina DEPOIS da demissão (fim {mi.group(2)} > demissão {mt.group(2)}) '
                        '— sem exposição após a saída; recorte ao contrato falhou.')
    # B1d — piso quinquenal: havendo Data da ação, o início TEM de ser max(admissão, ação−5 anos).
    # Pega divergência do NLM (marco errado dentro do contrato, que as 3 travas de bound não veem).
    ma = re.search(r'Data da ação:\s*(\d{2}/\d{2}/\d{4})', form_text)
    if ma and impr_a and adm:
        marco_br = _menos_cinco_anos(ma.group(1))
        marco = ce.first_date_iso(marco_br)[0]
        if marco:
            piso, piso_br = (marco, marco_br) if marco > adm else (adm, mt.group(1)[:10])
            if impr_a != piso:
                findings.append(f'Imprescrito-início {mi.group(1)} ≠ piso quinquenal '
                                f'max[admissão {mt.group(1)[:10]}, ação {ma.group(1)}−5a={marco_br}] = {piso_br} '
                                '— conferir Data da ação × marco; possível erro do NLM no início.')


def validate_process_identity(form_text: str, bundle_text: str, findings: list[str]) -> None:
    """B2 — o nº do processo no formulário tem de bater com o do bundle. Determinístico, 0 token."""
    pf = PROC_RE.search(form_text)
    pb = PROC_RE.search(bundle_text)
    if not pf:
        findings.append('Nº do processo ausente no formulário (não foi possível confirmar a identidade dos autos).')
        return
    if pb and pf.group(0) != pb.group(0):
        findings.append(f'Nº do processo DIVERGE entre formulário ({pf.group(0)}) e bundle ({pb.group(0)}) '
                        '— possível montagem sobre o bundle errado.')


def validate_guard_block(form_text: str, findings: list[str]) -> None:
    """O guard determinístico de EPI (check_epi) tem de ter rodado e carimbado o formulário."""
    if ce.MARK not in form_text:
        findings.append('Bloco de verificação automática de EPI (guard) não foi encontrado no formulário final.')


def main() -> int:
    if len(sys.argv) != 3:
        print('uso: python3 validate_form.py <formulario.md> <bundle.md>')
        return 1

    form_text = Path(sys.argv[1]).read_text(encoding='utf-8')
    bundle_text = Path(sys.argv[2]).read_text(encoding='utf-8')

    findings: list[str] = []
    validate_imprescrito_sanity(form_text, findings)
    validate_process_identity(form_text, bundle_text, findings)
    validate_guard_block(form_text, findings)

    if findings:
        print('VALIDAÇÃO FALHOU')
        for item in findings:
            print(f'- {item}')
        return 2

    print('VALIDAÇÃO OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
