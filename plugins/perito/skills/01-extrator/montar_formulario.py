#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""montar_formulario.py — consolida os 5 outputs do NotebookLM no formulario-pericia.md
do Eng. Irineu de FORMA DETERMINÍSTICA (script, zero token do modelo).

Substitui a consolidação feita pelo modelo (que escrevia ~340 linhas à mão, caro e sujeito
a drift de formato). O modelo passa a só salvar os 5 outputs do NLM num arquivo de bundle;
este script lê o bundle e CRAVA o formulário no template do Irineu. Depois o check_epi.py
roda por cima (classifica EPI por C.A., cobertura 📐, bloco 🚩).

Entrada: bundle .md com os 5 outputs do NLM em fluxo de subseções `▶ ...` (formato que o
perito já cola), SEM headers `## PARTE`. Re-templado para o formulário PRÓPRIO do Irineu.

uso: python3 montar_formulario.py <bundle.md> -o <saida.md> [--base <dir>] [--skip-guard]
"""
import argparse
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Piso 3.9 (anotações builtin) + stdout/err UTF-8: no Windows a saída capturada cai em
# cp1252 (Python <3.15) e um emoji do relatório mataria o script com UnicodeEncodeError.
if sys.version_info < (3, 9):
    sys.exit('Python 3.9+ é necessário (este ambiente tem %d.%d).' % sys.version_info[:2])
for _s in (sys.stdout, sys.stderr):
    if _s is not None and hasattr(_s, 'reconfigure'):
        _s.reconfigure(encoding='utf-8', errors='replace')

HERE = Path(__file__).resolve().parent
CHECK_EPI = HERE / "check_epi.py"
VALIDATE = HERE / "validate_form.py"

SUBSEC_RE = re.compile(r"^▶\s*(.+?)\s*$", re.M)
DATE_ROW_RE = re.compile(r"^\|\s*\d{2}/\d{2}/\d{4}\s*\|")
DIVISORIA = "▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO"
# EPI de admissão é entregue 0–poucos dias ANTES do início do imprescrito (= início do pacto,
# quando o contrato cabe inteiro na prescrição). Esta janela resgata a entrega de admissão sem
# readmitir histórico anterior. Espelha IMPRESC_GRACE_DAYS do check_epi.py.
IMPRESC_GRACE_DAYS = 31


# ── parsing do bundle (fluxo flat de ▶) ─────────────────────────────────────────
def split_subsections(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    matches = list(SUBSEC_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1).strip()] = text[start:end].strip()
    return out


def get_by_prefix(mapping: dict[str, str], prefix: str) -> str:
    pn = prefix.lower()
    for key, value in mapping.items():
        if key.lower().startswith(pn):
            return value
    return ""


def cleanup_value(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r"\s*\[[0-9][0-9,\-\s]*\]", "", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    return t.strip()


def bullet_value(block: str, label: str) -> str:
    m = re.search(rf"^[\-\*]?\s*{re.escape(label)}\s*:\s*(.+)$", block, re.M | re.I)
    return m.group(1).strip() if m else ""


def is_nao_localizado(v: str) -> bool:
    n = (v or "").lower()
    return any(k in n for k in ("não localizado", "nao localizado",
                                "não encontrado", "nao encontrado"))


def blank_if_nl(v: str) -> str:
    return "" if (not v or is_nao_localizado(v)) else cleanup_value(v)


def _iso(d: str) -> str:
    """DD/MM/AAAA → AAAA-MM-DD (comparável). Vazio/inválido → ''."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _menos_cinco_anos(d: str) -> str:
    """DD/MM/AAAA − 5 anos, em DD/MM/AAAA. Marco da prescrição quinquenal (CLT 7º XXIX).
    29/02 em ano-alvo não-bissexto → 28/02. Vazio/inválido → ''."""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", d or "")
    if not m:
        return ""
    dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3)) - 5
    try:
        return date(yy, mm, dd).strftime("%d/%m/%Y")
    except ValueError:
        return date(yy, mm, 28).strftime("%d/%m/%Y")


def clamp_imprescrito(periodo_impr: str, periodo_trab: str, data_acao: str = "") -> str:
    """Imprescrito DETERMINÍSTICO — ORDEM-INDEPENDENTE e com PISO QUINQUENAL calculado.
    A prescrição quinquenal (CLT 7º XXIX) recua até (ação−5 anos); não há vínculo — logo, nem
    exposição nem EPI — antes da admissão nem depois da demissão. O início legal é:
        início = max(admissão, ação−5 anos)   ·   fim = demissão
    Com a Data da ação disponível, o início é CONTA (piso = max[admissão, marco]), não palpite do NLM:
    contrato ≤5 anos → marco cai antes da admissão → pacto inteiro; >5 anos → o marco manda e um marco
    ERRADO do NLM dentro do contrato é forçado ao correto. Sem a Data da ação, cai no modo recorte:
    cada data clampada ao pacto, min=início/max=fim (imune à ordem do NLM — o bug VILCINEI era o marco
    cair na posição de 'fim' e inverter o período). Data única = marco de início → fim cai na demissão."""
    if not periodo_impr and not data_acao:
        return periodo_impr
    trab = re.findall(r"\d{2}/\d{2}/\d{4}", periodo_trab or "")
    adm = trab[0] if trab else ""
    dem = trab[-1] if len(trab) > 1 else ""
    # PISO QUINQUENAL determinístico: o início nunca recua além de (ação − 5 anos)
    acao = re.findall(r"\d{2}/\d{2}/\d{4}", data_acao or "")
    marco = _menos_cinco_anos(acao[0]) if acao else ""
    piso = adm
    if marco and (not adm or _iso(marco) > _iso(adm)):
        piso = marco
    impr = re.findall(r"\d{2}/\d{2}/\d{4}", periodo_impr)
    if not impr:
        if piso and dem:
            return f"de {piso} até {dem}"
        return periodo_impr

    def _clamp(d: str) -> str:
        di = _iso(d)
        if piso and di < _iso(piso):
            return piso
        if dem and di > _iso(dem):
            return dem
        return d

    clamped = [_clamp(d) for d in impr]
    if len(impr) == 1:
        ini, fim = clamped[0], (dem or clamped[0])
    else:
        ini, fim = min(clamped, key=_iso), max(clamped, key=_iso)
    # com a Data da ação, o início é cravado no piso (não confia no recorte do NLM p/ a ponta esquerda)
    if marco and piso:
        ini = piso
    return f"de {ini} até {fim}" if (ini and fim) else periodo_impr


