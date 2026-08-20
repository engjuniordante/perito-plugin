#!/usr/bin/env python3
"""Regressão da INTEGRIDADE DE LEITURA da ficha de EPI (check_epi.py).

Assinatura comum dos defeitos cobertos aqui: o extrator afirmava em vez de duvidar.
C.A. errado virava classificação, C.A. ilegível virava silêncio. Nenhum quebrava nada —
todos produziam um quadro de EPI completo e confiante.

  T4  o C.A. tem de sair da COLUNA, não da linha inteira ("CALCA 44" elegia 44)
  T5  C.A. ilegível pode ser descartado, mas nunca em silêncio
  T9  C.A. válido que pertence a OUTRO equipamento tem de virar aviso
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_epi as ce

FALHAS = []


def check(cond, msg):
    print(("  ✓ " if cond else "  ✗ FALHOU: ") + msg)
    if not cond:
        FALHAS.append(msg)


def t4_ca_da_coluna():
    print("T4 — C.A. lido da coluna, não da descrição")
    # Tamanho ao lado do nome é rotina em ficha de EPI; a cedilha salvava "CALÇA", mas OCR e
    # manuscrito perdem cedilha o tempo todo. "MOGI-CALCA 42" é linha de ficha real.
    for desc in ("CALCA 44", "TOUCA 2", "MOGI-CALCA 42", "CALÇA 44", "BOTA 42",
                 "JAQUETA 3", "MASCARA 3", "CALCADO 42"):
        linha = "• 09/03/2022 · 1un · %s · CA 20573" % desc
        check(ce.extract_ca(linha) == "20573", "%-16s → C.A. 20573" % desc)
    print("T4b — C.A. legítimo continua sendo lido")
    check(ce.extract_ca("• 09/03/2022 · 1un · LUVA · C.A. 5745") == "5745", "rótulo 'C.A.' com pontos")
    check(ce.extract_ca("• 09/03/2022 · 1un · LUVA · CA 11.512") == "11512", "C.A. com ponto de milhar")


def t5_ilegivel_avisa():
    print("T5 — C.A. ilegível avisa em vez de sumir")
    linhas = ["• 09/03/2022 · 1un · LUVA NITRILICA · CA 5745",
              "• 10/03/2022 · 1un · LUVA VAQUETA · CA [3?41]",
              "• 11/03/2022 · 1un · PROTETOR AURICULAR · CA 1234/2025",
              "• 12/03/2022 · 1un · COLETE REFLETIVO · CA Não se Aplica"]
    _cl, fl, _nc = ce.process(linhas, {}, ce.Caepi(None))
    msgs = " ".join(m for _d, m in fl)
    check("[3?41]" in msgs, "leitura duvidosa '[3?41]' vira aviso")
    check("1234/2025" in msgs, "validade colada '1234/2025' vira aviso")
    check("COLETE" not in " ".join(d for d, _m in fl),
          "'CA Não se Aplica' é ausência declarada, NÃO vira aviso")


def t9_outro_equipamento():
    print("T9 — C.A. válido, porém de outro equipamento")
    # Os dois casos reais medidos em processo: o do avental foi ao laudo assinado.
    check(ce.divergencia_equipamento("LUVA NITRILICA", "PROTETOR AUDITIVO"),
          "luva × protetor auditivo → aviso")
    check(ce.divergencia_equipamento("AVENTAL", "CALÇADO TIPO BOTA"),
          "avental × calçado → aviso (a régua NÃO pode deixar 'calçado' casar 'calça')")

    print("T9b — sinonímia legítima NÃO vira aviso (falso positivo é o inimigo)")
    for desc, eq in (("PROTETOR AUDITIVO SILICONE PLUGUE", "PROTETOR AUDITIVO"),
                     ("LUVA VAQUETA TAM G", "LUVA PARA PROTEÇÃO CONTRA AGENTES MECÂNICOS"),
                     ("BOTINA VAQ PR COMPOSITE", "BOTINA - TIPO B"),
                     ("MANGOTE", "VESTIMENTA TIPO AVENTAL"),
                     ("CALCA TIPO PIJAMA IMPERM NYLON", "VESTIMENTA TIPO AVENTAL"),
                     ("BLUSAO CAPUZ LAV VEICULOS", "VESTIMENTA TIPO AVENTAL"),
                     ("CREME PROT PELE G3", "CREME PROTETOR DE SEGURANÇA")):
        check(not ce.divergencia_equipamento(desc, eq), "%-34s × %s" % (desc[:34], eq[:30]))

    print("T9c — régua que não reconhece um dos lados fica calada")
    check(not ce.divergencia_equipamento("ITEM SEM FAMÍLIA CONHECIDA", "LUVA"),
          "descrição irreconhecível → sem aviso")
    check(not ce.divergencia_equipamento("LUVA", "EQUIPAMENTO GENÉRICO XPTO"),
          "equipamento irreconhecível → sem aviso")


def main():
    print("=== integridade de leitura da ficha de EPI ===")
    t4_ca_da_coluna()
    t5_ilegivel_avisa()
    t9_outro_equipamento()
    print()
    if FALHAS:
        print(f"✗ {len(FALHAS)} falha(s)")
        return 1
    print("✓ tudo verde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
