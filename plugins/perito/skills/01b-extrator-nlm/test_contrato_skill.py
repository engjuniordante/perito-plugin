#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contrato_skill.py — as travas do TEXTO da skill 01b e do gate do `nlm`.

Roda offline: nada aqui fala com o NotebookLM. O que ele trava são as duas
maneiras conhecidas de a extração cair na via errada — a que põe os 4 PDFs num
notebook só e devolve uma ficha de EPI plausível e ERRADA:

  A. o `\n` comido. Editar a SKILL.md por um caminho que interpreta escape
     transforma `Scripts\nlm.exe` numa quebra de linha de verdade, e o comando
     que o modelo deveria rodar sai partido em duas linhas — foi o que
     aconteceu na v1.6.1, e é o motivo de a correção não ter pegado. Um code
     span de crase que não fecha na mesma linha é a assinatura disso.
  B. a via na mão à mão. Enquanto o passo a passo do `source_add` estiver
     escrito na SKILL.md, ele é a saída fácil de qualquer tropeço — o aviso em
     prosa perde para o procedimento pronto logo abaixo dele. Ele agora vive em
     assets/fallback-mcp-na-mao.md e só é aberto de propósito.

  C. e o gate: quem diz se o `nlm` existe é `localizar_nlm()`, nunca o olho do
     modelo num `command not found`.

    python test_contrato_skill.py
"""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from extrai_processo import (          # noqa: E402
    localizar_nlm, versao_nlm, doctor, NLM_MINIMO,
)

falhas = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        falhas.append(label)


def linhas_fora_de_fence(caminho):
    """(nº, texto) de cada linha que NÃO está dentro de um bloco ``` … ```."""
    dentro, saida, fences = False, [], 0
    for n, l in enumerate(caminho.read_text(encoding="utf-8").split("\n"), 1):
        if l.strip().startswith("```"):
            fences += 1
            dentro = not dentro
            continue
        if not dentro:
            saida.append((n, l))
    return saida, fences


SKILL = AQUI / "SKILL.md"
FALLBACK = AQUI / "assets" / "fallback-mcp-na-mao.md"

# ── A. o `\n` comido: code span tem de abrir e fechar na MESMA linha ─────────
print("A — nenhum code span de crase atravessa quebra de linha (o bug da v1.6.1)")

for doc in (SKILL, FALLBACK):
    fora, fences = linhas_fora_de_fence(doc)
    tortas = [(n, l) for n, l in fora if l.count("`") % 2]
    ok(not tortas,
       f"{doc.name}: crases pareadas em cada linha" +
       ("" if not tortas else f" — quebradas: {[n for n, _ in tortas]}"))
    ok(fences % 2 == 0, f"{doc.name}: blocos ``` fechados ({fences} marcadores)")

texto_skill = SKILL.read_text(encoding="utf-8")
ok("\nlm.exe" not in texto_skill,
   "SKILL.md: nenhum 'lm.exe' órfão no começo de linha (assinatura do \n comido)")
ok(not any(l.rstrip().endswith("Scripts") for _, l in linhas_fora_de_fence(SKILL)[0]),
   "SKILL.md: nenhuma linha termina no meio de um caminho de Scripts")

# ── B. a via na mão NÃO mora na SKILL ────────────────────────────────────────
print()
print("B — o passo a passo da MCP na mão vive fora da SKILL, não à mão do modelo")

# `conversation_id` NÃO entra nesta lista: o encadeamento das queries é legítimo no
# Passo 3, que serve ao Modo A. O que não pode morar aqui é a receita de CRIAR o
# notebook e SUBIR as fontes na mão — é ela que põe os 4 PDFs juntos.
for proibido in ("source_add(", "notebook_create("):
    ok(proibido not in texto_skill,
       f"SKILL.md não traz `{proibido}` (receita na mão fica no asset)")

ok("Passos 2 e 3 são do MODO A" in texto_skill,
   "Passos 2/3 marcados como do Modo A — vindo do Modo B, o próximo passo é o 4")
ok("Script fora do ar = **PARAR**" in texto_skill,
   "regra de ouro: script fora do ar = parar, não descer para a mão")

ok(FALLBACK.exists(), "assets/fallback-mcp-na-mao.md existe")
texto_fb = FALLBACK.read_text(encoding="utf-8")
ok("source_add(" in texto_fb, "…e é ele quem guarda o passo a passo")
for guarda in ("doctor", "ficha", "PARAR"):
    ok(guarda in texto_fb, f"…e abre com a própria trava ({guarda!r})")
ok("fallback-mcp-na-mao.md" in texto_skill,
   "SKILL.md aponta o asset (a exceção continua alcançável, só não é o caminho fácil)")

# ── C. o gate é comando, não julgamento ──────────────────────────────────────
print()
print("C — o Passo 0 manda rodar o --doctor, e o --doctor decide por código")

ok("--doctor" in texto_skill, "SKILL.md manda rodar `extrai_processo.py --doctor`")
ok("nlm --version" not in texto_skill,
   "SKILL.md não manda mais rodar `nlm --version` cru (era o falso positivo)")
ok("VEREDITO" in texto_skill, "SKILL.md manda obedecer o VEREDITO do doctor")

ok(localizar_nlm(str(AQUI / "nao-existe-nlm.exe")) is None,
   "localizar_nlm(caminho inexistente) → None, sem derrubar o processo "
   "(o achar_nlm antigo dava sys.exit e não servia para diagnosticar)")
ok(NLM_MINIMO == (0, 9, 4), "piso de versão continua 0.9.4 (domínio notebook.google.com)")

txt, ver = versao_nlm(str(AQUI / "nao-existe-nlm.exe"))
ok(ver is None and "falhou" in txt.lower(),
   "versao_nlm de um executável que não roda → (motivo, None), sem exceção")

ok(callable(doctor), "doctor() exportado para o Passo 0")

# ── D. o Modo A não é saída para um Modo B que tropeçou ──────────────────────
print()
print("D — trocar de modo no meio do caminho está fechado")

ok("nunca** é saída para um Modo B" in texto_skill,
   "Modo A declarado NÃO-fallback do Modo B")
ok("não se troca de modo" in texto_skill,
   "uma vez em Modo B, não se troca de modo")
ok("Modo A está PROIBIDO" in texto_skill,
   "com ficha em arquivo separado, o Modo A está proibido")

# ── resultado ────────────────────────────────────────────────────────────────
print()
if falhas:
    print(f"FALHOU ({len(falhas)}):")
    for f in falhas:
        print("  - " + f)
    sys.exit(1)
print("✓ tudo verde — contrato do texto da skill 01b e do gate do nlm")
