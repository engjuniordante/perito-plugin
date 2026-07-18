#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extrai_processo.py — fatia MECÂNICA do Modo B da skill 01b-extrator-nlm.

Pega os 4 PDFs de uma pasta de processo, cria um notebook EFÊMERO no
NotebookLM (via o CLI `nlm`, sem passar pelo modelo), sobe as 4 fontes
esperando indexar, roda os 5 prompts de extração (Partes 1, 2, 3a, 3b, 4)
ENCADEADOS no mesmo conversation_id, limpa as citações [n], grava o
_bundle-<nº>.md e APAGA o notebook. Zero token de modelo.

Depois, quem chama (a skill / o perito) roda o montar_formulario.py sobre o
bundle. O bundle basta para o pipeline — o notebook não é mais necessário —,
por isso é seguro apagá-lo assim que o bundle é gravado.

Uso típico (a skill preenche os caminhos a partir do perito-config.json):
    python extrai_processo.py "<pasta com os 4 PDFs>" \
        --prompts "<...>/prompts-extracao-notebooklm.md" \
        --out "<...>/Formularios-Campo/_bundle-<nº>.md"

Uso "na mão" (auto-descobre config subindo a partir da pasta):
    python extrai_processo.py "G:/.../Irineu teste/<SUBPASTA>"

Saída: escreve o caminho do bundle na ÚLTIMA linha do stdout, prefixado por
"BUNDLE: ". Sai com código != 0 se algo falhar (e, nesse caso, NÃO apaga o
notebook — deixa de pé para inspeção, informando o id).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── console UTF-8 (Windows cp1252 quebra com emoji/acentos) ──────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# PDFs que ficam na mesma pasta mas NÃO são entrada (são saída do fluxo).
DENYLIST = ("formulario", "formulário", "laudo")

# As 5 partes na ordem do bundle + a chave de cada heading no arquivo de prompts.
PARTES = [
    ("REGRAS", r"REGRAS\s+GERAIS"),
    ("P1", r"PARTE\s+1\b"),
    ("P2", r"PARTE\s+2\b"),
    ("P3a", r"PARTE\s+3a\b"),
    ("P3b", r"PARTE\s+3b\b"),
    ("P4", r"PARTE\s+4\b"),
]


def log(msg):
    print(msg, flush=True)


