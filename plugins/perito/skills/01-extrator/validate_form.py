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
- B3 campo obrigatório vazio: os campos que a EXTRAÇÃO preenche saíram preenchidos. Só os
  da extração — campo de medição, citação e participante vêm em branco DE PROPÓSITO (o
  perito preenche in loco), e exigi-los daria alarme falso em todo formulário novo.
- B4 formulário degradado: quando quase tudo saiu vazio, o problema não é campo faltando —
  é o bundle inteiro que não foi reconhecido (marcador ▶ fora do início da linha). Sem
  isto, um formulário em branco passava com VALIDAÇÃO OK desde que o nº do processo
  sobrevivesse.
- B5 quesitos perdidos na transcrição: o bundle TEM quesitos da parte e o formulário saiu
  com o texto de ausência. Compara com o BUNDLE, não com o próprio formulário — conferência
  que fecha com ela mesma não pega nada (foi assim que a caixinha do NLM vazou duas vezes).
- B6 quesito transcrito pela METADE: o B5 só via o bloco ZERADO. Um bloco que devia ter 30
  e saiu com 22 passava calado — a mesma forma do bug da ficha de EPI (razão agregada não
  enxerga perda parcial). Conta as linhas NUMERADAS dos dois lados e acusa o déficit. Só
  déficit: sobra é o perito completando à mão, que é o trabalho dele.
- B7 bloco DESCARTADO por rótulo não-médico: o bundle diz "não pertinente ao perito técnico"
  para um capítulo cujo título fala de ergonomia/NR-12/NR-17/segurança/acidente. Isso é do
  perito de ENGENHARIA — o descarte custou 30 quesitos no 0011183-33 (22/08/2026) e o B5 não
  viu, porque a perda foi DENTRO do bundle e formulário e bundle conferiam. Único check que
  olha o bundle contra si mesmo, e pode: o modelo declara na própria linha o que jogou fora.

Uso:
  python3 validate_form.py <formulario.md> <bundle.md>
