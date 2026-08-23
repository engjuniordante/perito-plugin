#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrai_processo.py — fatia MECÂNICA do Modo B da skill 01b-extrator-nlm.

Pega os 4 PDFs de uma pasta de processo, cria um notebook EFÊMERO no
NotebookLM (via o CLI `nlm`, sem passar pelo modelo), sobe as 4 fontes
esperando indexar, roda os 5 prompts de extração (Partes 1, 2, 3a, 3b, 4)
ENCADEADOS no mesmo conversation_id, limpa as citações [n], grava o
_bundle-<nº>.md e APAGA o notebook. Zero token de modelo.

Dois modos:
  • UMA pasta:  python extrai_processo.py "<pasta com os 4 PDFs>"
  • LOTE (fila): python extrai_processo.py --lote ["<pasta-mãe>"]
      Processa CADA subpasta (nº do processo) da pasta-mãe em fila; a cada
      sucesso MOVE a subpasta para "<pasta-mãe>/Processados/". Sem argumento,
      a pasta-mãe sai de config.notebooklm.pasta_processos.

Depois, quem chama (a skill / o perito) roda o montar_formulario.py sobre cada
bundle. O bundle basta para o pipeline — o notebook não é mais necessário —,
por isso é seguro apagá-lo assim que o bundle é gravado.

