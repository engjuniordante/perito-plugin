#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_caepi_index.py — indexa a base oficial CAEPI (MTE) num SQLite compacto.

Entrada: o RelatorioCA_*.csv.gz baixado do site do MTE
         (https://caepi.mte.gov.br — exportação "Relatório CA"; ~168 MB, 124k CAs).
Saída:   caepi.sqlite — chave = nº do C.A.; por C.A.: validade, situação, equipamento
         e o AGENTE/ANEXO NR-15 DERIVADO (regras texto→anexo aplicadas aqui, uma vez).

Por que indexar: o guard de EPI (check_epi.py / build_laudo.py) faz lookup do C.A.
nesta base — fonte OFICIAL, ignora o nome comercial. O modelo nunca lê os 168 MB
(economia de token + à prova de erro). sqlite3 é stdlib → zero pip.

Atualização: re-baixe o csv.gz do MTE (trimestral basta) e rode de novo. O guard
avisa quando o índice passa de 90 dias.

uso: python3 build_caepi_index.py <RelatorioCA_*.csv.gz> <saida/caepi.sqlite>
"""
import csv
import io
import re
import sqlite3
import sys
import unicodedata
import zlib
from datetime import date


def deburr(s):
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c)).upper()


def to_iso(br):
    """DD/MM/AAAA -> AAAA-MM-DD (str) ou '' se inválido."""
    m = re.match(r'\s*(\d{2})/(\d{2})/(\d{4})', br or '')
    if not m:
        return ''
    d, mo, y = m.groups()
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return ''


# ---- derivação agente/anexo NR-15 a partir de equipamento + texto de proteção ----
# Conservador: quando não há agente NR-15 claro, devolve ('', '') — o guard então
# cai na regra absoluta (creme) ou flaga. NUNCA chuta agente que não está no texto.
def derive(equip, texto):
    e = deburr(equip)
    t = deburr(equip + ' ' + texto)

    has = lambda *ks: any(k in t for k in ks)
    quim = has('QUIMIC', 'ACIDO', 'ALCALI', 'BASICO', 'OLEO', 'GRAXA', 'SOLVENTE',
               'HIDROCARBONET', 'TOLUENO', 'XILENO', 'QUEROSENE', 'THINNER', 'GASOLINA')

    # 1) auditivo -> ruído (An.1)
    if 'AUDITIV' in e or 'AURICULAR' in e or 'ABAFADOR' in e:
        return 'Ruído (An.1)', '1'
    # 2) máscara/lente/viseira/facial de solda -> radiação não-ionizante (An.7)
    if ('SOLDA' in t) and any(k in e for k in ('MASCARA', 'LENTE', 'VISEIRA', 'FACIAL', 'ESCUDO')):
        return 'Radiação não-ionizante (An.7)', '7'
    # 3) creme/pomada
    if 'CREME' in e or 'POMADA' in e:
        if 'SOLAR' in t:
            return 'Proteção solar — não é EPI (NT 146/2015 §4)', ''
        return 'Químico dérmico (An.13)', '13'
    # 4) vibração
    if has('VIBRACAO', 'VIBRATOR', 'MAOS E BRACOS', 'CORPO INTEIRO'):
        return 'Vibração (An.8)', '8'
    # 5) frio (An.9) — neutralizável por vestimenta térmica.
    #    CALOR é DELIBERADAMENTE omitido: insalubridade de calor é por IBUTG, NÃO há
    #    EPI que a neutralize (luva/roupa térmica protege calor de contato, não a
    #    carga térmica ambiental). Derivar An.3 só geraria falso neutralizador.
    if has('FRIO', 'BAIXAS TEMPERATURAS', 'CAMARA FRIA', 'FRIGORIFIC'):
        return 'Frio (An.9)', '9'
    # 6) respiratório -> químico inalável (An.11) ou poeira (An.12)
    resp = any(k in e for k in ('RESPIRADOR', 'SEMIFACIAL', 'PFF', 'PURIFICADOR', 'PEÇA SEMIFACIAL', 'PECA SEMIFACIAL')) \
        or ('MASCARA' in e and not ('SOLDA' in t))
    if resp:
        if has('VAPOR', 'GAS', 'GASES', 'ORGANIC', 'AMONIA', 'CLORO') or quim:
            return 'Químico inalável (An.11)', '11'
        if has('POEIRA', 'PARTICULAD', 'AEROSSOL', 'AERODISPERSOID', 'NEVOA', 'FUMO'):
            return 'Poeira/particulado (An.12)', '12'
        return 'Poeira/particulado (An.12)', '12'
    # 7) contato dérmico químico: luva/vestimenta/avental/manga/bota + químico
    dermico = any(k in e for k in ('LUVA', 'VESTIMENTA', 'AVENTAL', 'MANGA', 'MANGOTE',
                                   'BOTA', 'CONJUNTO', 'MACACAO', 'JALECO'))
    if dermico and quim:
        return 'Químico dérmico (An.13)', '13'
    # 8) umidade: impermeável (sem químico)
    if has('UMIDADE', 'IMPERMEAV') and not quim:
        return 'Umidade (An.10)', '10'
    # 9) biológico
    if has('BIOLOGIC', 'MICRORGAN', 'MICROORGAN', 'VIRUS', 'BACTERI'):
        return 'Agente biológico (An.14)', '14'
    return '', ''


def main():
    if len(sys.argv) != 3:
        print('uso: python3 build_caepi_index.py <RelatorioCA_*.csv.gz> <saida/caepi.sqlite>')
        sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]

    best = {}  # ca -> (validade_iso, row_dict) — mantém a validade mais recente por C.A.
    # o export do MTE vem com lixo concatenado no fim do .gz: zlib decodifica o
    # primeiro membro e ignora o resto (o gzip do stdlib quebra; o gzcat ignora).
    if src.endswith('.gz'):
        with open(src, 'rb') as fh:
            data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(fh.read())
        f = io.TextIOWrapper(io.BytesIO(data), encoding='utf-8', errors='replace', newline='')
    else:
        f = open(src, 'rt', encoding='utf-8', errors='replace', newline='')
    with f:
        reader = csv.reader(f, delimiter=';', quotechar='"')
        header = next(reader, None)
        n_in = 0
        for row in reader:
            if len(row) < 13:
                continue
            ca = re.sub(r'\D', '', row[0])
            if not ca:
                continue
            n_in += 1
            validade_br = (row[1] or '').strip()
            situacao = (row[2] or '').strip()
            equip = (row[7] or '').strip()
            texto = ' '.join((row[i] or '') for i in (8, 10, 12, 13, 14) if i < len(row))
            vi = to_iso(validade_br)
            prev = best.get(ca)
            if prev is None or (vi and vi > prev[0]):
                agente, anexo = derive(equip, texto)
                best[ca] = (vi, {
                    'ca': ca, 'validade_iso': vi, 'validade_br': validade_br,
                    'situacao': situacao, 'equipamento': equip,
                    'agente': agente, 'anexo': anexo,
                })

    con = sqlite3.connect(out)
    con.execute('DROP TABLE IF EXISTS ca')
    con.execute('DROP TABLE IF EXISTS meta')
    con.execute('''CREATE TABLE ca (
        ca TEXT PRIMARY KEY, validade_iso TEXT, validade_br TEXT,
        situacao TEXT, equipamento TEXT, agente TEXT, anexo TEXT)''')
    con.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)')
    con.executemany('INSERT OR REPLACE INTO ca VALUES (:ca,:validade_iso,:validade_br,:situacao,:equipamento,:agente,:anexo)',
                    [r for _, r in best.values()])
    con.execute('INSERT INTO meta VALUES (?,?)', ('build_date', date.today().isoformat()))
    con.execute('INSERT INTO meta VALUES (?,?)', ('source', src.split('/')[-1]))
    con.execute('INSERT INTO meta VALUES (?,?)', ('n_cas', str(len(best))))
    con.commit()

    n_class = con.execute("SELECT COUNT(*) FROM ca WHERE anexo!=''").fetchone()[0]
    con.close()
    print('OK -> %s' % out)
    print('CAs lidos: %d | CAs únicos gravados: %d | com agente NR-15 derivado: %d (%.0f%%)'
          % (n_in, len(best), n_class, 100.0 * n_class / max(len(best), 1)))
    print('build_date: %s' % date.today().isoformat())


if __name__ == '__main__':
    main()
