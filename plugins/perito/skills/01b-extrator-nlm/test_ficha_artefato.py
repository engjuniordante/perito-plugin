#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ficha_artefato.py — a ficha pela via do ARTEFATO (data-table), T7.1.

Roda offline: nenhum destes testes fala com o `nlm`. O que eles travam é a conversão
CSV → bloco da Parte 3a, que é onde uma ficha grande se perde em silêncio.

As linhas do bloco "ficha real" saíram do artefato de verdade, medido em 20/08/2026 contra
o 3-ficha-epi.pdf do 0011183-33 (395 entregas, 20 fls. manuscritas) — inclusive a coluna
`Source` que a ferramenta acrescenta por conta própria e a quantidade `1.720`.

    python test_ficha_artefato.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extrai_processo import (          # noqa: E402
    casar_colunas, normaliza_data, normaliza_qtd, csv_para_p3a,
)

falhas = []


def ok(cond, label):
    print(("  ✓ " if cond else "  ✗ ") + label)
    if not cond:
        falhas.append(label)


# ── A. a coluna é casada por palavra-chave, nunca por posição ────────────────
print("A — casar_colunas sobrevive ao cabeçalho que o modelo inventar")

# o layout que o artefato devolveu de fato, com a coluna Source de brinde
real = ["DATA_ENTREGA", "QUANTIDADE", "EQUIPAMENTO", "CA", "Source"]
c = casar_colunas(real)
ok(c == {"data": "DATA_ENTREGA", "qtd": "QUANTIDADE", "desc": "EQUIPAMENTO", "ca": "CA"},
   "layout real (com a coluna 'Source' extra que a ferramenta acrescenta)")

# os outros dois layouts que a auditoria registrou em outros empregadores
c2 = casar_colunas(["Data de Entrega", "Qtd.", "Descrição do EPI", "C.A."])
ok(c2["data"] == "Data de Entrega" and c2["qtd"] == "Qtd." and c2["ca"] == "C.A.",
   "layout 'Data de Entrega | Qtd. | Descrição do EPI | C.A.'")

c3 = casar_colunas(["Dia", "Unidades", "Material entregue", "Certificado de Aprovação"])
ok(c3 == {"data": "Dia", "qtd": "Unidades", "desc": "Material entregue",
          "ca": "Certificado de Aprovação"},
   "layout com outros nomes ('Material entregue', 'Certificado de Aprovação')")

# a ordem das colunas trocada não pode mudar nada — é o ponto do casamento por chave
c4 = casar_colunas(["CA", "EQUIPAMENTO", "QUANTIDADE", "DATA_ENTREGA"])
ok(c4["data"] == "DATA_ENTREGA" and c4["ca"] == "CA",
   "colunas na ordem INVERTIDA → mesmo casamento (posição não importa)")

ok("data" not in casar_colunas(["Coluna A", "Coluna B"]),
   "cabeçalho irreconhecível → não inventa coluna de data")

# ── B. a data ────────────────────────────────────────────────────────────────
print("\nB — normaliza_data")

ok(normaliza_data("12/09/2024") == "12/09/2024", "dd/mm/aaaa passa")
ok(normaliza_data("1/7/2020") == "01/07/2020", "d/m/aaaa → zero à esquerda")
ok(normaliza_data("01/07/20") == "01/07/2020", "ano de 2 dígitos → 2020")
ok(normaliza_data("2020-07-01") == "01/07/2020", "ISO → dd/mm/aaaa")
# a armadilha do T11, que num caso real dobrou 11 linhas em 22 entregas
ok(normaliza_data("19/4/21 á 24/4/21") == "19/04/2021",
   "célula com PERÍODO (entrega→troca) → UMA entrega, a data INICIAL")
ok(normaliza_data("") == "" and normaliza_data("ilegível") == "",
   "sem data legível → vazio (a linha vira aviso, não some)")

# ── C. a quantidade ──────────────────────────────────────────────────────────
print("\nC — normaliza_qtd: o '1,000' que multiplica a cobertura por mil")

ok(normaliza_qtd("01") == ("01", None), "'01' passa limpo, sem aviso")
ok(normaliza_qtd("3") == ("3", None), "'3' passa limpo")

# esta é a linha 391 do CSV real: Bota PVC, quantidade 1.720
q, av = normaliza_qtd("1.720")
ok(q == "1" and av and "não milhar" in av,
   "'1.720' (3 casas decimais) → 1 unidade + aviso, NÃO 1720")
q, av = normaliza_qtd("1,000")
ok(q == "1" and av, "'1,000' → 1 unidade + aviso")

q, av = normaliza_qtd("?")
ok(q == "1" and av and "piso" in av,
   "quantidade ilegível → 1 (piso: a entrega existe) + aviso, e a linha NÃO se perde")