def die(msg, code=1):
    print(f"ERRO: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


# ── localizar o executável nlm ────────────────────────────────────────────────
def achar_nlm(explicit=None):
    if explicit:
        if Path(explicit).exists():
            return explicit
        die(f"--nlm apontado não existe: {explicit}")
    found = shutil.which("nlm")
    if found:
        return found
    # caminho conhecido no Windows (nlm.exe não costuma estar no PATH)
    appdata = os.environ.get("APPDATA", "")
    for base in (appdata,):
        if not base:
            continue
        for py in ("Python312", "Python311", "Python313", "Python310"):
            cand = Path(base) / "Python" / py / "Scripts" / "nlm.exe"
            if cand.exists():
                return str(cand)
    die("não encontrei o executável `nlm`. Rode `nlm login` uma vez ou passe --nlm <caminho>.")


# ── localizar e ler o perito-config.json (subindo a partir da pasta) ──────────
def achar_config(pasta):
    p = Path(pasta).resolve()
    for cand in [p, *p.parents]:
        cfg = cand / "perito-config.json"
        if cfg.exists():
            return cfg
    return None


# ── extrair os blocos de prompt do arquivo .md ────────────────────────────────
def ler_prompts(prompts_path):
    txt = Path(prompts_path).read_text(encoding="utf-8")
    linhas = txt.splitlines()
    # mapeia heading -> índice da linha
    blocos = {}
    heading_atual = None
    dentro = False
    buff = []
    key_ativa = None

    def casa_heading(linha):
        if not linha.lstrip().startswith("#"):
            return None
        # ignora explicitamente o prompt de Impugnação (é da Skill 4)
        if re.search(r"Impugna", linha, re.I):
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
                # abre bloco: só captura se a heading ativa é uma das nossas
                if key_ativa and key_ativa != "IGNORAR" and key_ativa not in blocos:
                    dentro = True
                    buff = []
                continue
            else:
                # fecha bloco
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
    p = Path(pasta)
    if not p.is_dir():
        die(f"pasta não encontrada: {pasta}")
    pdfs = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() != ".pdf":
            continue
        nome = f.stem.lower()
        if any(bad in nome for bad in DENYLIST):
            continue
        pdfs.append(f)
    return pdfs


# ── chamadas ao nlm ───────────────────────────────────────────────────────────
def nlm_run(nlm, args, timeout=None):
    """Roda `nlm ...` (sem --json). Devolve (stdout, erro-ou-None)."""
    cp = subprocess.run(
        [nlm, *args],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    return (cp.stdout or "").strip(), None


def nlm_json(nlm, args, timeout=None):
    """Roda `nlm ... --json` e devolve o dict do stdout."""
    cp = subprocess.run(
        [nlm, *args, "--json"],
        capture_output=True, text=True, encoding="utf-8", timeout=timeout,
    )
    if cp.returncode != 0:
        return None, (cp.stderr or cp.stdout or f"exit {cp.returncode}").strip()
    out = (cp.stdout or "").strip()
    # o nlm às vezes emite linhas de log antes do JSON; pega o último bloco {...}
    m = re.search(r"\{.*\}\s*$", out, re.S)
    raw = m.group(0) if m else out
    try:
        return json.loads(raw), None
    except json.JSONDecodeError:
        return None, f"resposta não-JSON do nlm: {out[:400]}"


def main():
    ap = argparse.ArgumentParser(description="Extrai processo → NotebookLM efêmero → bundle.")
    ap.add_argument("pasta", help="pasta com os 4 PDFs do processo")
    ap.add_argument("--prompts", help="caminho do prompts-extracao-notebooklm.md (senão lê do config)")
    ap.add_argument("--out", help="caminho do _bundle-<nº>.md a gerar (senão deriva do nº do processo)")
    ap.add_argument("--config", help="perito-config.json (senão auto-localiza subindo da pasta)")
    ap.add_argument("--nlm", help="caminho do executável nlm (senão auto-localiza)")
    ap.add_argument("--wait-timeout", type=float, default=600.0, help="seg. p/ indexar cada fonte (def. 600)")
    ap.add_argument("--query-timeout", type=float, default=300.0, help="seg. por query (def. 300)")
    ap.add_argument("--keep", action="store_true", help="NÃO apagar o notebook ao fim (debug)")
    args = ap.parse_args()

    nlm = achar_nlm(args.nlm)
    log(f"🔧 nlm: {nlm}")

    # config (para prompts e pasta de saída)
    cfg = {}
    cfg_path = Path(args.config) if args.config else achar_config(args.pasta)
    if cfg_path and Path(cfg_path).exists():
        cfg = json.loads(Path(cfg_path).read_text(encoding="utf-8"))
        log(f"🔧 config: {cfg_path}")

    prompts_path = args.prompts or (cfg.get("notebooklm", {}) or {}).get("prompts_extracao")
    if not prompts_path:
        die("prompts não informado e config sem notebooklm.prompts_extracao — passe --prompts.")
    if not Path(prompts_path).exists():
        die(f"arquivo de prompts não existe: {prompts_path}")

    blocos, faltando = ler_prompts(prompts_path)
    if "REGRAS" in faltando or "P1" in faltando:
        die(f"prompts essenciais ausentes no arquivo: {faltando}")
    if faltando:
        log(f"⚠ partes ausentes no arquivo de prompts (viram [NÃO LOCALIZADO]): {faltando}")

    pdfs = achar_pdfs(args.pasta)
    if len(pdfs) != 4:
        listagem = "\n".join(f"  - {p.name}" for p in pdfs) or "  (nenhum)"
        die(f"esperava 4 PDFs de entrada na pasta, achei {len(pdfs)}:\n{listagem}\n"
            f"Confira/renomeie (1-inicial, 2-contestação, 3-EPI, 4-ata+quesitos) e rode de novo.")
    log("📄 PDFs de entrada:")
    for p in pdfs:
        log(f"   • {p.name}")

    titulo = f"EFÊMERO — {Path(args.pasta).name}"

    # 1) criar notebook
    nb, err = nlm_json(nlm, ["notebook", "create", titulo])
    if not nb:
        die(f"falha ao criar notebook: {err}")
    nb_id = nb.get("id") or nb.get("notebook_id") or (nb.get("notebook") or {}).get("id")
    if not nb_id:
        die(f"não achei o id do notebook criado: {nb}")
    log(f"🆕 notebook: {nb_id} ({titulo})")

    def apagar(motivo_ok):
        if args.keep:
            log(f"🧷 --keep: notebook MANTIDO ({nb_id}).")
            return
        if not motivo_ok:
            log(f"🧷 notebook MANTIDO para inspeção: {nb_id} (título: {titulo}).")
            return
        cp = subprocess.run([nlm, "notebook", "delete", nb_id, "-y"],
                            capture_output=True, text=True, encoding="utf-8")
        if cp.returncode == 0:
            log(f"🗑️  notebook efêmero apagado: {nb_id}")
        else:
            log(f"⚠ não consegui apagar o notebook {nb_id}: {(cp.stderr or cp.stdout).strip()}")

    # 2) subir os 4 PDFs, esperando indexar (source add NÃO tem --json)
    for p in pdfs:
        _out, err = nlm_run(
            nlm,
            ["source", "add", nb_id, "--file", str(p), "--wait",
             "--wait-timeout", str(args.wait_timeout)],
            timeout=args.wait_timeout + 60,
        )
        if err:
            apagar(motivo_ok=False)
            die(f"falha ao subir/indexar '{p.name}': {err}")
        log(f"   ✓ indexado: {p.name}")

    # 3) rodar as queries encadeadas.
    # ⚠ A query do NotebookLM tem LIMITE de tamanho (~4.8k chars por mensagem).
    # Por isso as REGRAS GERAIS não são coladas na P1 (REGRAS+P1 estoura o
    # limite): vão como um TURNO DE PRIMING próprio — o contexto fica na
    # conversa — e cada Parte segue encadeada no mesmo conversation_id.
    LIMITE = 4700

    def query(texto, key, conv):
        if len(texto) > LIMITE:
            log(f"   ⚠ {key}: prompt tem {len(texto)} chars (> {LIMITE}) — o NotebookLM pode rejeitar (INVALID_ARGUMENT).")
        qargs = ["notebook", "query", nb_id, texto, "--timeout", str(args.query_timeout)]
        if conv:
            qargs += ["-c", conv]
        res, err = nlm_json(nlm, qargs, timeout=args.query_timeout + 60)
        if err or not res:
            apagar(motivo_ok=False)
            die(f"falha na query {key}: {err}")
        return res

    # priming com as REGRAS GERAIS (a resposta é descartada; serve de contexto)
    res = query(blocos["REGRAS"], "REGRAS(priming)", None)
    conv_id = res.get("conversation_id")
    if not conv_id:
        apagar(motivo_ok=False)
        die("priming das REGRAS não devolveu conversation_id.")
    log(f"   ✓ REGRAS (priming) — conv {conv_id}")

    ordem = ["P1", "P2", "P3a", "P3b", "P4"]
    respostas = {}
    for key in ordem:
        prompt = blocos.get(key)
        if not prompt:
            respostas[key] = ""  # ausente → [NÃO LOCALIZADO] no pipeline
            log(f"   ⚠ {key}: ausente no arquivo de prompts")
            continue
        res = query(prompt, key, conv_id)
        ans = (res.get("answer") or "").strip()
        if not ans:
            apagar(motivo_ok=False)
            die(f"query {key} voltou VAZIA — provável fonte faltando/indexação. Notebook mantido.")
        respostas[key] = ans
        log(f"   ✓ {key}: {len(ans)} chars")

    # 4) limpar citações e montar o bundle
    def limpar(s):
        s = re.sub(r"\[\d[\d,\s\-–]*\]", "", s)   # tira [4] [1, 2] [2-5]; preserva [X] [ ] [NÃO...]
        s = s.replace("**", "")
        s = re.sub(r"[ \t]+([.,;:])", r"\1", s)
        s = re.sub(r"[ \t]{2,}", " ", s)
        return s.strip()

    bundle = "\n\n".join(limpar(respostas[k]) for k in ordem if respostas.get(k))

    # nº do processo (para nomear o bundle) — do P1
    m = re.search(r"N[ºo]\s*:?\s*([\d.\-]{15,})", respostas.get("P1", ""))
    num = (m.group(1).strip(" .") if m else "").rstrip(".")

    if args.out:
        out_path = Path(args.out)
    else:
        base_out = (cfg.get("caminhos", {}) or {}).get("formularios_campo")
        cfg_dir = Path(cfg_path).parent if cfg_path else Path(args.pasta)
        out_dir = (cfg_dir / base_out) if base_out else Path(args.pasta)
        nome = f"_bundle-{num}.md" if num else "_bundle.md"
        out_path = out_dir / nome
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bundle, encoding="utf-8")
    log(f"📦 bundle: {out_path}  ({len(bundle)} chars)")

    # 5) apagar o notebook (bundle já salvo = sucesso; pipeline reprocessa do bundle)
    apagar(motivo_ok=True)

    # última linha, para quem chamou capturar o caminho
    print(f"BUNDLE: {out_path}")


if __name__ == "__main__":
    main()
