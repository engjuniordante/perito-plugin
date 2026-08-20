#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_contrato_prompts.py — o contrato entre os PROMPTS e o PARSER.

O buraco que isto fecha: até a v1.1.2 os prompts moravam SÓ no Drive do perito, fora do git.
O parser tem dezenas de testes; o arquivo que diz ao modelo o que produzir não tinha nenhum.
Tirar um marcador ▶ de lá não acendia nada — e o sintoma não é erro, é FORMULÁRIO VAZIO.

A régua deste arquivo: as seções exigidas NÃO são uma lista escrita à mão aqui. Elas são
LIDAS do próprio `montar_formulario.py` (as chamadas `get_by_prefix(sec, "…")`), então quem
acrescentar uma seção ao parser sem pedi-la no prompt quebra este teste — que é justamente o
tipo de divergência que ninguém percebe olhando um arquivo de cada vez.

Duas fontes, dois pesos:
  • BUNDLED (versionada no plugin) — o contrato TEM de valer, sempre.
  • VIVA (Drive do perito, quando alcançável) — o contrato TAMBÉM tem de valer. Editar a
    cópia viva é direito do perito; quebrar o contrato nela não é.
Divergência de conteúdo entre as duas é INFORMATIVA, nunca falha: a viva é a do perito e
costuma estar à frente. Suite que fica vermelha por motivo legítimo é suite que se ignora.
"""
import io
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EXTRATOR = AQUI.parent / '01-extrator'
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(EXTRATOR))

import extrai_processo as ep  # noqa: E402
from montar_formulario import split_subsections  # noqa: E402

falhas = []
avisos = []


def check(cond, msg):
    if not cond:
        falhas.append(msg)


# ── as seções que o PARSER consome, lidas do parser (não digitadas aqui) ──────────────
FONTE_PARSER = (EXTRATOR / 'montar_formulario.py').read_text(encoding='utf-8')
PREFIXOS = sorted(set(re.findall(r'get_by_prefix\(\s*sec\s*,\s*["\'](.+?)["\']', FONTE_PARSER)))
check(len(PREFIXOS) >= 12,
      'só %d prefixos lidos do montar_formulario.py — a extração da lista quebrou, e um '
      'contrato que não lê nada passa vazio' % len(PREFIXOS))

# Marcadores que NÃO são seção, mas de que um guard depende diretamente.
# Cada um destes já zerou alguma coisa quando faltou (ver a memória do extrator).
MARCADORES = [
    ('ORIGEM DA FICHA', 'corta_bloco_ficha() recorta o bloco da ficha a partir dele'),
    ('▼', 'o guard de EPI usa a divisória para achar o início do imprescrito na tabela'),
    ('🔄', 'linha da tabela NR-6 (registro do fornecimento)'),
    ('👤', 'linha da tabela NR-6 (treinamento/recibo do trabalhador)'),
    ('★', 'marca DATA CRÍTICA'),
]


def confere_contrato(texto, origem):
    """O contrato inteiro contra UM arquivo de prompts."""
    sec = split_subsections(texto)
    check(len(sec) >= 10,
          '%s: split_subsections achou só %d seções — os marcadores ▶ não estão no início '
          'absoluto da linha (heading, bullet ou recuo antes deles zera o formulário inteiro).'
          % (origem, len(sec)))
    for pref in PREFIXOS:
        # A regra é a MESMA do get_by_prefix (chave em minúsculas, startswith), mas olhando a
        # CHAVE e não o valor: no arquivo de prompts as seções são o MOLDE da resposta, e três
        # ▶ adjacentes ("QUESITOS DO JUÍZO/DO RECLAMANTE/DA RECLAMADA") deixam as duas
        # primeiras com conteúdo vazio — o que é correto ali, e não é seção faltando.
        check(any(k.lower().startswith(pref.lower()) for k in sec),
              '%s: o parser lê a seção "%s", mas o prompt não pede nada com esse nome — '
              'o campo sairia vazio, sem erro.' % (origem, pref))
    for marca, porque in MARCADORES:
        check(marca in texto, '%s: marcador %s ausente — %s.' % (origem, marca, porque))


# ── 1. a cópia BUNDLED existe, é lida e cumpre o contrato ─────────────────────────────
check(ep.PROMPTS_BUNDLED.exists(),
      'cópia bundled dos prompts ausente (%s) — sem ela o contrato volta a não ter teste '
      'e a skill 01b depende do Drive estar alcançável' % ep.PROMPTS_BUNDLED)

if ep.PROMPTS_BUNDLED.exists():
    texto_bundled = ep.PROMPTS_BUNDLED.read_text(encoding='utf-8')
    confere_contrato(texto_bundled, 'BUNDLED')

    # As 6 partes que o extrai_processo dispara têm de sair do arquivo, em bloco de código.
    blocos, faltando = ep.ler_prompts(str(ep.PROMPTS_BUNDLED))
    check(faltando == [], 'BUNDLED: partes ausentes no arquivo de prompts: %r' % faltando)
    for k, _ in ep.PARTES:
        check(len((blocos.get(k) or '').strip()) > 80,
              'BUNDLED: a parte %s saiu vazia ou curta demais (%d chars) — bloco de código '
              'malformado no arquivo de prompts' % (k, len((blocos.get(k) or '').strip())))

# ── 2. precedência: o arquivo VIVO vence; a bundled é a rede ──────────────────────────
check(ep.resolver_prompts(None) == str(ep.PROMPTS_BUNDLED),
      'sem caminho configurado, resolver_prompts deveria cair na cópia bundled')
check(ep.resolver_prompts(r'X:\nao\existe\prompts.md') == str(ep.PROMPTS_BUNDLED),
      'caminho inalcançável deveria cair na cópia bundled, não abortar')
check(ep.resolver_prompts(str(AQUI / 'test_contrato_prompts.py')) == str(AQUI / 'test_contrato_prompts.py'),
      'arquivo existente deveria VENCER a cópia bundled')

# ── 3. a cópia VIVA, quando alcançável, cumpre o MESMO contrato ───────────────────────
# É aqui que o teste ganha o dia a dia: o perito edita a cópia do Drive, e uma edição que
# derrube um marcador ▶ tem de acender agora, não no formulário vazio de um processo real.
VIVA = Path(r'G:\Meu Drive\Base Perícia Irineu\prompts-extracao-notebooklm.md')
if VIVA.exists():
    texto_vivo = VIVA.read_text(encoding='utf-8')
    confere_contrato(texto_vivo, 'VIVA (Drive)')
    if ep.PROMPTS_BUNDLED.exists() and texto_vivo != texto_bundled:
        avisos.append('a cópia VIVA do Drive difere da BUNDLED do plugin — as duas cumprem o '
                      'contrato, mas o plugin está publicando uma versão diferente da que o '
                      'perito usa. Re-bundle quando a viva estabilizar.')
else:
    avisos.append('cópia VIVA do Drive não alcançável — contrato conferido só na BUNDLED.')

for a in avisos:
    print('⚠ %s' % a)
if falhas:
    print('FALHOU:')
    for f in falhas:
        print('  ✗', f)
    sys.exit(1)
print('✓ tudo verde — contrato prompts↔parser conferido em %d seções + %d marcadores'
      % (len(PREFIXOS), len(MARCADORES)))