q, av = normaliza_qtd("")
ok(q == "1" and av, "quantidade vazia → 1 + aviso")

# ── D. CSV → bloco da Parte 3a ───────────────────────────────────────────────
print("\nD — csv_para_p3a: o bloco que o montador vai ler")

csv_real = (
    "DATA_ENTREGA,QUANTIDADE,EQUIPAMENTO,CA,Source\n"
    "12/09/2024,01,LUVA NEOPRENE (G),33333,[1]\n"
    "01/07/2020,1.720,Bota PVC,35223,[1]\n"
    "31/08/2024,01,CREME DE PROTEÇÃO,43802,[1]\n"
    "15/03/2019,02,Protetor auricular,NAO INFORMADO,[1]\n"
)
bloco, n, avisos = csv_para_p3a(csv_real, impr="03/07/2020")

ok(n == 4, "as 4 entregas entram")
ok(bloco.startswith("▶ ORIGEM DA FICHA:"),
   "bloco começa em 'ORIGEM DA FICHA' (é a âncora do corta_bloco_ficha)")
ok("| Data de Entrega | Quantidade | Descrição do EPI | C.A. |" in bloco,
   "cabeçalho da tabela no formato que o prompt exige")

linhas = [l for l in bloco.splitlines() if l.startswith("| ") and "/" in l[:14]]
ok(linhas[0].startswith("| 15/03/2019"), "ordenado por data: 2019 primeiro…")
ok(linhas[-1].startswith("| 12/09/2024"), "…e 2024 por último")

ok("| ▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO — 03/07/2020 ▼▼▼ | | | |" in bloco,
   "divisória do imprescrito com a data da Parte 1")
corpo = bloco.splitlines()
i_div = next(i for i, l in enumerate(corpo) if "▼▼▼" in l)
i_2019 = next(i for i, l in enumerate(corpo) if l.startswith("| 15/03/2019"))
i_2024 = next(i for i, l in enumerate(corpo) if l.startswith("| 12/09/2024"))
ok(i_2019 < i_div < i_2024, "divisória cai ENTRE o histórico e o período relevante")

ok("| 01/07/2020 | 1 | Bota PVC | 35223 |" in bloco,
   "a Bota PVC entra com quantidade 1, não 1720")
ok("C.A. não informado" in bloco, "'NAO INFORMADO' vira o literal que o montador espera")
ok(any("1.720" in a for a in avisos), "o 1.720 sai nomeado nos avisos")
ok("▶ CONFERÊNCIA OBRIGATÓRIA NA FICHA ORIGINAL:" in bloco
   and "1.720" in bloco.split("CONFERÊNCIA OBRIGATÓRIA")[1],
   "…e o aviso chega ao bloco de conferência, que é onde o perito olha")
ok("▶ EVIDÊNCIA DE ASSINATURA:" in bloco, "linha de evidência de assinatura presente")

# nenhuma linha pode sumir calada — é o defeito que a auditoria persegue
csv_torto = (
    "DATA_ENTREGA,QUANTIDADE,EQUIPAMENTO,CA\n"
    "12/09/2024,01,LUVA,33333\n"
    "ilegível,01,BOTINA,20573\n"
)
bloco2, n2, avisos2 = csv_para_p3a(csv_torto, impr="01/01/2020")
ok(n2 == 1, "linha com data ilegível não vira entrega…")
ok(any("BOTINA" in a for a in avisos2),
   "…mas sai NOMEADA no aviso (com o item), em vez de sumir em silêncio")
ok("BOTINA" in bloco2.split("CONFERÊNCIA OBRIGATÓRIA")[1],
   "…e aparece na conferência obrigatória")

# sem coluna de data não há tabela possível — tem de estourar, não devolver vazio
try:
    csv_para_p3a("Coluna A,Coluna B\n1,2\n")
    ok(False, "CSV sem coluna de data deveria levantar erro")
except ValueError as e:
    ok("DATA" in str(e).upper(), "CSV sem coluna de data → erro claro (e o chamador cai p/ chat)")

# divisória quando o imprescrito começa depois de tudo
b3, n3, _ = csv_para_p3a("DATA_ENTREGA,QUANTIDADE,EQUIPAMENTO,CA\n01/01/2015,1,LUVA,111\n",
                         impr="01/01/2020")
ok("▼▼▼" in b3 and n3 == 1,
   "ficha 100% anterior ao imprescrito → divisória ainda é emitida (no fim)")

# ── resultado ────────────────────────────────────────────────────────────────
print()
if falhas:
    print(f"FALHOU ({len(falhas)}):")
    for f in falhas:
        print("  - " + f)
    sys.exit(1)
print("✓ tudo verde — ficha via artefato do Studio (T7.1)")