def _reflow_flat_ficha(text: str) -> tuple[str, bool]:
    """Salvaguarda p/ quando o NotebookLM ACHATA a tabela da Parte 3a (devolve as entregas em prosa,
    sem os separadores `|`). O parser só lê linha markdown com pipe; achatado → zero linha → a TABELA
    sai vazia (parece 'EPI não carregou', mas é só formato). Aqui reconstruímos as entregas ANCORANDO
    NA DATA (a heurística que o perito faria à mão) e devolvemos a ficha em formato pipe — assim toda a
    lógica determinística a jusante (recorte do imprescrito, formatação, ACHADO) roda intacta.

    Reconstrução sem separador tem AMBIGUIDADE real (dígito de C.A. colado no campo seguinte) → o
    chamador marca a tabela como reconstruída p/ o perito conferir. NÃO inventa valor: C.A. ausente
    vira 'C.A. não informado'; descrição perdida vira placeholder explícito.

    NÃO dispara quando: já há linha tabular (pipe) · há <2 datas · a ficha foi declarada ausente."""
    if any(DATE_ROW_RE.match(ln.strip()) for ln in text.splitlines()):
        return text, False
    if re.search(r"N[ÃA]O\s+(?:LOCALIZAD|INDEXAD|H[ÁA]\s+FICHA)", text, re.I):
        return text, False
    dates = list(re.finditer(r"\b\d{2}/\d{2}/\d{4}\b", text))
    if len(dates) < 2:
        return text, False
    rebuilt = ["| Data de Entrega | Quantidade | Descrição do EPI | C.A. |",
               "| :--- | :---: | :--- | :---: |"]
    for i, m in enumerate(dates):
        data = m.group(0)
        end = dates[i + 1].start() if i + 1 < len(dates) else len(text)
        seg = text[m.end():end].strip(" \t\r\n|·—–-,;")
        qm = re.match(r"(\d{1,4})(?:\s*(?:un|und|par|pares|p[çc]|p[çc]s|pc|pcs)\b)?\s+", seg, re.I)
        if qm:
            qtd, resto = qm.group(1), seg[qm.end():].strip()
        else:
            qtd, resto = "1", seg
        cam = re.search(r"(\d{3,6})\s*$", resto)
        if cam:
            ca, desc = cam.group(1), resto[:cam.start()].strip(" ·—–-,;")
        else:
            ca, desc = "C.A. não informado", resto.strip(" ·—–-,;")
        desc = desc or "[descrição não recuperada — conferir ficha]"
        rebuilt.append(f"| {data} | {qtd} | {desc} | {ca} |")
    return "\n".join(rebuilt), True


