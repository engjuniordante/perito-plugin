#!/usr/bin/env python3
"""Regressão da limpeza das caixinhas de conversa do NotebookLM/Gemini Notebook.

O NLM varia o ícone da caixinha conforme o artefato do Studio que oferece (💡 → 📊/🎧/🧩),
então o filtro ancora no TEXTO. Os ícones do formulário do perito (▶ ★ ▼ 🔄 👤) têm de
sobreviver intactos — o guard de EPI depende do ▼▼▼.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import montar_formulario as mf

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def t_caixinhas_removidas():
    print("S1 — caixinhas de sugestão são descartadas (qualquer ícone)")
    for icone in ("💡", "📊", "🎧", "🧩", "✅"):
        txt = (f"- Nº: 0010094-14.2026.5.15.0079\n\n"
               f"{icone} Sugestão para o próximo passo: eu posso consolidar estes dados\n"
               f"em um infográfico, se você desejar.\n\n"
               f"### ▶ EVIDÊNCIAS DOCUMENTAIS\n")
        out = mf.strip_nlm_suggestion_box(txt)
        check("Sugestão para o próximo passo" not in out, f"caixinha {icone} some")
        check("infográfico" not in out, f"continuação da caixinha {icone} some")
        check("### ▶ EVIDÊNCIAS DOCUMENTAIS" in out, f"seção após a caixinha {icone} sobrevive")
        check("0010094-14.2026.5.15.0079" in out, f"conteúdo antes da caixinha {icone} sobrevive")

    print("S1b — redação legada ('Sugestão de próximo passo')")
    out = mf.strip_nlm_suggestion_box("💡 Sugestão de próximo passo: gerar áudio\n\n- Vara: 2ª VT\n")
    check("Sugestão" not in out, "redação legada some")
    check("- Vara: 2ª VT" in out, "campo seguinte sobrevive")


def t_marcadores_do_perito_sobrevivem():
    print("S2 — ícones do formulário do perito NÃO podem ser descartados")
    casos = [
        ("★ DATA CRÍTICA — Último dia efetivamente trabalhado: 08/12/2025", "★ DATA CRÍTICA"),
        ("| ▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO — 26/01/2021 ▼▼▼ | | | |", "▼▼▼"),
        ("| Ficha de EPI — registro do fornecimento 🔄 | [X] | [ ] |", "🔄"),
        ("| Fiscalização do uso 👤 (perito) | [ ] | [ ] |", "👤"),
        ("▶ ORIGEM DA FICHA: [X] PDF digital nativo", "▶ ORIGEM"),
        ("### ▶ NR-6 — COMPROVAÇÃO (as 4 linhas 🔄; as 2 linhas 👤 são juízo do perito)", "NR-6"),
        ("- CNAE — Fabricação de açúcar · TRCT campo 08 · valor ≠ código", "≠"),
    ]
    for linha, agulha in casos:
        out = mf.strip_nlm_suggestion_box(linha + "\n")
        check(agulha in out, f"preserva {agulha!r}")


def t_caixinha_no_fim_do_arquivo():
    print("S3 — caixinha no fim do bundle (caso real: vazava pro bloco de Quesitos)")
    txt = ("#### Conclusão:\n"
           "* 8) Concluir por período quanto a insalubridade.\n"
           "---\n"
           "🧩 Sugestão para o próximo passo: posso consolidar estes dados estruturados.\n")
    out = mf.strip_nlm_suggestion_box(txt)
    check("Sugestão" not in out, "caixinha final some")
    check("8) Concluir por período" in out, "último quesito real sobrevive")


def main():
    print("=== regressão: caixinhas de conversa do NLM ===")
    t_caixinhas_removidas()
    t_marcadores_do_perito_sobrevivem()
    t_caixinha_no_fim_do_arquivo()
    print()
    if FALHAS:
        print(f"✗ {len(FALHAS)} falha(s)")
        return 1
    print("✓ tudo verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
