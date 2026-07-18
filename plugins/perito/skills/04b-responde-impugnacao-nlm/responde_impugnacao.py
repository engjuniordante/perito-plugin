#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
responde_impugnacao.py — fatia MECÂNICA da skill 04b-responde-impugnacao-nlm.

Irmão do extrai_processo.py (skill 01b), mas para IMPUGNAÇÕES. Pega uma pasta de
processo com o LAUDO + a(s) PETIÇÃO(ÕES) de impugnação, cria um notebook EFÊMERO no
NotebookLM (via o CLI `nlm`, sem passar pelo modelo), sobe as fontes esperando
indexar, roda UM prompt (o de Impugnação, verbatim do prompts-extracao-notebooklm.md),
limpa as citações [n], parseia a minuta em campos + corpo, CORTA o fecho duplicado
(que já é fixo no template), compõe a frase de abertura (1 OU 2 partes), monta o JSON
e chama o build_impugnacao.py → esclarecimentos-<nº>.docx. Depois APAGA o notebook.
Zero token de modelo.

Dois modos:
  • UMA pasta:  python responde_impugnacao.py "<pasta com laudo + impugnação>"
  • LOTE (fila): python responde_impugnacao.py --lote ["<pasta-mãe>"]
      Processa CADA subpasta (nº do processo) da pasta-mãe em fila; a cada sucesso
      MOVE a subpasta para "<pasta-mãe>/Processados/". Sem argumento, a pasta-mãe sai
      de config.notebooklm.pasta_impugnacoes.

Saída: para cada pasta processada imprime "DOCX: <caminho>". Sai com código != 0 se a
(única) pasta falhar; em lote, segue a fila e resume no fim.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

# ── console UTF-8 (Windows cp1252 quebra com emoji/acentos) ──────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# importar o build_impugnacao.py (caixa-preta) da skill irmã 04-responde-impugnacao
_AQUI = Path(__file__).resolve().parent
_BUILD_DIR = _AQUI.parent / "04-responde-impugnacao" / "scripts"
sys.path.insert(0, str(_BUILD_DIR))
try:
    import build_impugnacao  # noqa: E402
except Exception as _e:   # pragma: no cover
    build_impugnacao = None
    _IMPORT_ERR = _e

# Template bundled (versionado junto do build) — o contrato do .docx é acoplado a
# esta versão do build/script, então NÃO usamos a cópia do Drive (pode estar velha).
TEMPLATE_BUNDLED = (_AQUI.parent / "04-responde-impugnacao" / "assets"
                    / "templates" / "template-impugnacao.docx")

# Arquivos que ficam na pasta mas NÃO são fonte (são saída do fluxo).
DENYLIST = ("esclarecimento", "formulario", "formulário")
# Extensões aceitas como fonte no NotebookLM (o laudo costuma ser PDF; docx best-effort).
SOURCE_EXTS = (".pdf", ".docx", ".txt", ".md")
DIR_PROCESSADOS = "Processados"
LIMITE_QUERY = 4700
CNJ_RE = r"\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}"
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
         "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def log(msg):
    print(msg, flush=True)


class FalhaPasta(RuntimeError):
    """Falha ao processar uma pasta; carrega o id do notebook mantido (se houver)."""
    def __init__(self, msg, notebook_id=None):
        super().__init__(msg)
        self.notebook_id = notebook_id


# ── localizar o executável nlm (igual ao extrai_processo.py) ──────────────────
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


# ── extrair o bloco do prompt de IMPUGNAÇÃO do prompts-extracao-notebooklm.md ──
def ler_prompt_impugnacao(prompts_path):
    """Devolve o bloco de código (``` … ```) logo abaixo do heading que casa 'Impugna'."""
    linhas = Path(prompts_path).read_text(encoding="utf-8").splitlines()
    dentro = False
    buff = []
    armado = False   # já passamos pelo heading de Impugnação
    for linha in linhas:
        if linha.lstrip().startswith("#") and re.search(r"Impugna", linha, re.I):
            armado = True
            continue
        if armado and linha.strip().startswith("```"):
            if not dentro:
                dentro = True
                buff = []
                continue
            return "\n".join(buff).strip()
        if dentro:
            buff.append(linha)
    return None