def parse_ficha_rows(ficha_block: str, impr_start: str = "", contract_end: str = "") -> list[str]:
    """Linhas da ficha (tabela markdown) → bullets '- Data · Qtd · Descrição · CA NNN', recortadas
    ao período imprescrito.

    Recorte por DATA, igual ao check_epi.py: mantém a entrega cuja data cai em
    [início_imprescrito − GRACE, demissão]. `impr_start`/`contract_end` chegam do `periodo_impr`
    DETERMINÍSTICO (clamp_imprescrito: max(admissão, ação−5anos) … demissão) — NÃO do marcador ▼ do
    NLM. Fecha o ponto cego do montador: dependendo só do ▼, se o NLM não o emitia a tabela inundava
    com histórico pré-vínculo, e a EPI de admissão acima do ▼ sumia (sem janela de graça). FALLBACK
    gracioso: sem janela determinística, volta ao recorte legado pelo ▼.

    FICHA 100% PRÉ-IMPRESCRITO: ficha COM entregas mas TODAS fora da janela → o recorte legítimo
    zera a tabela. Em vez de devolver vazio (que parece 'EPI não carregou'), emite uma linha de
    ACHADO explícita — a ficha não neutraliza o período em análise."""
    ficha_block, reflowed = _reflow_flat_ficha(ficha_block)  # recupera ficha achatada pelo NLM
    rows: list[str] = []
    all_dates: list[str] = []
    win_lo = ""
    win_hi = _iso(contract_end)
    if impr_start:
        try:
            win_lo = (datetime.strptime(impr_start, "%d/%m/%Y").date()
                      - timedelta(days=IMPRESC_GRACE_DAYS)).isoformat()
        except ValueError:
            win_lo = ""
    deterministic = bool(win_lo)

    after_split = False
    divider_seen = DIVISORIA in ficha_block
    for raw in ficha_block.splitlines():
        if DIVISORIA in raw:
            after_split = True
            continue
        if DATE_ROW_RE.match(raw.strip()):
            cells = [c.strip() for c in raw.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            data, qty, desc, ca = cells[0], cells[1], cells[2], cells[3]
            all_dates.append(data)
            if deterministic:
                di = _iso(data)
                if not di or di < win_lo or (win_hi and di > win_hi):
                    continue
            elif divider_seen and not after_split:
                continue  # legado: sem janela determinística, recorta pelo ▼
            qty_fmt = qty if re.search(r"[A-Za-zÀ-ÿ]", qty) else f"{qty}un"
            if not ca or "não informado" in ca.lower() or "nao informado" in ca.lower():
                ca_fmt = "CA não informado"
            else:
                ca_fmt = f"CA {ca}"
            rows.append(f"- {data} · {qty_fmt} · {desc} · {ca_fmt}")

    if deterministic and not rows and all_dates:
        isos = sorted(d for d in map(_iso, all_dates) if d)
        if isos:
            def _br(iso: str) -> str:
                return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}"
            n = len(all_dates)
            faixa = _br(isos[0]) if n == 1 else f"{_br(isos[0])}–{_br(isos[-1])}"
            if isos[-1] < win_lo:
                rows.append(
                    f"- ⚠ NENHUMA entrega de EPI no período imprescrito: as {n} entregas da ficha "
                    f"({faixa}) são todas ANTERIORES ao início do imprescrito ({impr_start}) — "
                    f"a ficha não neutraliza o período em análise.")
            else:
                rows.append(
                    f"- ⚠ NENHUMA das {n} entregas da ficha ({faixa}) cai no período imprescrito "
                    f"({impr_start} … {contract_end or 'contrato em curso'}) — não neutraliza o período.")
    if reflowed and rows:
        rows.insert(0, "- ⚠ ATENÇÃO — a tabela de EPI veio ACHATADA do NotebookLM (sem separadores) e foi "
                       "RECONSTRUÍDA automaticamente por âncora de data. CONFIRA cada C.A. e descrição "
                       "contra a ficha original antes de fechar o laudo.")
    return rows


def parse_nr6_table(block: str) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for raw in block.splitlines():
        if not raw.strip().startswith("|"):
            continue
        cols = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cols) < 3 or cols[0].lower().startswith("responsabilidade") or set(cols[0]) <= {":", "-", " "}:
            continue
        out[cols[0]] = cols[1].replace("[", "").replace("]", "").strip().upper() == "X"
    return out


def nr6_yesno(nr6: dict[str, bool], *keywords: str) -> tuple[str, str]:
    for label, sim in nr6.items():
        ll = label.lower()
        if any(k in ll for k in keywords):
            return ("X" if sim else " ", " " if sim else "X")
    return (" ", " ")


def parse_quesitos(block: str) -> str:
    lines = []
    for raw in block.splitlines():
        s = raw.rstrip()
        if not s.strip():
            continue
        if s.strip().startswith("*(") and s.strip().endswith(")*"):
            continue
        lines.append(re.sub(r"\s*\[[0-9][0-9,\-\s]*\]", "", s))
    txt = "\n".join(lines).strip()
    return "" if (is_nao_localizado(txt) or not txt) else txt


def parse_identificacao(block: str) -> list[dict[str, str]]:
    out = []
    for raw in block.splitlines():
        if not raw.strip().startswith("|"):
            continue
        cols = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cols) < 6 or cols[0].lower() == "função" or set("".join(cols)) <= {":", "-", " "}:
            continue
        out.append({"funcao": cols[0], "setor": cols[1], "inicio": cols[2],
                    "termino": cols[3], "autuacao": cols[4], "imprescrito": cols[5]})
    return out


def first_checked_label(block: str, options: list[str]) -> int:
    # App de nota (Notas do iPhone etc.) achata os checkboxes num parágrafo só. Restaura a quebra
    # antes de cada [ ]/[x] que não esteja no início da linha, pra cada opção cair em linha própria.
    block = re.sub(r"(?<!^)(\[\s*[ xX]\s*\])", r"\n\1", block, flags=re.M)
    for raw in block.splitlines():
        m = re.match(r"^\s*[\-\*]?\s*\[\s*[xX]\s*\]\s*(.+)$", raw)
        if m:
            txt = m.group(1).lower()
            for i, opt in enumerate(options):
                if opt.lower() in txt:
                    return i
    return -1


def mark(cond: bool) -> str:
    return "X" if cond else " "


# ── render: template do Irineu ───────────────────────────────────────────────────
# ── pré-triagem de agentes → checkbox determinístico (paridade com build_agente_section do squad) ──
# O script marca [X] Presente no Status quando a pré-triagem (Parte 3b) trouxe base documental p/ o
# agente; o modelo NÃO escreve prosa no Status. Assim o perito mantém o checkbox pra flipar in loco e
# o redator lê a marca, não uma alegação. Match do agente pelo NOME (tolerante ao rótulo do NLM; NÃO
# uso "An.1" que é substring de "An.10..14"); miss → deixa em branco (avaliar in loco), nunca erra.
_AGENTE_NEEDLES = [
    ("RUÍDO", ("ruído",)),
    ("CALOR", ("calor",)),
    ("RADIAÇÕES NÃO IONIZANTES", ("não ionizante",)),
    ("VIBRAÇÕES", ("vibra",)),
    ("FRIO", ("frio",)),
    ("UMIDADE", ("umidade",)),
    ("LIMITES DE TOLERÂNCIA", ("quantitativo",)),
    ("POEIRAS MINERAIS", ("poeira",)),
    ("CONTATO DÉRMICO", ("qualitativo", "dérmico")),
    ("BIOLÓGICOS", ("biológico",)),
]


