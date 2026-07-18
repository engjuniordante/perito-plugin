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


def limpar(s):
    """Tira citações [n]/[1, 2]/[2-5] (preserva [X] [ ] [NÃO...]); tira ** e espaços órfãos."""
    s = re.sub(r"\[\d[\d,\s\-–]*\]", "", s)
    s = s.replace("**", "")
    s = re.sub(r"[ \t]+([.,;:])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


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
                    regras_mode, keep):
    pasta = Path(pasta)
    pdfs = achar_pdfs(pasta)
    if not pdfs:
        raise FalhaPasta("nenhum PDF de entrada na pasta (só FORMULÁRIO/LAUDO, ou vazia)")
    parcial = "" if len(pdfs) >= 4 else \
        f"  (PARCIAL — {len(pdfs)}/4 partes; o que faltar sai como [NÃO LOCALIZADO])"
    log(f"📄 {len(pdfs)} PDF(s): " + " · ".join(p.name for p in pdfs) + parcial)

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

    try:
        # subir os 4 PDFs esperando indexar (source add NÃO tem --json)
        for p in pdfs:
            _o, err = nlm_run(nlm, ["source", "add", nb_id, "--file", str(p),
                                    "--wait", "--wait-timeout", str(wait_timeout)],
                              timeout=wait_timeout + 60)
            if err:
                raise FalhaPasta(f"falha ao subir/indexar '{p.name}': {err}", nb_id)
            log(f"   ✓ indexado: {p.name}")

        # queries encadeadas
        def query(texto, key, conv):
            if len(texto) > LIMITE_QUERY:
                log(f"   ⚠ {key}: {len(texto)} chars (> {LIMITE_QUERY}) — pode dar INVALID_ARGUMENT.")
            qargs = ["notebook", "query", nb_id, texto, "--timeout", str(query_timeout)]
            if conv:
                qargs += ["-c", conv]
            res, err = nlm_json(nlm, qargs, timeout=query_timeout + 60)
            if err or not res:
                raise FalhaPasta(f"falha na query {key}: {err}", nb_id)
            return res

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
            res = query(prompt, key, conv_id)
            conv_id = conv_id or res.get("conversation_id")
            ans = (res.get("answer") or "").strip()
            if not ans:
                raise FalhaPasta(f"query {key} voltou VAZIA (fonte faltando/indexação?)", nb_id)
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
        if not keep:
            log(f"🧷 notebook MANTIDO para inspeção: {nb_id} (título: {titulo}).")
        raise

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
    blocos, faltando = ler_prompts(prompts_path)
    if "P1" in faltando:
        sys.exit(f"ERRO: PARTE 1 ausente no arquivo de prompts: {faltando}")
    if faltando:
        log(f"⚠ partes ausentes (viram [NÃO LOCALIZADO]): {faltando}")

    comum = dict(blocos=blocos, wait_timeout=args.wait_timeout,
                 query_timeout=args.query_timeout, regras_mode=args.regras, keep=args.keep)

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