# ── achar as fontes (laudo + impugnação[ões]) ─────────────────────────────────
def achar_fontes(pasta):
    fontes = []
    for f in sorted(Path(pasta).iterdir()):
        if f.suffix.lower() not in SOURCE_EXTS:
            continue
        if any(bad in f.stem.lower() for bad in DENYLIST):
            continue
        fontes.append(f)
    return fontes


# ── chamadas ao nlm (igual ao extrai_processo.py) ─────────────────────────────
def nlm_run(nlm, args, timeout=None):
    cp = subprocess.run([nlm, *args], capture_output=True, text=True,
                        encoding="utf-8", timeout=timeout)
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    return (cp.stdout or "").strip(), None


def nlm_json(nlm, args, timeout=None):
    cp = subprocess.run([nlm, *args, "--json"], capture_output=True, text=True,
                        encoding="utf-8", timeout=timeout)
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    out = (cp.stdout or "").strip()
    m = re.search(r"\{.*\}\s*$", out, re.S)
    try:
        return json.loads(m.group(0) if m else out), None
    except json.JSONDecodeError:
        return None, f"resposta não-JSON do nlm: {out[:300]}"


def limpar(s):
    """Tira citações [n]/[1, 2]/[2-5]; tira ** e espaços órfãos (igual ao extrator)."""
    s = re.sub(r"\[\d[\d,\s\-–]*\]", "", s)
    s = s.replace("**", "")
    s = re.sub(r"[ \t]+([.,;:])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


# ── parsear a minuta do NLM → campos + corpo ──────────────────────────────────
HEADER_KEYS = ("CIDADE_VARA", "NUMERO_PROCESSO", "NOME_RECLAMANTE",
               "NOME_RECLAMADA", "IMPUGNANTES")
# fecho fixo do template — cortar da minuta pra não sair em dobro (sem acento p/ robustez)
FECHO_PREFIXOS = ("pelo exposto", "em razao de todo o exposto")


def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def _compor_intro(impugnantes):
    """impugnantes = [(parte, id), ...] → frase de abertura (1 ou 2 partes)."""
    def um(parte, idv):
        idv = idv or "____"
        return f"do(a) {parte} conforme Id. {idv}"
    if not impugnantes:
        return "para a impugnação protocolada pelo Ilustre Patrono ____ conforme Id. ____"
    if len(impugnantes) == 1:
        p, i = impugnantes[0]
        return f"para a impugnação protocolada pelo Ilustre Patrono {um(p, i)}"
    partes = " e ".join(um(p, i) for p, i in impugnantes)
    return f"para as impugnações protocoladas pelos Ilustres Patronos {partes}"


def _parse_impugnantes(valor, corpo_titulos):
    """Do valor de IMPUGNANTES ('Reclamada (Id. x)' ou 'Reclamante (Id. a); Reclamada
    (Id. b)') tira [(parte, id), ...]. Se vazio, deriva as partes dos títulos do corpo."""
    out = []
    if valor:
        for item in re.split(r"[;/]", valor):
            m = re.search(r"(Reclamante|Reclamada)", item, re.I)
            if not m:
                continue
            parte = m.group(1).capitalize()
            mid = re.search(r"Id\.?\s*([^)\]]+)", item, re.I)
            idv = mid.group(1).strip() if mid else None
            if idv and re.search(r"não\s+localizad", idv, re.I):
                idv = None
            out.append((parte, idv))
    if not out:   # sem header → deriva dos títulos "ESCLARECIMENTOS SOLICITADOS PELA X"
        for t in corpo_titulos:
            m = re.search(r"PELA?\s+(RECLAMANTE|RECLAMADA)", t, re.I)
            if m:
                parte = m.group(1).capitalize()
                if parte not in [p for p, _ in out]:
                    out.append((parte, None))
    return out


def parse_minuta(texto, pasta_name):
    """texto (minuta crua do NLM) → (scalars, esclarecimentos, flags)."""
    flags = []
    linhas = [limpar(l) for l in texto.splitlines()]

    # 1) header — linhas 'CHAVE: valor' (com ou sem '- ' na frente) ANTES do corpo
    campos = {}
    idx_corpo = None
    for i, l in enumerate(linhas):
        if re.match(r"^\s*-?\s*ESCLARECIMENTOS\s+SOLICITADOS", l, re.I):
            idx_corpo = i
            break
        m = re.match(r"^\s*-?\s*([A-Z_]+)\s*:\s*(.+?)\s*$", l)
        if m and m.group(1) in HEADER_KEYS:
            campos[m.group(1)] = m.group(2).strip()

    # 2) corpo — do 1º "ESCLARECIMENTOS SOLICITADOS" em diante (se não houver, tudo)
    corpo_linhas = linhas[idx_corpo:] if idx_corpo is not None else linhas
    esclarecimentos = []
    for l in corpo_linhas:
        s = l.strip().strip("-").strip()
        if not s:
            continue
        low = _sem_acento(s)
        if any(low.startswith(p) for p in FECHO_PREFIXOS):   # fecho já é fixo no template
            continue
        esclarecimentos.append(s)

    titulos = [e for e in esclarecimentos if e.upper().startswith("ESCLARECIMENTOS SOLICITADOS")]
    if not titulos:
        flags.append("nenhum título 'ESCLARECIMENTOS SOLICITADOS PELA …' no corpo do NLM")

    # 3) scalars
    scalars = {}
    for k in ("CIDADE_VARA", "NUMERO_PROCESSO", "NOME_RECLAMANTE", "NOME_RECLAMADA"):
        v = campos.get(k, "").strip()
        if not v or re.search(r"não\s+localizad", v, re.I):
            v = "____"
            flags.append(f"{k} não localizado na minuta do NLM")
        scalars[k] = v

    # nº do processo: se faltou, tenta o nome da pasta (nomeada pelo nº)
    if scalars["NUMERO_PROCESSO"] == "____":
        m = re.search(CNJ_RE, pasta_name)
        if m:
            scalars["NUMERO_PROCESSO"] = m.group(0)
            flags = [f for f in flags if not f.startswith("NUMERO_PROCESSO")]
            flags.append(f"NUMERO_PROCESSO preenchido pelo nome da pasta: {m.group(0)}")

    impugnantes = _parse_impugnantes(campos.get("IMPUGNANTES", ""), titulos)
    if not impugnantes:
        flags.append("PARTE(S) impugnante(s) não identificada(s) — INTRO_IMPUGNANTE ficará com ____")
    scalars["INTRO_IMPUGNANTE"] = _compor_intro(impugnantes)

    hoje = datetime.date.today()
    scalars["DATA_EXTENSO"] = f"{hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}"

    return scalars, esclarecimentos, flags


def slug_processo(pasta_name):
    m = re.search(CNJ_RE, pasta_name)
    return m.group(0) if m else re.sub(r"[^\w.-]+", "-", pasta_name)[:60].strip("-")


def nome_saida(pasta, cfg, cfg_path, out_override=None):
    if out_override:
        return Path(out_override)
    base_out = (cfg.get("caminhos", {}) or {}).get("saida_laudos")
    raiz = Path(cfg_path).parent if cfg_path else Path(pasta)
    out_dir = (raiz / base_out) if base_out else Path(pasta)
    return out_dir / f"esclarecimentos-{slug_processo(Path(pasta).name)}.docx"


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


# ── processar UMA pasta: pasta → docx (cria/sobe/consulta/parseia/build/apaga) ─
def processar_pasta(nlm, pasta, prompt, template, perito_nome, nomes_proibidos,
                    out_path, wait_timeout, query_timeout, keep):
    pasta = Path(pasta)
    fontes = achar_fontes(pasta)
    if not fontes:
        raise FalhaPasta("nenhuma fonte na pasta (esperado laudo + impugnação em PDF)")
    log(f"📄 {len(fontes)} fonte(s): " + " · ".join(f.name for f in fontes))

    if len(prompt) > LIMITE_QUERY:
        log(f"   ⚠ prompt de impugnação tem {len(prompt)} chars (> {LIMITE_QUERY}) — pode dar INVALID_ARGUMENT.")

    titulo = f"EFÊMERO IMPUG — {pasta.name}"
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

    try:
        for p in fontes:
            _o, err = nlm_run(nlm, ["source", "add", nb_id, "--file", str(p),
                                    "--wait", "--wait-timeout", str(wait_timeout)],
                              timeout=wait_timeout + 60)
            if err:
                raise FalhaPasta(f"falha ao subir/indexar '{p.name}': {err}", nb_id)
            log(f"   ✓ indexado: {p.name}")

        qargs = ["notebook", "query", nb_id, prompt, "--timeout", str(query_timeout)]
        res, err = nlm_json(nlm, qargs, timeout=query_timeout + 60)
        if err or not res:
            raise FalhaPasta(f"falha na query de impugnação: {err}", nb_id)
        minuta = (res.get("answer") or "").strip()
        if not minuta:
            raise FalhaPasta("query voltou VAZIA (fonte faltando/indexação?)", nb_id)
        log(f"   ✓ minuta: {len(minuta)} chars")

        scalars, esclarecimentos, flags = parse_minuta(minuta, pasta.name)
        if not esclarecimentos:
            raise FalhaPasta("minuta sem corpo de esclarecimentos após o parse", nb_id)

        data = {"perito_nome": perito_nome, "scalars": scalars,
                "esclarecimentos": esclarecimentos}
        if nomes_proibidos:
            data["nomes_proibidos"] = nomes_proibidos

        out_path.parent.mkdir(parents=True, exist_ok=True)
        json_dbg = out_path.with_suffix(".json")
        json_dbg.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        if build_impugnacao is None:
            raise FalhaPasta(f"não consegui importar build_impugnacao: {_IMPORT_ERR}", nb_id)
        ok = build_impugnacao.build(str(template), str(json_dbg), str(out_path))
        if not ok:
            raise FalhaPasta("build_impugnacao recusou o documento (veja o relatório acima)", nb_id)
        log(f"📦 docx: {out_path}")
        for f in flags:
            log(f"   🚩 {f}")
    except FalhaPasta:
        if not keep:
            log(f"🧷 notebook MANTIDO para inspeção: {nb_id} (título: {titulo}).")
        raise

    apagar_ok()
    return out_path, flags


def main():
    ap = argparse.ArgumentParser(description="Impugnação: pasta → NotebookLM efêmero → esclarecimentos.docx.")
    ap.add_argument("pasta", nargs="?", help="pasta com laudo + impugnação (modo single)")
    ap.add_argument("--lote", nargs="?", const="__CONFIG__", default=None,
                    help="modo LOTE: cada subpasta da pasta-mãe (default: config.notebooklm.pasta_impugnacoes)")
    ap.add_argument("--prompts", help="caminho do prompts-extracao-notebooklm.md (senão lê do config)")
    ap.add_argument("--template", help="template .docx (senão usa o BUNDLED do plugin)")
    ap.add_argument("--out", help="[single] caminho do esclarecimentos-<nº>.docx (senão deriva)")
    ap.add_argument("--config", help="perito-config.json (senão auto-localiza)")
    ap.add_argument("--nlm", help="caminho do executável nlm (senão auto-localiza)")
    ap.add_argument("--wait-timeout", type=float, default=600.0)
    ap.add_argument("--query-timeout", type=float, default=420.0)
    ap.add_argument("--keep", action="store_true", help="NÃO apagar o notebook ao fim (debug)")
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

    prompts_path = args.prompts or (cfg.get("notebooklm", {}) or {}).get("prompts_extracao")
    if not prompts_path or not Path(prompts_path).exists():
        sys.exit(f"ERRO: prompts não encontrados ({prompts_path!r}) — passe --prompts.")
    prompt = ler_prompt_impugnacao(prompts_path)
    if not prompt:
        sys.exit(f"ERRO: não achei o bloco do prompt de Impugnação em {prompts_path}.")
    log(f"🔧 prompt de impugnação: {len(prompt)} chars")

    template = Path(args.template) if args.template else TEMPLATE_BUNDLED
    if not Path(template).exists():
        sys.exit(f"ERRO: template não encontrado: {template}")
    log(f"🔧 template: {template}")

    perito_nome = (cfg.get("perito", {}) or {}).get("nome") or "Irineu de Freitas Branco Junior"
    nomes_proibidos = (cfg.get("perito", {}) or {}).get("nomes_proibidos") or []

    comum = dict(prompt=prompt, template=template, perito_nome=perito_nome,
                 nomes_proibidos=nomes_proibidos, wait_timeout=args.wait_timeout,
                 query_timeout=args.query_timeout, keep=args.keep)

    # ── modo SINGLE ──────────────────────────────────────────────────────────
    if args.lote is None:
        pasta = Path(args.pasta)
        if not pasta.is_dir():
            sys.exit(f"ERRO: pasta não encontrada: {pasta}")
        out_path = nome_saida(pasta, cfg, cfg_path, args.out)
        try:
            docx_path, _flags = processar_pasta(nlm, pasta, out_path=out_path, **comum)
        except FalhaPasta as e:
            sys.exit(f"ERRO: {e}")
        print(f"DOCX: {docx_path}")
        return

    # ── modo LOTE ────────────────────────────────────────────────────────────
    raiz = Path(args.lote) if args.lote != "__CONFIG__" else None
    if raiz is None:
        p = (cfg.get("notebooklm", {}) or {}).get("pasta_impugnacoes")
        if not p:
            sys.exit("ERRO: --lote sem pasta e config sem notebooklm.pasta_impugnacoes.")
        raiz = Path(p)
    if not raiz.is_dir():
        sys.exit(f"ERRO: pasta-mãe do lote não existe: {raiz}")
    if args.out:
        log("⚠ --out é ignorado no modo lote (cada docx é nomeado pelo nº do processo).")

    subs = [d for d in sorted(raiz.iterdir())
            if d.is_dir() and d.name != DIR_PROCESSADOS]
    if not subs:
        log(f"(nada a fazer: nenhuma subpasta de processo em {raiz})")
        return
    log(f"📚 LOTE: {len(subs)} subpasta(s) em {raiz}")

    ok, pulados, falhas = [], [], []
    for i, sub in enumerate(subs, 1):
        log(f"\n──────── [{i}/{len(subs)}] {sub.name} ────────")
        out_path = nome_saida(sub, cfg, cfg_path)
        try:
            processar_pasta(nlm, sub, out_path=out_path, **comum)
        except FalhaPasta as e:
            msg = str(e)
            if "nenhuma fonte" in msg:
                log(f"⏭️  PULADO: {msg}")
                pulados.append((sub.name, msg))
            else:
                log(f"❌ FALHOU: {msg}")
                falhas.append((sub.name, msg, e.notebook_id))
            continue
        dest = mover_processado(sub, raiz)
        log(f"📁 movido → {dest}")
        ok.append((sub.name, out_path))
        print(f"DOCX: {out_path}")

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