Saída: para cada pasta processada imprime "BUNDLE: <caminho>". Sai com código
!= 0 se a (única) pasta falhar; em lote, segue a fila e resume no fim.
"""
import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
import time
import zlib
from pathlib import Path

# ── console UTF-8 (Windows cp1252 quebra com emoji/acentos) ──────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# PDFs que ficam na mesma pasta mas NÃO são entrada (são saída do fluxo).
DENYLIST = ("formulario", "formulário", "laudo")
# Nome da subpasta de destino no modo lote.
DIR_PROCESSADOS = "Processados"
# Limite prático de tamanho por mensagem de query do NotebookLM (~4.8k chars).
LIMITE_QUERY = 4700

# As partes na ordem do bundle + a chave de cada heading no arquivo de prompts.
PARTES = [
    ("REGRAS", r"REGRAS\s+GERAIS"),
    ("P1", r"PARTE\s+1\b"),
    ("P2", r"PARTE\s+2\b"),
    ("P3a", r"PARTE\s+3a\b"),
    ("P3b", r"PARTE\s+3b\b"),
    ("P4", r"PARTE\s+4\b"),
]
ORDEM = ["P1", "P2", "P3a", "P3b", "P4"]


def log(msg):
    print(msg, flush=True)


class FalhaPasta(RuntimeError):
    """Falha ao processar uma pasta; carrega o id do notebook mantido (se houver)."""
    def __init__(self, msg, notebook_id=None):
        super().__init__(msg)
        self.notebook_id = notebook_id


# ── localizar o executável nlm ────────────────────────────────────────────────
def achar_nlm(explicit=None):
    if explicit:
        if Path(explicit).exists():
            return explicit
        sys.exit(f"ERRO: --nlm apontado não existe: {explicit}")
    found = shutil.which("nlm")
    if found:
        return found
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        for py in ("Python312", "Python311", "Python313", "Python310"):
            cand = Path(appdata) / "Python" / py / "Scripts" / "nlm.exe"
            if cand.exists():
                return str(cand)
    sys.exit("ERRO: não encontrei o executável `nlm`. Rode `nlm login` uma vez ou passe --nlm <caminho>.")


# ── localizar e ler o perito-config.json (subindo a partir do caminho) ────────
def achar_config(caminho):
    p = Path(caminho).resolve()
    for cand in [p, *p.parents]:
        cfg = cand / "perito-config.json"
        if cfg.exists():
            return cfg
    return None


# ── extrair os blocos de prompt do arquivo .md ────────────────────────────────
# Cópia BUNDLED dos prompts, ao lado da skill. Mesmo idioma da base CAEPI do check_epi: o
# arquivo VIVO (config/--prompts, no Drive do perito) vence sempre; a bundled é a rede quando
# ele não é alcançável — o bash do Cowork não enxerga a pasta do Drive.
# Ela também é o que torna o contrato prompt↔parser TESTÁVEL: até a v1.1.2 os prompts moravam
# só no Drive, fora do git, e tirar um marcador ▶ de lá não acendia nenhum dos testes — o
# sintoma seria formulário vazio, não erro.
PROMPTS_BUNDLED = Path(__file__).resolve().parent / "assets" / "prompts-extracao-notebooklm.md"


def resolver_prompts(caminho):
    """Caminho do arquivo de prompts: o vivo, senão a cópia bundled, senão None."""
    if caminho and Path(caminho).exists():
        return caminho
    if PROMPTS_BUNDLED.exists():
        if caminho:
            log(f"⚠ prompts do config não alcançáveis ({caminho!r}) — usando a cópia BUNDLED "
                f"do plugin ({PROMPTS_BUNDLED}). Ela pode estar atrás da sua.")
        else:
            log(f"🔧 prompts: cópia bundled do plugin ({PROMPTS_BUNDLED})")
        return str(PROMPTS_BUNDLED)
    return None


def ler_prompts(prompts_path):
    linhas = Path(prompts_path).read_text(encoding="utf-8").splitlines()
    blocos = {}
    dentro = False
    buff = []
    key_ativa = None

    def casa_heading(linha):
        if not linha.lstrip().startswith("#"):
            return None
        if re.search(r"Impugna", linha, re.I):   # ignora o prompt de Impugnação (Skill 4)
            return "IGNORAR"
        for key, pat in PARTES:
            if re.search(pat, linha, re.I):
                return key
        return None

    for linha in linhas:
        h = casa_heading(linha)
        if h is not None and not dentro:
            key_ativa = h
            continue
        if linha.strip().startswith("```"):
            if not dentro:
                if key_ativa and key_ativa != "IGNORAR" and key_ativa not in blocos:
                    dentro = True
                    buff = []
                continue
            blocos[key_ativa] = "\n".join(buff).strip()
            dentro = False
            key_ativa = None
            continue
        if dentro:
            buff.append(linha)

    faltando = [k for k, _ in PARTES if k not in blocos]
    return blocos, faltando


# ── achar os 4 PDFs de entrada ────────────────────────────────────────────────
def achar_pdfs(pasta):
    pdfs = []
    for f in sorted(Path(pasta).iterdir()):
        if f.suffix.lower() != ".pdf":
            continue
        if any(bad in f.stem.lower() for bad in DENYLIST):
            continue
        pdfs.append(f)
    return pdfs


# ── chamadas ao nlm ───────────────────────────────────────────────────────────
def nlm_run(nlm, args, timeout=None):
    """Roda `nlm ...` (sem --json). Devolve (stdout, erro-ou-None)."""
    cp = subprocess.run([nlm, *args], capture_output=True, text=True,
                        encoding="utf-8", timeout=timeout)
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    return (cp.stdout or "").strip(), None


def nlm_json(nlm, args, timeout=None):
    """Roda `nlm ... --json` e devolve (dict, erro-ou-None)."""
    cp = subprocess.run([nlm, *args, "--json"], capture_output=True, text=True,
                        encoding="utf-8", timeout=timeout)
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    out = (cp.stdout or "").strip()
    m = re.search(r"\{.*\}\s*$", out, re.S)   # o nlm às vezes loga antes do JSON
    try:
        return json.loads(m.group(0) if m else out), None
    except json.JSONDecodeError:
        return None, f"resposta não-JSON do nlm: {out[:300]}"


def strip_citacoes(s):
    """Remove a citação do NLM/Gemini Notebook, preservando os sinais de controle do formulário.

    Formas removidas: [12] · [1, 2] · [2-5] · [5–7] e, desde a virada para o Gemini, a referência
    de imagem [Image 115] · [77, 106, Image 115] · [Image 74, Image 88].
    Formas PRESERVADAS (o plugin as usa como sinal): [X] [ ] [NR-15] [Anexo 13] [N.A.]
    [NÃO LOCALIZADO] [Presente — …] [3?41] (leitura duvidosa de C.A.) [29/04/2025] (data).
    Por isso só é aceito conteúdo de número, "Image N", vírgula e traço de intervalo.
    Come só espaço/tab à esquerda (nunca \\n) para não emendar duas linhas numa só.

    ⚠ Cópia idêntica nas skills 01-extrator, 01b-extrator-nlm e 04b-responde-impugnacao-nlm —
    o test_helper_parity.py trava o drift. Alterar aqui = alterar nas três.
    """
    item = r"(?:[Ii]mage[m]?\s*)?\d+"
    faixa = r"(?:\s*[-–]\s*\d+)?"
    padrao = (r"[ \t]*\[\s*" + item + faixa +
              r"(?:\s*,\s*" + item + faixa + r")*\s*\]")
    return re.sub(padrao, "", s)


def limpar(s):
    """Tira citações/refs de imagem (preserva [X] [ ] [NÃO...]); tira ** e espaços órfãos."""
    s = strip_citacoes(s)
    s = s.replace("**", "")
    s = re.sub(r"[ \t]+([.,;:])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


# ── ficha de EPI em notebook PRÓPRIO (T7) ─────────────────────────────────────
# Medido em processo real (0011183-33, ficha manuscrita de 20 fls.): no notebook do lote a
# Parte 3a devolveu 2 a 3 entregas de uma ficha que tem centenas. A disputa é na INDEXAÇÃO,
# não na pergunta: filtrar a fonte na consulta não substitui subir sozinha. E ficha perdida
# não sai vazia, sai PLAUSÍVEL — uma tabela bonita com 5 entregas de uma ficha que tem 29 —,
# que é o pior modo de falhar, porque o perito só descobre com a ficha na mão, na diligência.
#
# Estes helpers leem RESPOSTA DE MODELO, então passam tudo por limpar() antes de casar texto:
# no dialeto do Gemini a linha vem "| **09/03/2022** | 1 | LUVA | 5745 [Image 20] |", e casar
# o literal contra formatação livre foi exatamente o que a v1.0.97 teve de desfazer.
FICHA_HINTS = ("ficha", "epi")


def achar_ficha(pdfs):
    """O PDF da ficha de EPI entre os da pasta, ou None (aí a ficha pode estar embutida na
    contestação e a Parte 3a roda no notebook do lote, como antes)."""
    for p in pdfs:
        nome = p.stem.lower()
        if any(h in nome for h in FICHA_HINTS):
            return p
    return None


def separar_ficha(pdfs, ficha_no_lote=False):
    """Decide o que vai para o notebook dedicado e o que sobra para o do lote.

    Devolve (ficha, pdfs_lote). A ficha só é isolada se SOBRAR pelo menos um PDF para o lote:
    pasta que só tem a ficha (acontece — a skill roda com ≥1 PDF, desde a v1.0.81) deixaria o
    notebook do lote sem nenhuma fonte, e as Partes 1/2/4 morreriam na primeira query.
    """
    if ficha_no_lote:
        return None, list(pdfs)
    ficha = achar_ficha(pdfs)
    if not ficha:
        return None, list(pdfs)
    lote = [p for p in pdfs if p != ficha]
    if not lote:                      # a ficha é o único PDF → nada a isolar
        return None, list(pdfs)
    return ficha, lote


def imprescrito_de(resposta_p1):
    """Data de início do imprescrito apurada na Parte 1. A Parte 3a precisa dela para a linha
    divisória ▼▼▼ e, fora da conversa do lote, não teria como saber."""
    if not resposta_p1:
        return None
    texto = limpar(resposta_p1)
    m = re.search(r"[Ii]mprescrito[^\n]*?de\s+(\d{2}/\d{2}/\d{4})", texto)
    if not m:
        m = re.search(r"[Ii]mprescrito[^\n]*?(\d{2}/\d{2}/\d{4})", texto)
    return m.group(1) if m else None


def _ordem_data(d):
    """'dd/mm/aaaa' → chave ordenável (aaaa, mm, dd). Ordenar a string crua compara o DIA
    primeiro, e aí '31/01/2020' sairia DEPOIS de '01/02/2021'."""
    return d[6:10], d[3:5], d[0:2]


# ── ORIGEM DA FICHA: medir, em vez de acreditar ──────────────────────────────────────
# O bundle JÁ traz "▶ ORIGEM DA FICHA: [X] PDF digital nativo · [ ] Imagem escaneada…", mas
# quem marca é o MODELO. E é essa linha que decide o peso da extração: em ficha com tabela
# legível a contagem fecha exata; em ficha manuscrita duas gerações do mesmo artefato deram
# 314 e 395 entregas (~20%), e ali a extração é ROTEIRO DE DILIGÊNCIA, não fonte de verdade.
#
# O que se mede NÃO é "o PDF é digital?" — medido nos PDFs do Irineu, a petição inicial tem
# 2071 chars/página e MENOS de uma data distinta no documento inteiro. Densidade de texto
# sozinha chamaria a petição de ficha. A pergunta certa é **"este PDF expõe uma tabela de
# entregas legível?"**, e quem responde é a DIVERSIDADE DE DATAS por página:
#
#   ficha digital (0010094-14, 7 fls.) ..... 721 ch/pág · 17 datas distintas · 2,43/pág
#   ficha escaneada (0017000-78, 1 fl.) .....  7 ch/pág ·  0 datas distintas · 0,00/pág
#   petição inicial (controle, 30 fls.) .... 2071 ch/pág ·  1 data  distinta · 0,03/pág
#   carimbo do PJe só (caso da auditoria) ... 330 ch/pág ·  1 data  distinta · 0,05/pág
#
# O último é o caso adversário: 20 páginas com a MESMA data (o carimbo), que a densidade de
# texto classificaria errado e a diversidade de datas acerta. Margem ~50×, não é corte fino.
#
# Tudo stdlib de propósito: o extrai_processo roda no PC do Irineu sem instalação. Qualquer
# falha de leitura vira 'indeterminado' e o comportamento é o de hoje — nunca pior.
_PDF_STREAM_RE = re.compile(rb'stream\r?\n(.*?)endstream', re.S)
# "show text" do PDF: [..]TJ ou (..)Tj/'/" — restringir a isto é o que impede parêntese
# dentro de stream de IMAGEM binária de entrar na conta (sem o filtro deu 1,2 M chars/pág).
_PDF_TJ_RE = re.compile(rb'\[[^\[\]]{0,4000}\]\s*TJ'
                        rb"|\((?:\\.|[^\\()]){0,2000}\)\s*(?:Tj|'|\")", re.S)
_PDF_STR_RE = re.compile(rb'\((?:\\.|[^\\()])*\)', re.S)
# Como o _PDF_TJ_RE, mas capturando TAMBÉM o posicionamento, na ordem do stream: é o grupo 3
# que vira quebra de linha.
_PDF_TOKEN_RE = re.compile(
    rb'(\[[^\[\]]{0,4000}\]\s*TJ)'
    rb'|(\((?:\\.|[^\\()]){0,2000}\)\s*(?:Tj|\'|"))'
    rb'|(\bT\*|\bTd|\bTD|\bTm|\bBT|\bET)', re.S)
_PDF_PAGE_RE = re.compile(rb'/Type\s*/Page[^sA-Za-z]')
# Data da ficha, nos formatos que aparecem DE VERDADE. Medido na ficha da ASW (proc.
# 0011183-33): "17.07.24", "18/07/24", "29.11.22", "01-12-22", "27.04.21" — separador ponto,
# barra OU hífen, e ano de DOIS dígitos. A regex antiga só aceitava dd/mm/aaaa e não casava
# NENHUM desses; num ficha digital com esse estilo o gabarito do T7.2 sairia zerado.
# O separador é independente em cada posição de propósito: manuscrito transcrito mistura.
_DATA_BR_RE = re.compile(r'\b(\d{2})[./-](\d{2})[./-](\d{4}|\d{2})\b')


def _data_valida(m):
    """Dia 1–31 e mês 1–12. É o que separa data de código com pontos — sem isto, um C.A.
    escrito "33.333" ou um RG "46.272.896-1" viram entrega e o gabarito infla (superestimar
    é a direção que cria alarme falso)."""
    try:
        d, mes = int(m.group(1)), int(m.group(2))
    except (TypeError, ValueError):
        return False
    return 1 <= d <= 31 and 1 <= mes <= 12


def _datas_do_texto(texto):
    """Todas as datas válidas do texto, normalizadas para dd/mm/aaaa (ano de 2 dígitos vira
    20xx — ficha trabalhista não tem entrega do século passado nesta base)."""
    out = []
    for m in _DATA_BR_RE.finditer(texto or ''):
        if not _data_valida(m):
            continue
        ano = m.group(3)
        out.append('%s/%s/%s' % (m.group(1), m.group(2), ano if len(ano) == 4 else '20' + ano))
    return out
# Piso de datas distintas por página para dizer "tem tabela legível". O digital conhecido dá
# 2,43 e o maior falso-candidato dá 0,05; 0,5 fica no meio, com folga dos dois lados.
LIMIAR_DATAS_POR_PAGINA = 0.5


def _pdf_linhas(raw):
    """Linhas aproximadas do PDF. A linha é o que o T7.2 precisa: o gabarito conta UMA data
    por linha, a primeira — em todos os layouts a data de entrega vem primeiro, e numa das
    fichas a segunda era a validade do C.A., que inflava a conta.

    A quebra sai dos operadores de POSICIONAMENTO (Td/TD/T*/Tm/BT/ET): é assim que o PDF
    marca linha nova. Aproximado de propósito — serve para CONTAR, não para transcrever.
    """
    linhas = []
    for m in _PDF_STREAM_RE.finditer(raw):
        d = m.group(1)
        infl = None
        for tenta in (zlib.decompress, lambda x: zlib.decompressobj().decompress(x)):
            try:
                infl = tenta(d)
                break
            except Exception:
                infl = None
        if not infl:
            continue
        atual = []
        for op in _PDF_TOKEN_RE.finditer(infl):
            if op.group(3):                       # posicionou → fecha a linha
                if atual:
                    linhas.append(' '.join(atual))
                    atual = []
                continue
            for g in _PDF_STR_RE.finditer(op.group(1) or op.group(2)):
                t = g.group(0)[1:-1]
                if t and sum(1 for c in t if 32 <= c < 127 or c in (9, 10, 13)) >= 0.7 * len(t):
                    atual.append(t.decode('latin-1', 'replace'))
        if atual:
            linhas.append(' '.join(atual))
    return linhas


def _pdf_texto(raw):
    """Texto corrido, derivado das linhas — fonte única com o _pdf_linhas."""
    return ' '.join(_pdf_linhas(raw))


def sondar_origem_ficha(pdf_path):
    """(origem, medidas) medidos no PDF. origem ∈ 'digital' | 'escaneada' | 'indeterminado'.

    'indeterminado' é resposta legítima e frequente (PDF cifrado, object stream que não
    inflamos, layout exótico) — e nesse caso ninguém decide nada por ele.
    """
    try:
        raw = Path(pdf_path).read_bytes()
    except Exception:
        return "indeterminado", {}
    # Sem isto, um arquivo que NAO e PDF devolvia veredicto confiante ("escaneada", porque
    # nao acha data nenhuma) em vez de admitir que nao sabe.
    if not raw[:1024].lstrip().startswith(b"%PDF"):
        return "indeterminado", {}
    try:
        pags = len(_PDF_PAGE_RE.findall(raw)) or 1
        texto = _pdf_texto(raw)
        datas = _datas_do_texto(texto)
        distintas = len(set(datas))
        dpp = distintas / pags
        med = {"paginas": pags, "chars": len(texto), "chars_pag": round(len(texto) / pags, 1),
               "datas": len(datas), "datas_distintas": distintas, "datas_pag": round(dpp, 2)}
        if dpp >= LIMIAR_DATAS_POR_PAGINA:
            return "digital", med
        # Sem tabela de datas legível. Se também não há texto nenhum, é scan puro; se há
        # texto mas as datas não variam, é o carimbo do PJe. Os dois caem no mesmo ramo.
        return "escaneada", med
    except Exception:
        return "indeterminado", {}


_ORIGEM_DECL_RE = re.compile(
    r'ORIGEM\s+DA\s+FICHA.*?$', re.I | re.M)


def origem_declarada(resposta_p3a):
    """O que o MODELO marcou na linha ▶ ORIGEM DA FICHA, ou None se não marcou nada."""
    m = _ORIGEM_DECL_RE.search(resposta_p3a or "")
    if not m:
        return None
    linha = m.group(0)
    # a 1ª opção marcada manda; "[X] PDF digital nativo" vs "[X] Imagem escaneada…"
    marcadas = re.findall(r'\[\s*[xX]\s*\]\s*([^·|\[\]]{3,60})', linha)
    for texto in marcadas:
        t = texto.lower()
        if 'digital' in t or 'nativo' in t or 'selecion' in t:
            return "digital"
        if 'escane' in t or 'imagem' in t or 'manuscrit' in t or 'ocr' in t:
            return "escaneada"
    return None


# ── T7.2/T7.3: conferência da CONTAGEM ───────────────────────────────────────────────
# Até aqui não existia NENHUMA conferência independente: o check_epi classifica por C.A. o
# que já está na tabela, e o checklist do SKILL.md é o modelo conferindo o bundle contra o
# próprio bundle. Conferência que fecha com ela mesma não pega nada — em 07/08 o motor gêmeo
# declarou 240, listou 240, e faltavam 15. Zero alarme. Só quebra o círculo quem compara com
# o DOCUMENTO.
#
# Direção única, de propósito: a conferência acusa FALTA, nunca sobra. Falta é omissão de
# leitura; sobra também acontece e é outro problema (T11), que esta régua não vê.

# Linha de entrega no que o modelo transcreveu: tabela markdown que começa com a data, ou o
# bullet do montador. Mesma regra do parse_ficha_rows: quem produz e quem confere têm de ler
# da mesma origem.
_LINHA_ENTREGA_RE = re.compile(r'^[\s\-–—•·*]*\|?\s*\d{2}[./-]\d{2}[./-](?:\d{4}|\d{2})\s*[|·]', re.M)
# Mesma linha, com a data CAPTURADA — a conferência por data (T7.2 fino) precisa saber
# QUANDO cada linha transcrita foi entregue, não só quantas são.
_LINHA_ENTREGA_DATA_RE = re.compile(
    r'^[\s\-–—•·*]*\|?\s*(\d{2}[./-]\d{2}[./-](?:\d{4}|\d{2}))\s*[|·]', re.M)
# Marcador da nota da sonda. ESPELHA `SONDA_FICHA` do montar_formulario.py — quem escreve
# e quem le tem de usar a mesma string (test_sonda_no_formulario.py trava as duas pontas).
SONDA_FICHA = "▶ SONDA FICHA"

# Rodapé de emissão — a assinatura de ficha REIMPRESSA. Ver o porquê em conferir_contagem().
_EMISSAO_RE = re.compile(
    r'(?:emiss[ãa]o|emitid[oa]|impress[ãa]o|gerado)\D{0,24}(\d{2}/\d{2}/\d{4})', re.I)
# Piso de entregas por página da ficha (T7.3). Medido em 9 fichas: o único colapso conhecido
# deu 0,15 e as outras oito ficaram entre 1,0 e 19,55.
PISO_ENTREGAS_POR_PAGINA = 0.5
# Quanto o transcrito pode ficar abaixo do gabarito sem virar alarme. O gabarito é uma conta
# de linhas com data e pega junto o cabeçalho ("Admissão: …"): medido na ficha do 0010094-14,
# 44 datas de gabarito para 38 entregas reais (86%). O colapso que se quer pegar é de outra
# ordem — 5 de 29 é 17%. 0,75 passa longe de um e longe do outro.
RAZAO_MINIMA_CONTAGEM = 0.75


def gabarito_entregas(pdf_path):
    """(datas, paginas) lidas do PDF: a PRIMEIRA data de cada linha que tem data.

    ⚠ A ficha de EPI NÃO tem layout único — cada empregador imprime a sua, e o plugin vê
    modelos novos o tempo todo. Por isso a régua é a mais agnóstica possível: uma data por
    linha, a primeira, onde quer que ela esteja. Foi a regra medida em 9 fichas de
    empregadores diferentes — em todos os layouts a data de ENTREGA vem antes das outras
    (numa delas a segunda era a validade do C.A., e contar todas inflava a conta).

    Exigir a data no INÍCIO da linha seria mais limpo neste PDF, mas quebra em qualquer
    layout que comece a linha por nº de item ou código de produto — e aí o gabarito sai
    baixo demais, o que não dá alarme falso mas também não confere nada.

    O gabarito é um TETO aproximado (pega cabeçalho junto: "Data da Autuação: …"), nunca um
    número exato — quem compara com ele usa RAZÃO, não igualdade.
    """
    try:
        raw = Path(pdf_path).read_bytes()
        if not raw[:1024].lstrip().startswith(b"%PDF"):
            return [], 0
        pags = len(_PDF_PAGE_RE.findall(raw)) or 1
        datas = []
        for ln in _pdf_linhas(raw):
            do_linha = _datas_do_texto(ln)
            if do_linha:
                datas.append(do_linha[0])       # a PRIMEIRA da linha = a de entrega
        return datas, pags
    except Exception:
        return [], 0


def contar_entregas_transcritas(resposta_p3a):
    """Quantas linhas de entrega o modelo devolveu."""
    return len(_LINHA_ENTREGA_RE.findall(resposta_p3a or ""))


def datas_transcritas(resposta_p3a):
    """Data de cada linha de entrega devolvida pelo modelo, normalizada dd/mm/aaaa."""
    out = []
    for bruta in _LINHA_ENTREGA_DATA_RE.findall(resposta_p3a or ""):
        norm = _datas_do_texto(bruta.replace('.', '/').replace('-', '/'))
        if norm:
            out.append(norm[0])
    return out


def ficha_reimpressa(pdf_path):
    """Datas DISTINTAS de rodapé de emissão — 2 ou mais = ficha reimpressa.

    Armadilha que custou uma corrida: o PDF traz o mesmo histórico duas vezes, com rodapés
    de emissão em datas distintas. A contagem por data sai em DOBRO e a guarda acusa datas
    que estão certas. Deduplicar linha não resolve (o extrator quebra a mesma entrega de
    jeitos diferentes nas duas cópias) e chave por código de produto também não (o carimbo
    diagonal do PJe joga o código para outra linha). O sinal confiável é o rodapé.
    """
    try:
        raw = Path(pdf_path).read_bytes()
        if not raw[:1024].lstrip().startswith(b"%PDF"):
            return set()
        return set(_EMISSAO_RE.findall(' '.join(_pdf_linhas(raw))))
    except Exception:
        return set()


def conferir_por_data(datas_pdf, resposta_p3a, log_fn=log):
    """T7.2 FINO: compara a contagem POR DATA, não só o total. Só avisa.

    Por que o total sozinho não bastava — caso real, 0010094-14, ficha DIGITAL de 6 páginas
    (22/08/2026): o modelo devolveu 34 entregas contra as 38 verdadeiras, e as 4 perdidas
    estavam TODAS numa data só — 31/01/2025, 6 linhas de 10. No agregado isso dá 76% contra
    um piso de 75% e sai um "✓ contagem confere" tranquilo; por data, a MESMA leitura acusa
    `31/01/2025: 6 de 10`. As outras 15 datas batiam exatas, uma a uma.

    O que fez o modelo perder as 4: aquela data aparece em DOIS blocos de aprovação da mesma
    ficha (fim da pág. 4 e começo da pág. 6) com itens repetidos — mesmo dia, mesmo item,
    mesmo C.A. Linha repetida parece engano de digitação, e o modelo "limpa". Na ficha a
    linha É a unidade de prova: repetida ou não, transcreve-se.

    Duas contenções contra alarme falso, porque gate que grita à toa é gate que o perito
    aprende a ignorar:
    • **déficit** (🚩) só em data que o modelo TRANSCREVEU — aí não há como confundir com
      cabeçalho, e é a forma comum da perda (parte das linhas do dia);
    • **data sumida inteira** (⚠, mais fraco) só quando cai ESTRITAMENTE DENTRO do intervalo
      que o próprio modelo transcreveu. É o que mantém a régua agnóstica de layout: as datas
      de cabeçalho/rodapé (admissão, autuação, emissão, "Período: X até Y") ficam nas pontas
      ou fora, e não entram. Na ficha real são exatamente as 6 de `01/04/2011` (admissão) e a
      de `26/01/2026` — nenhuma delas dispara.
    """
    do_pdf = Counter(datas_pdf)
    do_modelo = Counter(datas_transcritas(resposta_p3a))
    if not do_pdf or not do_modelo:
        return []

    def _chave(d):                                   # dd/mm/aaaa ordena errado como string
        dd, mm, aa = d.split('/')
        return (aa, mm, dd)

    deficits = sorted(((d, do_pdf[d], do_modelo[d]) for d in do_modelo
                       if do_pdf.get(d, 0) > do_modelo[d]), key=lambda t: _chave(t[0]))
    lo, hi = min(do_modelo, key=_chave), max(do_modelo, key=_chave)
    sumidas = sorted((d for d in do_pdf
                      if d not in do_modelo and _chave(lo) < _chave(d) < _chave(hi)),
                     key=_chave)

    if deficits:
        falta = sum(g - t for _, g, t in deficits)
        log_fn("   🚩 CONTAGEM POR DATA NÃO FECHA — %d linha(s) a menos que o PDF, em %d "
               "data(s): %s. O total pode até fechar no agregado; aqui não fecha. Confira "
               "essas datas na ficha (linha repetida no mesmo dia é entrega, não engano)."
               % (falta, len(deficits),
                  ', '.join('%s: %d de %d' % (d, t, g) for d, g, t in deficits)))
    if sumidas:
        log_fn("   ⚠ data(s) com linha no PDF e NENHUMA entrega transcrita, dentro do "
               "intervalo que o modelo leu: %s. Pode ser linha de cabeçalho do layout — "
               "confira na ficha." % ', '.join(sumidas))
    if not deficits and not sumidas:
        log_fn("   ✓ contagem por data confere: %d data(s), todas com a mesma contagem do PDF."
               % len(do_modelo))
    return deficits


def nota_sonda(deficits):
    """Déficits por data → a linha que o montador iça para o topo da tabela de EPI.

    Por que sair do console: a sonda por data existe desde a v1.5.2 e ACUSOU a perda do
    0010094-14 (`31/01/2025: 6 de 10`) — no log do lote, que ninguém reabre. O formulário,
    que é o que o perito lê na diligência, saiu limpo, e o laudo foi redigido em cima dele.
    Nota que só aparece no console e nota que não existe dão no mesmo.

    Formato: uma linha `SONDA_FICHA: <texto>`, colada ABAIXO da tabela da Parte 3a — abaixo
    para não se meter entre as linhas `| … |` que o montador recorta por data.
    """
    if not deficits:
        return ""
    falta = sum(g - t for _, g, t in deficits)
    onde = '; '.join('%s: %d de %d' % (d, t, g) for d, g, t in deficits)
    return ("%s: FALTAM ~%d entrega(s) na tabela abaixo, em %d data(s) — %s. O modelo leu a "
            "ficha e devolveu MENOS linhas do que ela tem nesses dias (tipicamente linha "
            "repetida no mesmo dia, que ele \"limpa\" achando que é engano de digitação, ou "
            "entrega partida entre duas páginas). CONFIRA essas datas na ficha original antes "
            "de fechar o laudo — na ficha, linha repetida É entrega."
            % (SONDA_FICHA, falta, len(deficits), onde))


def conferir_contagem(pdf_path, resposta_p3a, origem, log_fn=log):
    """T7.2 no ramo digital, T7.3 nos dois. Só avisa — nada entra no bundle."""
    transcritas = contar_entregas_transcritas(resposta_p3a)
    datas, pags = gabarito_entregas(pdf_path)

    # T7.3 — o sinal barato, que vale inclusive quando não há gabarito nenhum.
    if pags and transcritas / pags < PISO_ENTREGAS_POR_PAGINA:
        log_fn(f"   🚩 SÓ {transcritas} entrega(s) para {pags} página(s) de ficha "
               f"({transcritas / pags:.2f}/pág, piso {PISO_ENTREGAS_POR_PAGINA}) — indício de "
               f"LEITURA COLAPSADA. Abra a ficha e confira antes de usar esta tabela.")

    if origem != "digital":
        # Sem tabela legível não há gabarito, e gabarito cego NÃO pode passar calado: foi
        # assim que um formulário saiu com 5 entregas de uma ficha que tinha 29.
        log_fn(f"   ⚠ {transcritas} entrega(s) transcritas, SEM conferência automática "
               "possível (a ficha não expõe tabela legível). Confira na ficha original.")
        return transcritas, len(datas), ""

    emissoes = ficha_reimpressa(pdf_path)
    if len(emissoes) >= 2:
        log_fn(f"   ⚠ FICHA REIMPRESSA — rodapés de emissão em datas distintas "
               f"({', '.join(sorted(emissoes))}). O histórico aparece mais de uma vez e a "
               f"contagem sairia em dobro, então NÃO comparo. Confira na via original.")
        return transcritas, len(datas), ""

    if not datas:
        log_fn(f"   ⚠ {transcritas} entrega(s) transcritas, mas não consegui montar gabarito "
               "de datas no PDF — sem conferência automática nesta ficha.")
        return transcritas, 0, ""

    if len(datas) < transcritas:
        # O gabarito é um TETO: sair MENOR que o transcrito significa que a régua não
        # enxergou o layout desta ficha (cada empregador imprime a sua). Silêncio aqui
        # pareceria concordância, que é justamente o que não se pode afirmar.
        log_fn(f"   ⚠ gabarito ({len(datas)} linha(s) com data) MENOR que o transcrito "
               f"({transcritas}) — a régua não leu o layout desta ficha, então NÃO há "
               f"conferência de contagem aqui. Não é sinal de que está certo.")
        return transcritas, len(datas), ""

    razao = transcritas / len(datas)
    if razao < RAZAO_MINIMA_CONTAGEM:
        log_fn(f"   🚩 CONTAGEM NÃO FECHA — o modelo transcreveu {transcritas} entrega(s) e o "
               f"PDF tem {len(datas)} linha(s) começando por data ({razao:.0%}). Faltam "
               f"~{len(datas) - transcritas}. O gabarito é um TETO aproximado (conta cabeçalho "
               f"junto), então o número exato é na ficha — mas uma diferença desta ordem é "
               f"leitura perdida, não arredondamento.")
    else:
        log_fn(f"   ✓ contagem confere: {transcritas} transcritas × {len(datas)} linhas com "
               f"data no PDF ({razao:.0%}).")
    # O agregado passa com folga e a perda pode estar inteira numa data (caso real de
    # 22/08/2026 — ver conferir_por_data). Roda SEMPRE que houve comparação, inclusive
    # depois do ✓, que é justamente quando ninguém iria olhar.
    deficits = conferir_por_data(datas, resposta_p3a, log_fn=log_fn)
    return transcritas, len(datas), nota_sonda(deficits)


def avisar_rotacao(pdf_path, log_fn=log):
    """Avisa se a ficha tem páginas com rotação declarada. NÃO corrige nada.

    Rotação declarada não é defeito por si — medido no acervo do Irineu, as 78 páginas
    giradas da contestação do 0010094-14 são cartões-ponto em paisagem e renderizam CERTAS,
    e o pdftotext lê a página girada inteira. O ganho de normalizar existe só se quem lê o
    PDF ignorar o campo /Rotate, e isso não está medido no Gemini Notebook — por isso aqui
    só se INFORMA, e quem decide rodar o normalizar_rotacao.py é o perito.
    """
    try:
        from normalizar_rotacao import diagnostico
    except Exception:
        return 0, 0
    pags, giradas = diagnostico(pdf_path)
    if giradas:
        log_fn(f"   ⚠ a ficha tem {giradas} de {pags} página(s) com rotação declarada. Não é "
               f"defeito por si (o leitor honra o /Rotate), mas se a leitura vier ruim, uma "
               f"cópia normalizada pode ajudar: python normalizar_rotacao.py "
               f'"{pdf_path}" -o ficha-normalizada.pdf')
    return pags, giradas


def texto_resposta(res):
    """A resposta do modelo como TEXTO, venha ela em envelope (dict do nlm/artefato) ou crua.

    Um ponto só para todo mundo desembrulhar: quem produz e quem confere têm de ler da mesma
    origem — foi um consumidor lendo o envelope que matou a sonda em silêncio.
    """
    if isinstance(res, dict):
        return res.get("answer") or ""
    return res or ""


def conferir_origem_ficha(pdf_path, resposta_p3a, log_fn=log):
    """Cruza a declaração do modelo com a medida. Só AVISA — no console, nunca no bundle.

    Não corrige a linha do bundle de propósito: o formulário do Irineu não se toca, e uma
    medida com margem grande mas amostra pequena (3 casos conhecidos) não deve sobrescrever
    em silêncio o que o modelo leu do documento. Quem decide é o perito.
    """
    medida, med = sondar_origem_ficha(pdf_path)
    declarada = origem_declarada(resposta_p3a)
    if med:
        log_fn(f"   🔎 ficha medida: {med['paginas']} pág · {med['chars_pag']} chars/pág · "
               f"{med['datas_distintas']} datas distintas ({med['datas_pag']}/pág) → {medida}")
    if medida == "indeterminado":
        log_fn("   ⚠ não foi possível medir a camada de texto da ficha — segue a declaração "
               "do modelo, como antes.")
        return medida, declarada
    if medida == "escaneada":
        log_fn("   ⚠ FICHA SEM TABELA DE ENTREGAS LEGÍVEL (escaneada/manuscrita). A extração "
               "dela é ROTEIRO DE DILIGÊNCIA, não fonte de verdade: confira as entregas na "
               "ficha original, em campo. Não existe conferência automática possível aqui.")
    if declarada and declarada != medida:
        log_fn(f"   🚩 ORIGEM DA FICHA DIVERGE — o modelo declarou '{declarada}' e a medição "
               f"diz '{medida}'. O bundle mantém o que o modelo escreveu; confira a linha "
               f"▶ ORIGEM DA FICHA antes de confiar na contagem.")
    elif not declarada:
        log_fn(f"   ⚠ o modelo não marcou a linha ▶ ORIGEM DA FICHA; a medição diz '{medida}'.")
    return medida, declarada


def resumo_ficha(resposta_p3a, limite=1200):
    """Digest compacto da ficha para a Parte 3b (que cruza 'a prática' com 'a norma').

    A tabela inteira não cabe no limite da mensagem — e não precisa: o que a 3b consome dela é
    quantidade, faixa de datas e quais C.A. apareceram. As contas finas (lacuna no imprescrito,
    cobertura) quem faz é o check_epi.py, de forma determinística, e não o modelo.
    """
    if not resposta_p3a:
        return ""
    linhas = [l for l in limpar(resposta_p3a).splitlines()
              if re.match(r"^\s*\|\s*\d{2}/\d{2}/\d{2,4}", l)]
    corpo = "\n".join(linhas)
    datas = re.findall(r"\b\d{2}/\d{2}/\d{4}\b", corpo)
    cas = []
    # o C.A. é a última coluna: número colado no '|'. O lookbehind exclui dígito e '/' para
    # não eleger o ANO da coluna de data ("| 09/03/2022 |" daria o C.A. fantasma 2022).
    for c in re.findall(r"(?<![\d/])(\d{4,6})\s*(?=\|)", corpo):
        if c not in cas:
            cas.append(c)
    sem_ca = sum(1 for l in linhas if re.search(r"n[ãa]o informado", l, re.I))
    partes = ["CONTEXTO — a tabela de EPI da Parte 3a já foi extraída em consulta dedicada à "
              "ficha. Resumo do que ela trouxe (não reextraia a ficha; use este resumo):",
              f"- entregas registradas: {len(linhas)}"]
    if datas:
        ini, fim = min(datas, key=_ordem_data), max(datas, key=_ordem_data)
        partes.append(f"- período coberto pela ficha: {ini} a {fim}")
    if sem_ca:
        partes.append(f"- entregas SEM C.A. informado: {sem_ca}")
    if cas:
        lista = ", ".join(cas[:40]) + ("…" if len(cas) > 40 else "")
        partes.append(f"- C.A. distintos ({len(cas)}): {lista}")
    return "\n".join(partes)[:limite]


# ── T7.1: a ficha pela via do ARTEFATO (data-table), não pela do chat ─────────
# O notebook próprio (T7) resolve a INDEXAÇÃO; não resolve o TETO DA RESPOSTA DE CHAT.
# Medido no 0015098-90 (ficha de 195 páginas, 255 entregas reais), seis tentativas de chat
# para o MESMO PDF: 64 (truncou sem avisar) · 240 · 240 · 0 · 250 · e o artefato 253, contra
# 255 do documento. Seis prompts, seis resultados: a causa é estrutural, não de prompt — o
# teto é o da mensagem, e o artefato não o tem porque escreve em ARQUIVO.
#
# Medido nesta casa em 20/08/2026, ficha manuscrita de 20 fls. do 0011183-33: a via do
# artefato devolveu 395 entregas, todas com data válida, de 01/07/2020 a 12/09/2024.
DESC_DATA_TABLE = (
    "Transcreva a FICHA DE CONTROLE DE ENTREGA DE EPI, uma linha por entrega registrada, na "
    "ordem em que aparecem no documento. Colunas: DATA_ENTREGA (dd/mm/aaaa; se a celula trouxer "
    "um periodo com duas datas, e UMA entrega so - transcreva apenas a data inicial), "
    "QUANTIDADE (o numero exatamente como esta escrito; atencao: 1,000 e UMA unidade com tres "
    "casas decimais, NAO mil), EQUIPAMENTO (a descricao literal como escrita, mantendo a "
    "grafia original), CA (numero do Certificado de Aprovacao; se ilegivel transcreva o que se "
    "ve entre colchetes, ex. [3?41]; se nao houver escreva NAO INFORMADO). Transcreva TODAS as "
    "entregas de TODAS as paginas, sem resumir, sem agrupar e sem omitir repeticoes."
)

# A coluna é casada por PALAVRA-CHAVE, nunca por posição: o cabeçalho do CSV vem do modelo e
# varia (foram três layouts em três fichas de empregadores diferentes), e a ferramenta ainda
# acrescenta uma coluna "Source" por conta própria — indexar por posição já quebraria na
# primeira ficha. Ordem importa: "descrição do EPI" casaria em 'epi' e em 'desc'; quem procura
# primeiro é a chave certa.
COLUNAS_FICHA = [
    ("data", ("data", "entrega", "date", "dia")),
    ("qtd",  ("quant", "qtd", "unid", "qty")),
    ("desc", ("equipamento", "descri", "produto", "item", "epi", "material")),
    ("ca",   ("c.a", "ca", "certificado", "aprova")),
]


def casar_colunas(cabecalho):
    """Cabeçalho do CSV → {papel: nome da coluna}. Devolve só o que reconheceu."""
    achado = {}
    usados = set()
    for papel, chaves in COLUNAS_FICHA:
        for chave in chaves:
            for col in cabecalho or ():
                if col in usados or not col:
                    continue
                if chave in col.strip().lower().replace("_", " "):
                    achado[papel] = col
                    usados.add(col)
                    break
            if papel in achado:
                break
    return achado


def normaliza_data(valor):
    """Data da célula → dd/mm/aaaa, ou "" se não der para ler.

    Célula com DUAS datas é UMA entrega e vale a PRIMEIRA (a coluna DATA às vezes traz o
    período entrega→troca; transcrever os dois extremos como entregas dobrou 11 linhas em 22
    num caso real, e o número dobrado chegou ao laudo).
    """
    v = (valor or "").strip()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", v)
    if m:
        d, mes, a = m.group(1), m.group(2), m.group(3)
        if len(a) == 2:                       # 20 → 2020 (ficha não tem entrega do século XX)
            a = ("20" if int(a) < 70 else "19") + a
        return f"{int(d):02d}/{int(mes):02d}/{a}"
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", v)   # ISO, se o modelo resolver mudar de formato
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return ""


def normaliza_qtd(valor):
    """Quantidade da célula → (texto para a tabela, aviso ou None).

    Duas armadilhas, ambas vistas em ficha real:
    • "1,000"/"1.720" é o formato de TRÊS CASAS DECIMAIS do sistema de estoque — é UMA unidade,
      não mil e nem mil setecentas. Ler como milhar multiplica a cobertura daquele EPI por mil.
    • quantidade ilegível: a entrega EXISTE (a linha existe), então registrar 1 é o PISO, não um
      palpite — e vai marcada na conferência. Subestimar é seguro; perder a linha inteira, não:
      some junto a data que sustenta a cobertura do imprescrito.
    """
    v = (valor or "").strip()
    if re.fullmatch(r"\d+", v):
        return v, None
    m = re.fullmatch(r"(\d+)[.,](\d{3})", v)
    if m:
        return m.group(1), (f"quantidade '{v}' lida como {m.group(1)} "
                            f"(formato de 3 casas decimais, não milhar)")
    m = re.fullmatch(r"(\d+)[.,](\d{1,2})", v)
    if m:
        return m.group(1), f"quantidade '{v}' (decimal) lida como {m.group(1)}"
    return "1", (f"quantidade ilegível ('{v or 'vazia'}') registrada como 1 (piso — a entrega "
                 f"existe); conferir na ficha")


def csv_para_p3a(csv_texto, impr=None, origem=None):
    """CSV do artefato → o bloco da Parte 3a no formato que o montador já sabe ler.

    Devolve (bloco, n_entregas, avisos). Nenhuma linha é descartada em silêncio: o que não
    virou entrega sai nomeado na CONFERÊNCIA OBRIGATÓRIA, que é onde o perito olha.
    """
    leitor = csv.DictReader(io.StringIO(csv_texto))
    cols = casar_colunas(leitor.fieldnames)
    faltando = [p for p, _ in COLUNAS_FICHA if p not in cols]
    if "data" in faltando:
        raise ValueError(f"CSV sem coluna de DATA reconhecível (cabeçalho: {leitor.fieldnames})")

    avisos = []
    if faltando:
        avisos.append(f"colunas não reconhecidas no CSV ({', '.join(faltando)}); "
                      f"cabeçalho veio como {leitor.fieldnames}")

    entregas, sem_data = [], 0
    for i, r in enumerate(leitor, start=2):        # 2 = primeira linha depois do cabeçalho
        data = normaliza_data(r.get(cols["data"]))
        if not data:
            bruto = (r.get(cols["data"]) or "").strip()
            if any((v or "").strip() for v in r.values()):
                sem_data += 1
                avisos.append(f"linha {i} do CSV sem data legível (lida como '{bruto}') — "
                              f"item '{(r.get(cols.get('desc','')) or '?').strip()[:40]}'")
            continue
        qtd, aviso_q = normaliza_qtd(r.get(cols.get("qtd", "")))
        if aviso_q:
            avisos.append(f"{data} — {aviso_q}")
        desc = re.sub(r"\s+", " ", (r.get(cols.get("desc", "")) or "").strip()) or "não descrito"
        ca = (r.get(cols.get("ca", "")) or "").strip()
        if not ca or re.fullmatch(r"(?i)n[ãa]o informado|n/?a|-+|s/?\s*ca", ca):
            ca = "C.A. não informado"
        entregas.append((data, qtd, desc.replace("|", "/"), ca.replace("|", "/")))

    entregas.sort(key=lambda e: _ordem_data(e[0]))

    linhas = ["| Data de Entrega | Quantidade | Descrição do EPI | C.A. |",
              "| :--- | :---: | :--- | :---: |"]
    divisoria_posta = not impr
    for data, qtd, desc, ca in entregas:
        if not divisoria_posta and _ordem_data(data) >= _ordem_data(impr):
            linhas.append(f"| ▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO — {impr} ▼▼▼ | | | |")
            divisoria_posta = True
        linhas.append(f"| {data} | {qtd} | {desc} | {ca} |")
    if not divisoria_posta:      # imprescrito começa DEPOIS da última entrega
        linhas.append(f"| ▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO — {impr} ▼▼▼ | | | |")

    conf = avisos or ["Todos os campos transcritos com alta confiança."]
    origem_txt = origem or ("[ ] PDF digital nativo · [ ] Imagem escaneada / manuscrita / OCR "
                            "— tabela extraída via ARTEFATO (data-table) do Studio; marcar na "
                            "conferência")
    bloco = "\n".join([
        f"▶ ORIGEM DA FICHA: {origem_txt}",
        "",
        *linhas,
        "",
        "▶ EVIDÊNCIA DE ASSINATURA: não verificável por esta via — a tabela veio do artefato "
        "(data-table), que transcreve células e não o campo de assinatura. Conferir na ficha.",
        "",
        "▶ CONFERÊNCIA OBRIGATÓRIA NA FICHA ORIGINAL:",
        *(f"- {c}" for c in conf),
    ])
    if sem_data:
        avisos.append(f"{sem_data} linha(s) do CSV não viraram entrega por data ilegível")
    return bloco, len(entregas), avisos


def ficha_via_artefato(nlm, nb_ficha, impr, artefato_timeout, log_fn=log):
    """Parte 3a pela via do artefato. Devolve (bloco, n_entregas) ou levanta RuntimeError.

    Quem chama cai para o chat se isto falhar: uma via nova não pode ser um jeito novo de o
    processo inteiro parar.
    """
    res, err = nlm_json(nlm, ["data-table", "create", nb_ficha, DESC_DATA_TABLE, "-y"],
                        timeout=300)
    if not res:
        raise RuntimeError(f"não criei o data-table: {err}")
    art_id = res.get("artifact_id") or res.get("id")
    log_fn(f"   🧮 data-table pedido (artifact {art_id}) — aguardando gerar…")

    # ⚠ `nlm status artifacts` está QUEBRADO na 0.9.13 (TypeError int/OptionInfo em
    # services/studio.py:639 — default do typer não resolvido). Sondar tentando o DOWNLOAD
    # funciona e não depende do comando quebrado; se um dia consertarem, o status é mais barato.
    destino = Path(tempfile.gettempdir()) / f"nlm-ficha-{art_id or 'x'}.csv"
    destino.unlink(missing_ok=True)
    prazo = time.monotonic() + artefato_timeout
    tentativa = 0
    while time.monotonic() < prazo:
        time.sleep(20)
        tentativa += 1
        args = ["download", "data-table", nb_ficha, "-o", str(destino)]
        if art_id:
            args += ["--id", art_id]
        _o, e = nlm_run(nlm, args, timeout=300)
        if not e and destino.exists() and destino.stat().st_size > 0:
            log_fn(f"   ⬇ CSV baixado na tentativa {tentativa} ({destino.stat().st_size} bytes)")
            break
        log_fn(f"   … ainda gerando (tentativa {tentativa})")
    else:
        raise RuntimeError(f"o data-table não ficou pronto em {artefato_timeout:.0f}s")

    texto = destino.read_text(encoding="utf-8-sig", errors="replace")
    bloco, n, avisos = csv_para_p3a(texto, impr)
    if n == 0:
        raise RuntimeError("o CSV do artefato não trouxe nenhuma entrega legível")
    for a in avisos[:10]:
        log_fn(f"   ⚠ ficha: {a}")
    if len(avisos) > 10:
        log_fn(f"   ⚠ ficha: (+{len(avisos) - 10} avisos, todos no bloco de conferência)")
    destino.unlink(missing_ok=True)
    return bloco, n


CNJ_RE = r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}"


def injetar_numero(bundle, pasta_name):
    """Se a linha '- Nº:' do bundle não tiver um nº CNJ válido e o NOME DA PASTA
    tiver, preenche a linha com o nº da pasta. Devolve (bundle, nº ou None)."""
    m = re.search(CNJ_RE, pasta_name)
    if not m:
        return bundle, None
    num = m.group(0)

    def repl(mo):
        if re.search(CNJ_RE, mo.group(0)):   # já veio um CNJ da extração → respeita
            return mo.group(0)
        return f"- Nº: {num} (do nome da pasta)"

    novo, n = re.subn(r"(?m)^-\s*Nº:.*$", repl, bundle, count=1)
    if n == 0:   # não havia linha de Nº — prepende
        return f"- Nº: {num} (do nome da pasta)\n" + bundle, num
    return novo, (num if novo != bundle else None)


# ── processar UMA pasta: pasta → bundle (cria/sobe/consulta/limpa/apaga) ──────
def processar_pasta(nlm, pasta, blocos, out_path, wait_timeout, query_timeout,
                    regras_mode, keep, ficha_no_lote=False, ficha_por_chat=False,
                    artefato_timeout=900.0):
    pasta = Path(pasta)
    pdfs = achar_pdfs(pasta)
    if not pdfs:
        raise FalhaPasta("nenhum PDF de entrada na pasta (só FORMULÁRIO/LAUDO, ou vazia)")
    parcial = "" if len(pdfs) >= 4 else \
        f"  (PARCIAL — {len(pdfs)}/4 partes; o que faltar sai como [NÃO LOCALIZADO])"
    log(f"📄 {len(pdfs)} PDF(s): " + " · ".join(p.name for p in pdfs) + parcial)

    # A ficha de EPI sai do notebook do lote e vai para um notebook só dela (T7). O lote fica
    # com o resto; se não há arquivo de ficha separado (ela pode estar embutida na contestação),
    # nada muda e a Parte 3a roda no lote, como antes.
    ficha, pdfs_lote = separar_ficha(pdfs, ficha_no_lote)
    if ficha:
        log(f"🧾 ficha de EPI em notebook PRÓPRIO: {ficha.name}  "
            f"(lote fica com {len(pdfs_lote)} PDF(s))")

    titulo = f"EFÊMERO — {pasta.name}"
    nb, err = nlm_json(nlm, ["notebook", "create", titulo])
    if not nb:
        raise FalhaPasta(f"falha ao criar notebook: {err}")
    nb_id = nb.get("id") or nb.get("notebook_id") or (nb.get("notebook") or {}).get("id")
    if not nb_id:
        raise FalhaPasta(f"não achei o id do notebook criado: {nb}")
    log(f"🆕 notebook: {nb_id}")

    def apagar_ok():
        if keep:
            log(f"🧷 --keep: notebook mantido ({nb_id}).")
            return
        _o, e = nlm_run(nlm, ["notebook", "delete", nb_id, "-y"])
        log(f"🗑️  notebook apagado: {nb_id}" if not e else f"⚠ não apaguei {nb_id}: {e}")

    nb_ficha = [None]        # id do notebook dedicado (lista p/ o finally enxergar)

    def apagar_ficha():
        if not nb_ficha[0]:
            return
        if keep:
            log(f"🧷 --keep: notebook da ficha mantido ({nb_ficha[0]}).")
            return
        _o, e = nlm_run(nlm, ["notebook", "delete", nb_ficha[0], "-y"])
        log(f"🗑️  notebook da ficha apagado: {nb_ficha[0]}" if not e
            else f"⚠ não apaguei o notebook da ficha {nb_ficha[0]}: {e}")

    try:
        # subir os PDFs do lote esperando indexar (source add NÃO tem --json)
        for p in pdfs_lote:
            _o, err = nlm_run(nlm, ["source", "add", nb_id, "--file", str(p),
                                    "--wait", "--wait-timeout", str(wait_timeout)],
                              timeout=wait_timeout + 60)
            if err:
                raise FalhaPasta(f"falha ao subir/indexar '{p.name}': {err}", nb_id)
            log(f"   ✓ indexado: {p.name}")

        # queries encadeadas
        def query(texto, key, conv, alvo=None):
            if len(texto) > LIMITE_QUERY:
                log(f"   ⚠ {key}: {len(texto)} chars (> {LIMITE_QUERY}) — pode dar INVALID_ARGUMENT.")
            qargs = ["notebook", "query", alvo or nb_id, texto, "--timeout", str(query_timeout)]
            if conv:
                qargs += ["-c", conv]
            res, err = nlm_json(nlm, qargs, timeout=query_timeout + 60)
            if err or not res:
                raise FalhaPasta(f"falha na query {key}: {err}", nb_id)
            return res

        def query_ficha(prompt_p3a, impr):
            """Parte 3a num notebook que só tem a ficha. Como sai da conversa do lote, o marco
            do imprescrito (apurado na Parte 1) vai EXPLÍCITO no texto da pergunta."""
            nb2, err2 = nlm_json(nlm, ["notebook", "create", f"EFÊMERO — ficha {pasta.name}"])
            if not nb2:
                raise FalhaPasta(f"falha ao criar o notebook da ficha: {err2}", nb_id)
            nb_ficha[0] = (nb2.get("id") or nb2.get("notebook_id")
                           or (nb2.get("notebook") or {}).get("id"))
            if not nb_ficha[0]:
                raise FalhaPasta(f"não achei o id do notebook da ficha: {nb2}", nb_id)
            log(f"   🆕 notebook da ficha: {nb_ficha[0]}")
            _o, err2 = nlm_run(nlm, ["source", "add", nb_ficha[0], "--file", str(ficha),
                                     "--wait", "--wait-timeout", str(wait_timeout)],
                               timeout=wait_timeout + 60)
            if err2:
                raise FalhaPasta(f"falha ao subir/indexar a ficha '{ficha.name}': {err2}", nb_id)
            log(f"   ✓ indexada (dedicado): {ficha.name}")

            # T7.1 — primeiro o ARTEFATO (escreve em arquivo, sem o teto da resposta de chat).
            # Falhando, cai para o chat: via nova não pode virar jeito novo de o processo parar.
            if not ficha_por_chat:
                try:
                    bloco, n = ficha_via_artefato(nlm, nb_ficha[0], impr, artefato_timeout)
                    log(f"   ✓ P3a(artefato): {n} entregas")
                    return {"answer": bloco}
                except Exception as e:                    # noqa: BLE001 — qualquer falha cai p/ chat
                    log(f"   ⚠ artefato falhou ({e}); caindo para a via do CHAT, "
                        f"que TEM teto de resposta — confira o total de entregas.")

            texto = prompt_p3a
            if impr:
                texto = (f"CONTEXTO (já apurado na Parte 1): o período imprescrito começa em "
                         f"{impr}. Use EXATAMENTE esta data na linha divisória ▼▼▼.\n\n"
                         + prompt_p3a)
            return query(texto, "P3a(ficha dedicada)", None, alvo=nb_ficha[0])

        conv_id = None
        prompts = dict(blocos)
        # REGRAS: off (padrão) = não manda; priming = turno próprio; inline = cola na P1
        if regras_mode == "priming" and prompts.get("REGRAS"):
            res = query(prompts["REGRAS"], "REGRAS(priming)", None)
            conv_id = res.get("conversation_id")
            log(f"   ✓ REGRAS (priming) — conv {conv_id}")
        elif regras_mode == "inline" and prompts.get("REGRAS") and prompts.get("P1"):
            candidato = prompts["REGRAS"] + "\n\n" + prompts["P1"]
            if len(candidato) <= LIMITE_QUERY:
                prompts["P1"] = candidato
            else:
                log(f"   ⚠ REGRAS+P1 = {len(candidato)} chars > {LIMITE_QUERY}: caindo p/ priming.")
                res = query(prompts["REGRAS"], "REGRAS(priming)", None)
                conv_id = res.get("conversation_id")

        respostas = {}
        for key in ORDEM:
            prompt = prompts.get(key)
            if not prompt:
                respostas[key] = ""   # ausente → [NÃO LOCALIZADO] no pipeline
                log(f"   ⚠ {key}: ausente no arquivo de prompts")
                continue
            nota = ""
            if key == "P3a" and ficha:
                # fora da conversa do lote: leva o imprescrito da P1 no texto da pergunta
                res = query_ficha(prompt, imprescrito_de(respostas.get("P1")))
                # medir a origem AQUI: é o único ponto em que temos, ao mesmo tempo, o PDF da
                # ficha e o que o modelo declarou sobre ele. Só avisa, no console.
                try:
                    avisar_rotacao(ficha)
                    # TEXTO, não o envelope: query_ficha devolve dict ({"answer": …}) e o
                    # `ans = res.get("answer")` só acontece adiante. Passar `res` cru fazia a
                    # sonda inteira morrer em TypeError ("got 'dict'") e ser engolida pelo
                    # except abaixo — o guard não alarmava errado, calava. Medido no
                    # 0011183-33 (21/08/2026), ficha de 397 entregas sem conferência nenhuma.
                    p3a_txt = texto_resposta(res)
                    _origem, _ = conferir_origem_ficha(ficha, p3a_txt)
                    _, _, nota = conferir_contagem(ficha, p3a_txt, _origem)
                except Exception as e:
                    log(f"   ⚠ sonda da ficha falhou ({e}) — seguindo sem ela.")
            else:
                if key == "P3b" and ficha:
                    # a 3b cruza "a prática" (ficha) com "a norma"; como ela não viu a 3a nesta
                    # conversa, recebe o DIGEST da ficha — nunca a tabela inteira (não cabe).
                    digest = resumo_ficha(respostas.get("P3a"))
                    if digest and len(digest) + len(prompt) + 2 <= LIMITE_QUERY:
                        prompt = digest + "\n\n" + prompt
                    elif digest:
                        # não cabe: a 3b vai sem o contexto da ficha. Não é fatal (ela trata da
                        # NORMA), mas o perito precisa saber que o cruzamento saiu mais fraco.
                        log(f"   ⚠ P3b: digest da ficha ({len(digest)} chars) não coube no "
                            f"limite de {LIMITE_QUERY} — a 3b vai sem o resumo da ficha.")
                res = query(prompt, key, conv_id)
                conv_id = conv_id or res.get("conversation_id")
            ans = texto_resposta(res).strip()
            if not ans:
                raise FalhaPasta(f"query {key} voltou VAZIA (fonte faltando/indexação?)", nb_id)
            if nota:
                # ABAIXO da tabela: o parse_ficha_rows recorta as linhas `| … |` por data e
                # ignora o resto, então a nota no meio se perderia. Ele a reconhece pelo
                # prefixo e a iça para o topo da tabela do formulário.
                ans = ans + "\n\n" + nota
            respostas[key] = ans
            log(f"   ✓ {key}: {len(ans)} chars")

        # montar bundle
        bundle = "\n\n".join(limpar(respostas[k]) for k in ORDEM if respostas.get(k))
        # fallback do Nº: se a extração não achou (típico quando só há a inicial —
        # o número é atribuído no protocolo, não consta na peça), usa o nº do
        # NOME DA PASTA (o perito nomeia a subpasta pelo processo).
        bundle, num_injetado = injetar_numero(bundle, pasta.name)
        if num_injetado:
            log(f"   ↳ Nº preenchido pelo nome da pasta: {num_injetado}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(bundle, encoding="utf-8")
        log(f"📦 bundle: {out_path}  ({len(bundle)} chars)")
    except FalhaPasta:
        # falha → os DOIS notebooks ficam de pé para inspeção (achar pelo prefixo "EFÊMERO —")
        if not keep:
            log(f"🧷 notebook MANTIDO para inspeção: {nb_id} (título: {titulo}).")
            if nb_ficha[0]:
                log(f"🧷 notebook da ficha MANTIDO para inspeção: {nb_ficha[0]}.")
        raise

    apagar_ficha()
    apagar_ok()   # sucesso: bundle gravado → o pipeline reprocessa do bundle
    return out_path


def nome_bundle(pasta, cfg, cfg_path, out_override=None):
    if out_override:
        return Path(out_override)
    base_out = (cfg.get("caminhos", {}) or {}).get("formularios_campo")
    raiz = Path(cfg_path).parent if cfg_path else Path(pasta)
    out_dir = (raiz / base_out) if base_out else Path(pasta)
    # nome do processo: o próprio nome da subpasta se parecer nº CNJ, senão genérico
    nome = Path(pasta).name
    m = re.search(r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}", nome)
    slug = m.group(0) if m else re.sub(r"[^\w.-]+", "-", nome)[:60].strip("-")
    return out_dir / f"_bundle-{slug}.md"


def mover_processado(pasta, raiz_lote):
    dest_dir = Path(raiz_lote) / DIR_PROCESSADOS
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(pasta).name
    if dest.exists():
        i = 2
        while (dest_dir / f"{Path(pasta).name} ({i})").exists():
            i += 1
        dest = dest_dir / f"{Path(pasta).name} ({i})"
    shutil.move(str(pasta), str(dest))
    return dest


def main():
    ap = argparse.ArgumentParser(description="Extrai processo(s) → NotebookLM efêmero → bundle.")
    ap.add_argument("pasta", nargs="?", help="pasta com os 4 PDFs (modo single)")
    ap.add_argument("--lote", nargs="?", const="__CONFIG__", default=None,
                    help="modo LOTE: processa cada subpasta da pasta-mãe (default: config.notebooklm.pasta_processos)")
    ap.add_argument("--prompts", help="caminho do prompts-extracao-notebooklm.md (senão lê do config)")
    ap.add_argument("--out", help="[single] caminho do _bundle-<nº>.md (senão deriva)")
    ap.add_argument("--config", help="perito-config.json (senão auto-localiza)")
    ap.add_argument("--nlm", help="caminho do executável nlm (senão auto-localiza)")
    ap.add_argument("--regras", choices=["off", "priming", "inline"], default="off",
                    help="REGRAS GERAIS: off (padrão, P1 sozinha e cheia) | priming (turno próprio) | inline (cola na P1)")
    ap.add_argument("--wait-timeout", type=float, default=600.0)
    ap.add_argument("--query-timeout", type=float, default=300.0)
    ap.add_argument("--keep", action="store_true", help="NÃO apagar o notebook ao fim (debug)")
    ap.add_argument("--ficha-no-lote", action="store_true",
                    help="comportamento antigo: ficha de EPI junto no notebook do lote "
                         "(por padrão ela vai para um notebook próprio — ver T7)")
    ap.add_argument("--ficha-por-chat", action="store_true",
                    help="extrair a ficha pela resposta de CHAT em vez do artefato do Studio. "
                         "O chat TEM teto de resposta e trunca ficha grande sem avisar — use "
                         "só para comparar (ver T7.1)")
    ap.add_argument("--artefato-timeout", type=float, default=900.0,
                    help="quanto esperar o data-table da ficha ficar pronto (s)")
    args = ap.parse_args()

    if not args.pasta and args.lote is None:
        ap.error("informe uma pasta (single) ou --lote.")

    nlm = achar_nlm(args.nlm)
    log(f"🔧 nlm: {nlm}")

    ancora = args.pasta or (args.lote if args.lote and args.lote != "__CONFIG__" else None)
    cfg, cfg_path = {}, (Path(args.config) if args.config else None)
    if not cfg_path:
        cfg_path = achar_config(ancora) if ancora else achar_config(Path.cwd())
    if cfg_path and Path(cfg_path).exists():
        cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
        log(f"🔧 config: {cfg_path}")

    prompts_path = resolver_prompts(
        args.prompts or (cfg.get("notebooklm", {}) or {}).get("prompts_extracao"))
    if not prompts_path:
        sys.exit("ERRO: prompts não encontrados — passe --prompts com o caminho do "
                 "prompts-extracao-notebooklm.md.")
    blocos, faltando = ler_prompts(prompts_path)
    if "P1" in faltando:
        sys.exit(f"ERRO: PARTE 1 ausente no arquivo de prompts: {faltando}")
    if faltando:
        log(f"⚠ partes ausentes (viram [NÃO LOCALIZADO]): {faltando}")

    comum = dict(blocos=blocos, wait_timeout=args.wait_timeout,
                 query_timeout=args.query_timeout, regras_mode=args.regras, keep=args.keep,
                 ficha_no_lote=args.ficha_no_lote, ficha_por_chat=args.ficha_por_chat,
                 artefato_timeout=args.artefato_timeout)

    # ── modo SINGLE ──────────────────────────────────────────────────────────
    if args.lote is None:
        pasta = Path(args.pasta)
        if not pasta.is_dir():
            sys.exit(f"ERRO: pasta não encontrada: {pasta}")
        out_path = nome_bundle(pasta, cfg, cfg_path, args.out)
        try:
            bundle = processar_pasta(nlm, pasta, out_path=out_path, **comum)
        except FalhaPasta as e:
            sys.exit(f"ERRO: {e}")
        print(f"BUNDLE: {bundle}")
        return

    # ── modo LOTE ────────────────────────────────────────────────────────────
    raiz = Path(args.lote) if args.lote != "__CONFIG__" else None
    if raiz is None:
        p = (cfg.get("notebooklm", {}) or {}).get("pasta_processos")
        if not p:
            sys.exit("ERRO: --lote sem pasta e config sem notebooklm.pasta_processos.")
        raiz = Path(p)
    if not raiz.is_dir():
        sys.exit(f"ERRO: pasta-mãe do lote não existe: {raiz}")
    if args.out:
        log("⚠ --out é ignorado no modo lote (cada bundle é nomeado pelo nº do processo).")

    subs = [d for d in sorted(raiz.iterdir())
            if d.is_dir() and d.name != DIR_PROCESSADOS]
    if not subs:
        log(f"(nada a fazer: nenhuma subpasta de processo em {raiz})")
        return
    log(f"📚 LOTE: {len(subs)} subpasta(s) em {raiz}")

    ok, pulados, falhas = [], [], []
    for i, sub in enumerate(subs, 1):
        log(f"\n──────── [{i}/{len(subs)}] {sub.name} ────────")
        out_path = nome_bundle(sub, cfg, cfg_path)
        try:
            processar_pasta(nlm, sub, out_path=out_path, **comum)
        except FalhaPasta as e:
            msg = str(e)
            if "nenhum PDF" in msg:
                log(f"⏭️  PULADO: {msg}")
                pulados.append((sub.name, msg))
            else:
                log(f"❌ FALHOU: {msg}")
                falhas.append((sub.name, msg, e.notebook_id))
            continue
        dest = mover_processado(sub, raiz)
        log(f"📁 movido → {dest}")
        ok.append((sub.name, out_path))
        print(f"BUNDLE: {out_path}")

    # resumo
    log("\n════════ RESUMO DO LOTE ════════")
    log(f"✅ processados: {len(ok)}   ⏭️ pulados: {len(pulados)}   ❌ falhas: {len(falhas)}")
    for nome, _ in ok:
        log(f"   ✅ {nome}")
    for nome, msg in pulados:
        log(f"   ⏭️ {nome} — {msg}")
    for nome, msg, nbid in falhas:
        extra = f" [notebook mantido: {nbid}]" if nbid else ""
        log(f"   ❌ {nome} — {msg}{extra}")
    if falhas:
        sys.exit(1)


if __name__ == "__main__":
    main()