def parse_agentes(block: str) -> dict[str, str]:
    """Bloco PRÉ-TRIAGEM DE AGENTES → {rótulo do agente: valor}. Valor traz '[Presente — …]' ou '— …'."""
    out: dict[str, str] = {}
    for raw in block.splitlines():
        m = re.match(r"^[-•*]\s*([^:]+):\s*(.+)$", raw.strip())
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


def _agente_present(agentes: dict[str, str], needles: tuple[str, ...]) -> bool:
    for key, val in agentes.items():
        kl = key.lower()
        if any(n in kl for n in needles):
            return "[presente" in val.lower()
    return False


def prefill_agentes(form: str, agentes: dict[str, str]) -> str:
    """Marca [X] Presente no Status dos agentes que a pré-triagem trouxe com base documental (e
    [X] Aplicável na periculosidade). Só o checkbox — o Obs fica pro modelo (Fase 2). Sem base → o
    Status fica intacto (vazio) p/ o perito marcar in loco."""
    if not agentes:
        return form
    lines = form.split("\n")
    needles: tuple[str, ...] | None = None
    peric = False
    for i, line in enumerate(lines):
        if line.startswith("### ") or line.startswith("## ▶"):
            up = line.upper()
            needles, peric = None, False
            if "PERICULOSIDADE" in up:
                needles, peric = ("periculosidade",), True
            else:
                for hdr, nd in _AGENTE_NEEDLES:
                    if hdr in up:
                        needles = nd
                        break
            continue
        if not needles:
            continue
        s = line.strip()
        if not peric and s == "- Status: [ ] Ausente  [ ] Presente":
            if _agente_present(agentes, needles):
                lines[i] = "- Status: [ ] Ausente  [X] Presente"
            needles = None
        elif peric and s == "- Status: [ ] Não aplicável  [ ] Aplicável":
            if _agente_present(agentes, needles):
                lines[i] = "- Status: [ ] Não aplicável  [X] Aplicável"
            needles = None
    return "\n".join(lines)