"""
from __future__ import annotations

import re
import sys
import unicodedata
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
from montar_formulario import (_menos_cinco_anos, first_checked_label, get_by_prefix,
                               normalize_bundle, parse_quesitos, split_subsections)


PROC_RE = re.compile(r'\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}')

# ── B3/B4: campos que a EXTRAÇÃO preenche ────────────────────────────────────────────
# Ficam de fora, de propósito: medição (o perito mede in loco), CITAÇÕES (vêm em branco da
# extração por desenho), participantes além do reclamante, "Neutraliza?" e o laudo base.
# Exigir qualquer um deles daria VALIDAÇÃO FALHOU em todo formulário recém-montado.
# crítico=True → achado próprio; crítico=False → só conta para o B4.
CAMPOS_EXTRACAO = [
    ('Nº',                      True,  'sem ele não há como confirmar os autos'),
    ('Reclamante',              True,  'a tabela de identificação do laudo sai sem parte'),
    ('Reclamada',               True,  'a tabela de identificação do laudo sai sem parte'),
    ('Data da autuação / ação', True,  'é o marco do piso quinquenal — sem ela o imprescrito não se confere (B1d)'),
    ('Vara',                    False, ''),
    ('Data da diligência',      False, ''),
    ('Horário',                 False, ''),
    ('Local',                   False, ''),
]
# Valor que EXISTE mas não é conteúdo. "[NÃO LOCALIZADO]" é o montador dizendo que o NLM não
# achou — honesto e visível, mas para um campo crítico o formulário está quebrado do mesmo jeito.
VAZIOS = {'', '-', '—', '–', '_', '__', '___', '____', '[não localizado]', '[nao localizado]',
          'não localizado', 'nao localizado', 'n/a', 'na'}
TIPOS_LAUDO = ['Insalubridade + Periculosidade', 'Insalubridade', 'Periculosidade', 'Ergonomia']
# O que o montador escreve quando a extração não trouxe quesitos daquela parte.
AUSENCIA_QUESITO = ('não houve', 'nao houve', 'não encontrado', 'nao encontrado')


def _valor_campo(form_text, rotulo):
    """Valor do campo, ou None se o RÓTULO nem existe no formulário (coisa diferente de vazio).

    Tolera o negrito que o próprio template escreve em alguns rótulos
    ("- **Data da autuação / ação:** 26/01/2026").
    """
    m = re.search(r'^[\-\*•·]?[ \t]*\*{0,2}' + re.escape(rotulo) + r'\*{0,2}[ \t]*:[ \t]*\*{0,2}[ \t]*(.*)$',
                  form_text, re.M)
    if not m:
        return None
    return re.sub(r'\s*\*\(.*?\)\*\s*$', '', m.group(1)).strip()


def _vazio(v):
    return v is None or v.strip().lower() in VAZIOS


def _secao_form(form_text, titulo):
    """Bloco de uma seção do FORMULÁRIO ("## ▶ TIPO DE LAUDO ★"). Não dá pra usar o
    split_subsections aqui: ele exige o ▶ no início ABSOLUTO da linha, e no formulário o
    marcador vem depois do "## "."""
    m = re.search(r'^#{1,3}[ \t]*▶[ \t]*' + re.escape(titulo) + r'.*?$(.*?)(?=^#{1,3}[ \t]*▶|\Z)',
                  form_text, re.M | re.S)
    return m.group(1) if m else ''


def _bloco_quesito_form(form_text, titulo):
    """O bloco vai até o próximo heading de nível IRMÃO OU SUPERIOR — nunca até um subtítulo.

    A versão anterior fechava em qualquer `#{2,4}`, e um bloco que COMEÇA com subdivisão
    ("### Quesitos do Reclamante" seguido de "#### XIV — QUESITOS TÉCNICOS…", que é como a
    petição organiza quesitos em blocos numerados) era capturado vazio. Vazio virava "o
    formulário diz que não há" e o gate acusava perda de transcrição com os 30 quesitos
    intactos no arquivo — falso positivo medido no 0011183-33 (21/08/2026).
    """
    m = re.search(r'^(#{2,4})[ \t]*' + re.escape(titulo) + r'[ \t]*$', form_text, re.M)
    if not m:
        return None
    nivel = len(m.group(1))
    resto = form_text[m.end():]
    fim = re.search(r'^#{1,%d}[ \t]' % nivel, resto, re.M)
    return resto[:fim.start()] if fim else resto


def validate_campos_obrigatorios(form_text, findings):
    """B3 + B4 — campo da extração vazio, e o diagnóstico quando quase tudo saiu vazio."""
    vazios = []
    for rotulo, critico, porque in CAMPOS_EXTRACAO:
        v = _valor_campo(form_text, rotulo)
        if not _vazio(v):
            continue
        vazios.append(rotulo)
        if critico:
            como = 'rótulo ausente do formulário' if v is None else 'campo vazio'
            findings.append('Campo obrigatório "%s" não foi preenchido pela extração (%s) — %s.'
                            % (rotulo, como, porque))

    # Tipo de laudo: sem opção marcada o Redator não tem como escolher o template.
    tipo_block = _secao_form(form_text, 'TIPO DE LAUDO')
    if tipo_block and first_checked_label(tipo_block, TIPOS_LAUDO) < 0:
        vazios.append('TIPO DE LAUDO')
        findings.append('TIPO DE LAUDO sem nenhuma opção marcada — é ele que escolhe o template '
                        'do laudo; confira o PEDIDO da petição inicial no bundle.')

    # B4 — o diagnóstico. Campo isolado vazio é falta de dado; quase tudo vazio é OUTRA coisa.
    if len(vazios) >= 6:
        findings.append(
            '%d de %d campos da extração saíram vazios (%s) — isto não é dado faltando, é o '
            'BUNDLE que não foi reconhecido. Confira se os marcadores ▶ do bundle estão no '
            'início da linha (heading "### ▶", bullet "* ▶" e recuo já zeraram o formulário '
            'inteiro antes).' % (len(vazios), len(CAMPOS_EXTRACAO) + 1, ', '.join(vazios)))


def validate_quesitos(form_text, bundle_text, findings):
    """B5 — o bundle traz quesitos da parte e o formulário saiu com o texto de ausência.

    Só acusa nesse sentido. "Sobra" (formulário com quesito que o bundle não tem) fica de
    fora: seria acusar o perito de ter completado o formulário à mão, que é o trabalho dele.
    """
    sec = split_subsections(normalize_bundle(bundle_text))
    for chave, titulo in (('QUESITOS DO JUÍZO', 'Quesitos do Juízo'),
                          ('QUESITOS DO RECLAMANTE', 'Quesitos do Reclamante'),
                          ('QUESITOS DA RECLAMADA', 'Quesitos da Reclamada')):
        do_bundle = parse_quesitos(get_by_prefix(sec, chave))
        if not do_bundle or do_bundle.strip().lower().startswith(AUSENCIA_QUESITO):
            continue                      # o bundle não tem → ausência no form é correta
        bloco = _bloco_quesito_form(form_text, titulo)
        if bloco is None:
            findings.append('Bloco "%s" ausente do formulário, mas o bundle traz quesitos dessa '
                            'parte — a seção se perdeu na montagem.' % titulo)
            continue
        texto = bloco.strip().lower()
        if not texto or any(texto.startswith(k) for k in AUSENCIA_QUESITO):
            n = len([l for l in do_bundle.splitlines() if l.strip()])
            findings.append('"%s": o formulário diz que não há, mas o bundle traz %d linha(s) de '
                            'quesito — perdidos na transcrição, não ausentes dos autos. Confira '
                            'o bloco de quesitos do bundle.' % (titulo, n))


# ── B6/B7: quesito contado e quesito descartado ──────────────────────────────────────
# Linha de quesito numerada: "1. ", "12) ", "* 3. ", "- 7) ". Conta LINHAS, não números
# distintos — a numeração REINICIA a cada capítulo (XIII 1..30, XIV 1..30) e contar únicos
# esconderia exatamente a perda de um capítulo inteiro.
QUESITO_NUM_RE = re.compile(r'^[ 	]*(?:[-*+][ 	]+)?\d{1,3}[.)][ 	]', re.M)
# A linha com que o modelo anuncia que descartou um bloco.
DESCARTE_RE = re.compile(r'^.*n[aã]o pertinente ao perito t[eé]cnico.*$', re.M | re.I)
# O título do capítulo que a linha de descarte cita entre aspas. Preferir o TÍTULO à linha
# inteira evita o alarme falso do capítulo "XIII — QUESITOS À PERÍCIA MÉDICA E FUNCIONAL",
# que o modelo rotulou de "médica/ergonômica" na prosa embora seja clínico de ponta a ponta.
TITULO_CITADO_RE = re.compile(r'''["“”'](.+?)["“”']''')
# Matérias que são do perito de ENGENHARIA e nunca justificam descarte.
MATERIA_ENGENHARIA = ('ergonom', 'nr-17', 'nr 17', 'nr-12', 'nr 12', 'seguranca',
                      'maquina', 'acidente', 'reconstituicao', 'postural')
QTD_DECLARADA_RE = re.compile(r'(\d{1,3})\s+quesitos')


def _sem_acento(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower())
                   if unicodedata.category(c) != 'Mn')


def validate_quesitos_contagem(form_text, bundle_text, findings):
    """B6 — o bloco foi transcrito, mas incompleto.

    Mede na granularidade em que a perda acontece (a linha), não na razão agregada. Só
    compara quando o bundle tem numeração: bloco em prosa corrida não é mensurável e
    inventar régua ali daria alarme falso — que custa mais que o bug que pegaria.
    """
    sec = split_subsections(normalize_bundle(bundle_text))
    for chave, titulo in (('QUESITOS DO JUÍZO', 'Quesitos do Juízo'),
                          ('QUESITOS DO RECLAMANTE', 'Quesitos do Reclamante'),
                          ('QUESITOS DA RECLAMADA', 'Quesitos da Reclamada')):
        do_bundle = parse_quesitos(get_by_prefix(sec, chave)) or ''
        n_bundle = len(QUESITO_NUM_RE.findall(do_bundle))
        if n_bundle == 0:
            continue                      # sem numeração no bundle → nada a medir
        bloco = _bloco_quesito_form(form_text, titulo)
        if bloco is None:
            continue                      # bloco ausente já é achado do B5
        n_form = len(QUESITO_NUM_RE.findall(bloco))
        if n_form == 0:
            continue                      # bloco zerado já é achado do B5
        if n_form < n_bundle:
            findings.append('"%s": o bundle traz %d quesito(s) numerado(s) e o formulário só '
                            '%d — %d perdido(s) na transcrição. O bloco NÃO está vazio, por '
                            'isso o B5 não pega. Confira o bloco no bundle.'
                            % (titulo, n_bundle, n_form, n_bundle - n_form))


def validate_bloco_descartado(bundle_text, findings):
    """B7 — o modelo descartou um bloco que é do perito de ENGENHARIA.

    Perícia MÉDICA (lesão, nexo, incapacidade, CID) sai mesmo. Ergonomia (NR-17), segurança
    de máquinas (NR-12) e reconstituição de acidente NÃO — o plugin tem skill própria para
    ergonomia. Régua: o extrator TRANSCREVE, não TRIA.
    """
    for linha in DESCARTE_RE.findall(bundle_text):
        m = TITULO_CITADO_RE.search(linha)
        alvo = _sem_acento(m.group(1) if m else linha)
        materias = [k for k in MATERIA_ENGENHARIA if k in alvo]
        if not materias:
            continue                      # descarte de bloco médico: legítimo
        qtd = QTD_DECLARADA_RE.search(_sem_acento(linha))
        findings.append('Bundle descartou um bloco que é do perito de ENGENHARIA%s: %s. '
                        'Ergonomia/NR-12/NR-17/reconstituição de acidente são para '
                        'TRANSCREVER INTEIRO. Reextraia essa parte ou transcreva à mão.'
                        % (' (%s quesitos declarados)' % qtd.group(1) if qtd else '',
                           (m.group(1) if m else linha.strip())[:90]))


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
    validate_campos_obrigatorios(form_text, findings)
    validate_quesitos(form_text, bundle_text, findings)
    validate_quesitos_contagem(form_text, bundle_text, findings)
    validate_bloco_descartado(bundle_text, findings)

    if findings:
        print('VALIDAÇÃO FALHOU')
        for item in findings:
            print(f'- {item}')
        return 2

    print('VALIDAÇÃO OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
