# Perito — plugin de perícia trabalhista (Claude Code / Cowork)

Plugin que automatiza o pipeline de perícia de **insalubridade, periculosidade e ergonomia**
do Eng. Antonio Carlos Dante Junior.

O plugin contém **a lógica** (skills + scripts). Os **dados de cada perito** (base de
conhecimento, templates `.docx`, planilha de agendamento e identidade) ficam na **pasta do
projeto** que o perito conecta no Cowork, descritos em um `perito-config.json` na raiz dela.

> 📖 **É perito e quer só usar o plugin?** Veja o [**Manual de uso (passo a passo)**](MANUAL.md)
> — instalação, configuração e cada skill explicada em linguagem simples. Este README é a
> visão técnica (arquitetura e estrutura).

## Skills

| Comando | O que faz |
|---|---|
| `/configurar` | Cria/edita o `perito-config.json` (identidade + caminhos). Roda 1 vez. |
| Extrator | Consolida os 5 outputs do NotebookLM no formulário de campo. |
| Redator Insal/Peric | Monta o laudo NR-15/NR-16 (`.docx`) no template do perito. |
| Redator Ergonômico | Monta o laudo NR-17 a partir da planilha de avaliação. |
| Responde Impugnação | Formata a minuta de esclarecimentos no template. |
| Atualiza Base | Grava uma correção pontual na base de conhecimento. |
| Povoar Base | Povoa a base em lote a partir de laudos anteriores. |
| Alertas de Prazos | Lê a planilha de agendamento e monta o planejamento da semana (read-only). |

## Instalação

No Claude Code **ou** no Cowork:

```
/plugin marketplace add engjuniordante/perito-plugin
/plugin install perito@perito-jr
```

Depois, **uma vez**, conecte a pasta do projeto (que contém a base do perito e o
`perito-config.json`) e rode `/configurar` se o config ainda não existir.

Para receber atualizações: `/plugin update perito`.

## Arquitetura

- **Universal (este repo):** skills, scripts (`build_*.py`), formulário de campo, esqueleto
  de agentes. Os scripts **se auto-provisionam** (`pip install python-docx openpyxl` no
  início, idempotente) — o perito não instala nada à mão.
- **Por perito (pasta do projeto, fora deste repo):** `perito-config.json`, base de
  conhecimento (`08-Textos-Padrao/`, `04-EPIs/`, …), templates `.docx` marcados com
  `{{...}}`, planilha de agendamento. Schema do config em
  `plugins/perito/skills/_perito-config.md`.

## Onboarding de um perito novo

1. Instalar o plugin (comandos acima).
2. Levar a base de conhecimento dele + os templates `.docx` **marcados no padrão do plugin**
   (`{{VARA}}`, `{{ANALISE_*}}`, …) para a pasta do projeto.
3. Rodar `/configurar` (ou deixar o `perito-config.json` pré-preenchido).