def build_form(bundle_path: Path) -> str:
    text = bundle_path.read_text(encoding="utf-8")
    # O NLM às vezes formata headers/labels/células em **negrito** ("▶ **PROCESSO...**", "- **Nº:**").
    # Neutraliza o negrito UMA vez na ingestão p/ nenhum campo silenciar por formatação (senão a chave
    # da seção vira "**PROCESSO" e o get_by_prefix devolve vazio, travando o form). Paridade c/ o squad.
    text = text.replace("**", "")
    sec = split_subsections(text)

    proc = get_by_prefix(sec, "PROCESSO E EMPRESA")
    ident_block = get_by_prefix(sec, "IDENTIFICAÇÃO")
    tipo_block = get_by_prefix(sec, "TIPO DE LAUDO")
    ambiente_block = get_by_prefix(sec, "DESCRIÇÃO DO AMBIENTE")
    afast_block = get_by_prefix(sec, "AFASTAMENTOS")
    ativ_block = get_by_prefix(sec, "ATIVIDADES POR FUNÇÃO")
    cit_block = get_by_prefix(sec, "CITAÇÕES")
    part_block = get_by_prefix(sec, "PARTICIPANTES")
    ficha_block = text[text.find("ORIGEM DA FICHA"):] if "ORIGEM DA FICHA" in text else text
    evid_block = get_by_prefix(sec, "EVIDÊNCIAS DOCUMENTAIS")
    nr6_block = get_by_prefix(sec, "NR-6")
    escopo_block = get_by_prefix(sec, "ESCOPO DA AVALIAÇÃO")
    q_juizo = parse_quesitos(get_by_prefix(sec, "QUESITOS DO JUÍZO"))
    q_recte = parse_quesitos(get_by_prefix(sec, "QUESITOS DO RECLAMANTE"))
    q_recda = parse_quesitos(get_by_prefix(sec, "QUESITOS DA RECLAMADA"))

    numero = cleanup_value(bullet_value(proc, "Nº"))
    vara = cleanup_value(bullet_value(proc, "Vara"))
    # "Autuação" pode vir com parêntese antes do ':' (ex.: "Autuação (data de propositura): 26/01/2026")
    m_aut = re.search(r"Autua[cç][aã]o[^:]*:\s*(.+)$", proc, re.M | re.I)
    autuacao = cleanup_value(m_aut.group(1)) if m_aut else cleanup_value(bullet_value(proc, "Data da ação"))
    reclamante = cleanup_value(bullet_value(proc, "Reclamante"))
    reclamada = cleanup_value(bullet_value(proc, "Reclamada"))
    cnae = cleanup_value(bullet_value(proc, "CNAE da atividade principal"))
    data_dilig = blank_if_nl(bullet_value(proc, "Data da diligência"))
    horario = blank_if_nl(bullet_value(proc, "Horário"))
    local = blank_if_nl(bullet_value(proc, "Local"))

    tipo_idx = first_checked_label(tipo_block, [
        "insalubridade + periculosidade", "periculosidade", "insalubridade", "ergonomia"])
    tipo_map = {0: 2, 1: 1, 2: 0, 3: 3}
    tipo_marks = [" ", " ", " ", " "]
    if tipo_idx in tipo_map:
        tipo_marks[tipo_map[tipo_idx]] = "X"

    amb_idx = first_checked_label(ambiente_block, ["imóvel comercial", "fabril", "ambiente externo", "outro"])
    amb_marks = [" ", " ", " ", " "]
    if 0 <= amb_idx < 4:
        amb_marks[amb_idx] = "X"

    ident = parse_identificacao(ident_block)
    ident_lines = [
        f"- Função: {r['funcao']} · Setor: {r['setor']} · de {r['inicio']} a {r['termino']} "
        f"· Autuação: {r['autuacao']} · Imprescrito: {r['imprescrito']}" for r in ident]
    if not ident_lines:
        ident_lines = ["- Função: ____ · Setor: ____ · de ____ a ____ · Autuação: ____ · Imprescrito: ____"]
    ident_render = "\n".join(ident_lines)
    periodo_trab = cleanup_value(bullet_value(ident_block, "Período trabalhado")) \
        or cleanup_value(bullet_value(ident_block, "Período trabalhado (geral)"))
    periodo_impr = clamp_imprescrito(
        cleanup_value(bullet_value(ident_block, "Período imprescrito")), periodo_trab, autuacao)

    esc_idx = first_checked_label(escopo_block, ["todo o período", "somente o período imprescrito"])
    esc_marks = [" ", " "]
    if 0 <= esc_idx < 2:
        esc_marks[esc_idx] = "X"

    ultimo_line = next((l for l in afast_block.splitlines() if "Último dia efetivamente trabalhado" in l), "")
    ultimo_dia = blank_if_nl(re.sub(r"^.*?Último dia efetivamente trabalhado[^:]*:\s*", "", ultimo_line, flags=re.I))

    ativ_recte = blank_if_nl(bullet_value(ativ_block, "Descrição passo a passo (versão do Reclamante na Inicial)")) \
        or blank_if_nl(bullet_value(ativ_block, "Descrição passo a passo das atividades (versão do Reclamante na Inicial)"))
    ativ_recda = blank_if_nl(bullet_value(ativ_block, "Descrição (versão da Reclamada na Contestação / divergências, se houver)")) \
        or blank_if_nl(bullet_value(ativ_block, "Descrição (versão da Reclamada na Contestação"))

    cit_recte = blank_if_nl(bullet_value(cit_block, "Reclamante disse"))
    cit_recda = blank_if_nl(bullet_value(cit_block, "Reclamada disse"))
    cit_parad = blank_if_nl(bullet_value(cit_block, "Paradigma (se houver)"))

    part_recte = ""
    for raw in part_block.splitlines():
        if raw.strip().lower().startswith("reclamante:"):
            part_recte = cleanup_value(raw.split(":", 1)[1])
            break
    part_recte = part_recte or reclamante

    treino_line = next((l for l in evid_block.splitlines() if "treinamento de uso de epi" in l.lower()), "")
    controle_line = next((l for l in evid_block.splitlines() if "controle de entrega" in l.lower()), "")
    treino_sim = bool(re.search(r"\[\s*[xX]\s*\]\s*Sim", treino_line))
    controle_sim = bool(re.search(r"\[\s*[xX]\s*\]\s*Sim", controle_line))
    # Janela do imprescrito DETERMINÍSTICA (não depende do ▼ do NLM): início = 1ª data do
    # periodo_impr (max(admissão, ação−5anos)); fim = demissão. Mesmo anchor do check_epi.
    _impr_dates = re.findall(r"\d{2}/\d{2}/\d{4}", periodo_impr)
    _impr_ini = _impr_dates[0] if _impr_dates else ""
    _impr_fim = _impr_dates[-1] if len(_impr_dates) > 1 else ""
    ficha_rows = parse_ficha_rows(ficha_block, _impr_ini, _impr_fim)
    ficha_render = "\n".join(ficha_rows) if ficha_rows else "- ____ · ____ · ____ · CA ____"

    nr6 = parse_nr6_table(nr6_block)
    f_s, f_n = nr6_yesno(nr6, "ficha de epi", "registro do fornecimento")
    ca_s, ca_n = nr6_yesno(nr6, "anota")
    tr_s, tr_n = nr6_yesno(nr6, "treinamento")
    fr_s, fr_n = nr6_yesno(nr6, "frequ")

    form = TEMPLATE.format(
        numero=numero, vara=vara, data_dilig=data_dilig, horario=horario, local=local,
        autuacao=autuacao, part_recte=part_recte, cnae=cnae,
        amb0=amb_marks[0], amb1=amb_marks[1], amb2=amb_marks[2], amb3=amb_marks[3],
        tipo0=tipo_marks[0], tipo1=tipo_marks[1], tipo2=tipo_marks[2], tipo3=tipo_marks[3],
        reclamante=reclamante, reclamada=reclamada, ident=ident_render,
        periodo_trab=periodo_trab or "de ____ até ____", periodo_impr=periodo_impr or "de ____ até ____",
        esc0=esc_marks[0], esc1=esc_marks[1], ultimo_dia=ultimo_dia or "____",
        ativ_recte=ativ_recte, ativ_recda=ativ_recda,
        cit_recte=cit_recte, cit_recda=cit_recda, cit_parad=cit_parad,
        treino_s=mark(treino_sim), treino_n=mark(not treino_sim),
        controle_s=mark(controle_sim), controle_n=mark(not controle_sim),
        ficha=ficha_render,
        nr6_f_s=f_s, nr6_f_n=f_n, nr6_ca_s=ca_s, nr6_ca_n=ca_n,
        nr6_tr_s=tr_s, nr6_tr_n=tr_n, nr6_fr_s=fr_s, nr6_fr_n=fr_n,
        q_juizo=q_juizo or "Não houve.",
        q_recte=q_recte or "Não encontrado no PJE.",
        q_recda=q_recda or "Não encontrado no PJE.",
    )
    # Pré-marca [X] Presente no Status dos agentes que a pré-triagem trouxe com base documental
    # (determinístico, paridade com o squad) — o modelo só refina o Obs na Fase 2.
    agentes = parse_agentes(get_by_prefix(sec, "PRÉ-TRIAGEM"))
    return prefill_agentes(form, agentes)


# Template do Irineu com slots {}. Mantém a estrutura/rótulos do formulario-pericia.md
# (o redator 02 lê estes rótulos). Agentes A–M e Periculosidade ficam EM BRANCO para o
# perito preencher in loco; o check_epi.py crava o bloco 🚩 e a cobertura 📐 depois.
TEMPLATE = """# FORMULÁRIO DE PERÍCIA — Eng. Irineu de Freitas Branco Junior

> **Fonte-mestra de dados.** Consolidado pelo script (montar_formulario.py) a partir dos 5 outputs do NotebookLM; o perito completa em loco os campos `[NÃO LOCALIZADO]`/em branco. Depois, a Skill 2/3 (Redatores) lê este formulário para montar o laudo.

---

## ▶ TIPO DE LAUDO ★
- [{tipo0}] Insalubridade → `template-insalubridade.docx`
- [{tipo1}] Periculosidade → `template-periculosidade.docx`
- [{tipo2}] Insalubridade + Periculosidade → `template-insal-peric.docx`
- [{tipo3}] Ergonomia → `template-ergonomico.docx`

## ▶ LAUDO BASE (opcional)
Laudo Base: (O perito irá colocar o laudo base caso tenha)

---

## ▶ PROCESSO
- Nº: {numero}
- Vara: {vara}
- Data da diligência: {data_dilig}
- Horário: {horario}
- Local: {local}
- **Data da autuação / ação:** {autuacao}

## ▶ HONORÁRIOS *(manual — arbitrado pelo perito)*
- Valor (R$): 5.800,00
- Valor por extenso: Cinco mil e oitocentos reais

## ▶ PARTICIPANTES
*(Nome / Papel — uma linha por pessoa; o Reclamante é preenchido na extração, os demais em loco)*

Nome: {part_recte}
Papel: Reclamante

Nome:
Papel:

Nome:
Papel:

---

## ▶ EMPRESA / ESTABELECIMENTO
- CNAE da atividade principal da Reclamada: {cnae}

### Descrição do ambiente de trabalho *(marcar com X)*
- [{amb0}] Imóvel comercial, feito em alvenaria, apresenta ventilação e iluminação natural e artificial.
- [{amb1}] Fabril/industrial feito em alvenaria e estruturas metálicas, apresenta ventilação e iluminação natural e artificial.
- [{amb2}] Trabalho em ambiente externo.
- [{amb3}] Outro:

---

## ▶ RECLAMANTE
- Reclamante: {reclamante}
- Reclamada: {reclamada}

### Identificação / vínculo *(uma linha por função — alimenta a tabela de identificação do laudo)*
{ident}

- Período trabalhado: {periodo_trab}
- Turno: `[interno]`
- **Período imprescrito ★:** {periodo_impr}

### ▶ Escopo da avaliação *(conforme ata — vai ao laudo)*
- [{esc0}] Será avaliado **todo o período laboral**. Esse geralmente é para laudo ergonomico apenas
- [{esc1}] Será avaliado **somente o período imprescrito** (últimos 5 anos da propositura da ação). Aplicável para insalubridade e periculosidade.

### ▶ Afastamentos / períodos a excluir
*(> 15 dias no imprescrito: acidente, doença, auxílio-doença, licença, suspensão/COVID. **Nunca contar férias.**)*

★ **Último dia efetivamente trabalhado** (FECHA a exposição — data mais importante): {ultimo_dia}  ·  Houve retorno? [ ] Sim  [ ] Não → rescisão em ____

**Afastamento 1:**
- Último dia efetivamente trabalhado antes do afastamento: ____
- Benefício previdenciário (espécie + datas): de ____ até ____
- Limbo previdenciário / suspensão (se houve): de ____ até ____
- Retorno efetivo às atividades: ____

---

## ▶ ATIVIDADES POR FUNÇÃO
*(descrever passo a passo o que o trabalhador faz; uma sub-lista por função/período)*

**Versão do Reclamante (Inicial):** {ativ_recte}

**Versão da Reclamada (Contestação):** {ativ_recda}

## ▶ CITAÇÕES / DEPOIMENTOS *(campo de campo — preencher in loco; vem EM BRANCO da extração, salvo se a ata já trouxer depoimento)*
**Reclamante disse:** {cit_recte}

**Reclamada disse:** {cit_recda}

**Paradigma (se houver):** {cit_parad}

---

## ▶ EPIs FORNECIDOS
- Evidenciado treinamento de uso de EPI? [{treino_s}] Sim  [{treino_n}] Não
- Evidenciado controle de entrega (ficha assinada)? [{controle_s}] Sim  [{controle_n}] Não

### Fornecimento de EPIs *(uma entrega por linha — alimenta a tabela de EPI do laudo)*
*(formato: Data · Qtd · Descrição do EPI · C.A.)*
{ficha}

Observações sobre os EPIs:

### EPI — RESUMO por agente `[interno]` *(pré-cálculo do Extrator — apoio à decisão do perito; o VEREDICTO de neutralização é do perito in loco)*
> A **cobertura** (Σ qtd × vida útil) é calculada pelo `check_epi.py` — bloco 📐 (só creme e protetor auditivo; demais = perito). Aqui o perito **confronta** com os meses do imprescrito (menos afastamentos) e dá o veredicto. Só entram agentes com EPI que protege; calor e periculosidade não têm EPI neutralizante; **biológico não é elidido por EPI**. **Nunca calcular cobertura em prosa** — usar o 📐 do script.

**A) Conta fecha** (cobertura = bloco 📐 do `check_epi.py`):
- Protetor auditivo (ruído An.1): __ un · CA __ · cobre __/__ meses · [ ]✓ [ ]⚠ gap [ ]✗
- Creme (óleo/álcali An.13): __ potes · cobre __/__ meses · [ ]✓ [ ]⚠ [ ]✗

**B) Conta + perito decide:**
- Luva imperm.: __ pares · __ material (látex/nitríl./PVC)
- Máscara/resp.: __ un · [ ]PFF1 [ ]PFF2 [ ]PFF3 [ ]cartucho VO

**C) Conjunto (falta 1 derruba — perito confirma adequação):**
- Umidade An.10: bota[ ] avental[ ] luva[ ]
- Defensivo An.13: conjunto/pulveriz.[ ] bota[ ] luva[ ] resp/PFF2[ ] viseira[ ] touca árabe[ ]
- Frio An.9: __ peças (japona/calça/luva/balaclava/bota)
- Solda An.7: lente tonalidade __

Fora do quadro (sem EPI que neutraliza): calor · periculosidade · biológico (luva "proteção bio" NÃO elide — não testada p/ vírus).

> Veredicto final (Neutralizado [ ]Sim [ ]Não + motivo) é marcado por agente na seção abaixo, a partir deste quadro + áudio.

### NR-6 — Comprovação *(alimenta a tabela NR-6 do laudo; pré-preenchível pela skill na extração)*

> 🔄 = extrator pré-preenche (documentável) · 👤 = **perito decide in loco** (deixar em branco na extração)

*(Responsabilidade da Reclamada — marcar Sim/Não)*
- Ficha de EPI — registro do fornecimento 🔄 — [{nr6_f_s}] Sim  [{nr6_f_n}] Não
- Anotação do respectivo C.A. 🔄 — [{nr6_ca_s}] Sim  [{nr6_ca_n}] Não
- Treinamento e orientação 🔄 — [{nr6_tr_s}] Sim  [{nr6_tr_n}] Não
- Frequência regular de fornecimento 🔄 — [{nr6_fr_s}] Sim  [{nr6_fr_n}] Não
- Adequado ao risco ambiental 👤 (perito) — [ ] Sim  [ ] Não
- Fiscalização do uso 👤 (perito) — [ ] Sim  [ ] Não

---

## ▶ AGENTES — INSALUBRIDADE (NR-15)
> Bloco fixo dos anexos NR-15 (A–M) — **avaliar in loco**. Status em branco = avaliar in loco.

### A. RUÍDO (Anexos 1 e 2)
- Status: [ ] Ausente  [ ] Presente
- Equipamento: Dosímetro de ruído
- Nível medido (dB):
- Tempo de exposição (h/dia):
- Limite NR-15 Anexo 1: 85 dB
- Neutralizado pelo EPI: [ ] Sim  [ ] Não
- C.A. do protetor auditivo:
- Vida útil conforme boletim técnico:
- Utilizado valor de PPP ou PGR? [ ] Sim  [ ] Não
- Obs:

### B. CALOR (Anexo 3)
- Status: [ ] Ausente  [ ] Presente
- Equipamento: Termômetro de globo e bulbo úmido
- IBUTG medido:
- Taxa metabólica:
- Atividade: [ ] Leve  [ ] Moderada  [ ] Pesada
- Limite de tolerância NR-15 Anexo 3:
- Utilizado valor de PPP? [ ] Sim  [ ] Não
- Obs:

### C. ILUMINAÇÃO (Anexo 4)
*Revogado pela Portaria 3.751/1990. [não preencher]*

### D. RADIAÇÕES IONIZANTES (Anexo 5)
- Status: [ ] Ausente  [ ] Presente
- Fonte:
- Obs:

### E. PRESSÕES ANORMAIS / CONDIÇÕES HIPERBÁRICAS (Anexo 6)
- Status: [ ] Ausente  [ ] Presente
- Obs:

### F. RADIAÇÕES NÃO IONIZANTES (Anexo 7)
- Status: [ ] Ausente  [ ] Presente
- Tipo: [ ] UV — solda  [ ] IR  [ ] Laser  [ ] Outro:
- Tipo de soldagem / amperagem:
- Tonalidade da lente fornecida (C.A.):
- Obs:

### G. VIBRAÇÕES (Anexo 8)
- Status: [ ] Ausente  [ ] Presente
- Tipo: [ ] Mãos/braços  [ ] Corpo inteiro
- Equipamento:
- Obs:

### H. FRIO (Anexo 9)
- Status: [ ] Ausente  [ ] Presente
- Câmara: [ ] Resfriados  [ ] Congelados
- Temperatura (°C):
- Número de entradas por jornada:
- Tempo de permanência em cada entrada:
- EPI térmico adequado: [ ] Sim  [ ] Não
- Obs:

### I. UMIDADE (Anexo 10)
- Status: [ ] Ausente  [ ] Presente
- Obs:

### J. AGENTES QUÍMICOS — Limites de Tolerância (Anexo 11)
- Status: [ ] Ausente  [ ] Presente
- Agente(s):
- Contato dérmico? [ ] Sim  [ ] Não
- Concentração medida:
- EPI: ver bloco EPI — RESUMO (An.11)
- Obs:

### K. POEIRAS MINERAIS (Anexo 12)
- Status: [ ] Ausente  [ ] Presente
- Agente(s):
- EPI: ver bloco EPI — RESUMO (An.12)
- Concentração:
- Obs:

### L. AGENTES QUÍMICOS — Contato Dérmico (Anexo 13)
- Status: [ ] Ausente  [ ] Presente
- Agente(s):
- [ ] Óleos e graxas minerais — Qual:
- [ ] Álcalis cáusticos — Qual:
- [ ] Outros:
- EPI: ver bloco EPI — RESUMO (An.13)
- Obs:

### M. AGENTES BIOLÓGICOS (Anexo 14)
- Status: [ ] Ausente  [ ] Presente
- Atividade(s):
- [ ] Limpeza de banheiros de grande circulação
- [ ] Período de COVID-19 (pandemia) — De: ____ até: ____
- [ ] SAMU / Enfermeiros / Técnicos de enfermagem
- Obs:

---

## ▶ PERICULOSIDADE (NR-16)
- Status: [ ] Não aplicável  [ ] Aplicável
- Qual anexo (se aplicável):
  - [ ] Anexo 1 — Explosivos
  - [ ] Anexo 2 — Inflamáveis
  - [ ] Anexo 3 — Violência física / segurança pessoal ou patrimonial
  - [ ] Anexo 4 — Energia elétrica
  - [ ] Anexo 5 — Motocicleta (Portaria MTE nº 1.565/2014)
  - [ ] Anexo (*) — Radiações ionizantes / substâncias radioativas
- Obs:

---

## ▶ ERGONOMIA (NR-17)
> **Preencher somente se a ata de audiência designar perícia ergonômica.**

- Designada perícia ergonômica pela ata? [ ] Sim  [ ] Não
- Posto(s)/atividade(s) a avaliar:
- Planilha de avaliação ergonômica preenchida? [ ] Sim  [ ] Não
- Obs:

---

## ▶ DOCUMENTOS COLETADOS `[interno]`
- [ ] PPP
- [ ] Documentos ambientais (LTCAT / PGR / PPRA)
- [ ] Fichas de EPI
- [ ] Ordem de serviço
- Obs:

---

## ▶ REGISTRO FOTOGRÁFICO
*(descrever cada foto — as imagens são inseridas manualmente no laudo; estas descrições viram as legendas)*
- Foto 01:
- Foto 02:
- Foto 03:
- Foto 04:
- Foto 05:
- Foto 06:

---

## ▶ QUESITOS

### Quesitos do Juízo
{q_juizo}

### Quesitos do Reclamante
{q_recte}

### Quesitos da Reclamada
{q_recda}

---

## ▶ OBSERVAÇÕES GERAIS / IMPRESSÕES IN LOCO (DITADO) `[subsídio]`
> Dite no Notas do iPhone e cole o texto aqui. **Complementa** as atividades já descritas e dá a **direção** da conclusão.

🎙️ **Em ~1 min, diga:**
1. O que constatei in loco (o que complementa as atividades e o ambiente).
2. Divergências que pesam, se houver.
3. Para onde aponta a conclusão e por quê.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle", help="bundle .md com os 5 outputs do NotebookLM (fluxo ▶)")
    ap.add_argument("-o", "--output", required=True, help="arquivo final .md")
    ap.add_argument("--skip-guard", action="store_true", help="não roda check_epi.py")
    ap.add_argument("--skip-validate", action="store_true", help="não roda validate_form.py (gate)")
    ap.add_argument("--base", default=None, help="diretório da base de conhecimento (04-EPIs)")
    args = ap.parse_args()

    bundle_path = Path(args.bundle).resolve()
    if not bundle_path.exists():
        raise SystemExit(f"bundle não encontrado: {bundle_path}")

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_form(bundle_path), encoding="utf-8")
    print(out_path)

    if not args.skip_guard:
        cmd = [sys.executable, str(CHECK_EPI), str(out_path)]
        if args.base:
            cmd.append(args.base)
        subprocess.run(cmd, check=False)
    # gate determinístico (após o guard, que carimba o form) — invariantes de imprescrito/processo/guard
    if not args.skip_validate:
        subprocess.run([sys.executable, str(VALIDATE), str(out_path), str(bundle_path)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
