---
name: perito-responde-impugnacao-nlm
description: Use SÓ no Claude Code quando o perito disser "responder impugnação em lote", "responde impugnação do NotebookLM", "montar esclarecimentos automático", "rodar a impugnação da pasta", "gerar esclarecimentos sem colar", ou apontar uma PASTA com o laudo + a(s) petição(ões) de impugnação. Faz o MESMO que a 04-responde-impugnacao, mas cria um notebook EFÊMERO, sobe laudo + impugnação(ões), roda o prompt e monta o .docx sozinha — em vez de o perito colar a minuta do NLM. Cria um notebook efêmero e o APAGA no fim. Não funciona no Cowork (que não enxerga o MCP/CLI nlm).
---

# Responde Impugnação NLM — automático (exclusiva do Claude Code)

Esta skill faz **o que a `04-responde-impugnacao` faz**, com **uma diferença**: em vez de o perito colar a minuta do NotebookLM, ela **cria o notebook, sobe as fontes, roda o prompt de impugnação e monta o `.docx` sozinha**, via o CLI `nlm`, **sem gastar token de modelo**. É o irmão da `01b-extrator-nlm`, mas para impugnações.

> **Fonte única do conteúdo:** o texto dos esclarecimentos **é redigido pelo prompt no NotebookLM** (com o laudo + a impugnação como fontes). A skill/script **não avalia nem reescreve nada** — só transpõe a minuta pronta para o template `.docx`, exatamente como a `04-responde-impugnacao` (que "formata, não cria").

## Passo 0 — Pré-requisitos (Code + CLI nlm + config)

1. **Só Claude Code.** Se o CLI `nlm` / MCP `notebooklm` **não existir** nesta sessão (Cowork/app), **PARE** e diga: *"O modo automático só roda no Claude Code. No Cowork, use `/04-responde-impugnacao` e cole a minuta do NotebookLM manualmente."*
2. **`nlm` autenticado.** Auth expirado → instrua `nlm login` (conta Google do perito) e re-dispare. (A sessão do NLM é frágil — expira em dias.)
3. **`perito-config.json`** na **raiz do projeto** (schema em `_perito-config.md`). Identidade = `config.perito`; caminhos = `config.caminhos`.
4. **Prompt de impugnação:** vive no MESMO arquivo `config.notebooklm.prompts_extracao` (o heading que casa "Impugnação", que o extrator ignora). O script o extrai sozinho. Ausente → **pergunte** o caminho do arquivo de prompts.
5. **Pasta-mãe do lote:** `config.notebooklm.pasta_impugnacoes` (a pasta `Impugnações-notebooklm`). Ausente → **pergunte** e **ofereça salvar** no config.

## Como as fontes ficam na pasta

Cada **subpasta = 1 processo** (nome = nº do processo). Dentro, as fontes que o NLM vai ler:
- **o LAUDO pericial** (PDF) — a base técnica das respostas;
- **a(s) PETIÇÃO(ÕES) de impugnação/esclarecimentos** (PDF) — pode ser **de uma parte só ou das duas**.

O script sobe **todos** os PDFs/arquivos de fonte da pasta (aceita `.pdf`, `.docx`, `.txt`, `.md`), **ignorando** os arquivos de saída (`esclarecimento…`, `formulario…`). **≥ 1 fonte já roda**; zero fontes → pula.

## Passo 1 — Rodar o script `responde_impugnacao.py` (pasta → docx, tudo mecânico)

> Um script faz **toda a parte mecânica**: cria o notebook `EFÊMERO IMPUG — <nº>`, sobe as fontes esperando indexar, roda **1 query** (o prompt de impugnação, verbatim), limpa citações `[n]`, parseia a minuta em campos + corpo, **corta o fecho duplicado** (que já é fixo no template), compõe a frase de abertura (1 OU 2 partes), monta o JSON, chama o `build_impugnacao.py` → `esclarecimentos-<nº>.docx` e **apaga o notebook**. No terminal, **sem token**.

No Windows/Code use **`python`** (não `python3`). O script auto-descobre o `perito-config.json` (subindo do caminho), acha o `nlm` sozinho e usa o **template BUNDLED** do plugin (o contrato do `.docx` é acoplado a esta versão do script — não usa a cópia do Drive).

- **LOTE (o padrão)** — cada subpasta de `config.notebooklm.pasta_impugnacoes`, em fila; a cada sucesso **move a subpasta para `Processados/`**:
  ```
  python <plugin>/skills/04b-responde-impugnacao-nlm/responde_impugnacao.py --lote "<config.notebooklm.pasta_impugnacoes>"
  ```
- **UMA pasta** — quando o perito aponta uma específica:
  ```
  python <plugin>/skills/04b-responde-impugnacao-nlm/responde_impugnacao.py "<pasta>"
  ```

1. **Ler o stdout.** O script imprime `✓ indexado`, `✓ minuta`, `📦 docx`, os `🚩` de campos não localizados, e uma linha `DOCX: <caminho>` por processo. No lote, fecha com **RESUMO** (✅/⏭️/❌).
2. **Tratar as saídas** (a fila continua mesmo se uma pasta falhar):
   - `⏭️ PULADO — nenhuma fonte` → subpasta sem PDF de fonte; segue.
   - `auth`/`nlm login` → credenciais expiraram: rode `nlm login` e re-dispare.
   - `❌ FALHOU` (query vazia / `INVALID_ARGUMENT` / build recusou) → o script **mantém aquele notebook de pé** (título `EFÊMERO IMPUG — …`, id no resumo) e **não move** a subpasta, para inspeção/re-run.
3. **Sucesso** → o notebook **já foi apagado** e a subpasta **movida** pelo script. **Entregue o(s) `.docx`** ao perito (salva em `Laudos-Gerados/`). O script grava um `esclarecimentos-<nº>.json` ao lado do `.docx` (o JSON que alimentou o build) — útil para depurar; não precisa abrir.

## Passo 2 — Relatório ao perito

Para cada processo, reproduza:
```
## 📝 IMPUGNAÇÃO AUTOMÁTICA (NotebookLM → esclarecimentos.docx)
Processo: <nº>
Fontes: <n> (laudo + impugnação[ões]) · indexadas [✓/⚠]
Parte(s) impugnante(s): [Reclamante | Reclamada | ambas]
Docx: esclarecimentos-<nº>.docx
Notebook efêmero: [APAGADO ✓ | MANTIDO — <motivo>]
Campos não localizados (🚩): [lista, ou "nenhum"]
```
**Sempre destaque os `🚩`** (ex.: `ID_IMPUGNACAO`/cidade não localizados, parte não identificada) — são os campos que o perito confere antes de assinar. O script **não deixa marcador `{{…}}` no documento** (o build recusa o `.docx` se sobrar).

## Contrato do prompt de impugnação (o que o NLM deve devolver)

O parser é determinístico e espera, **no topo** da minuta, as linhas de cabeçalho (com ou sem `- ` na frente):
```
- CIDADE_VARA: <cidade da Vara>
- NUMERO_PROCESSO: <nº completo>
- NOME_RECLAMANTE: <nome em MAIÚSCULAS>
- NOME_RECLAMADA: <nome em MAIÚSCULAS>
- IMPUGNANTES: Reclamada (Id. xyz)        ← 1 parte
      (ou, com as duas)  Reclamante (Id. abc); Reclamada (Id. xyz)
```
E, no corpo, um bloco por parte impugnante:
```
ESCLARECIMENTOS SOLICITADOS PELA <RECLAMANTE | RECLAMADA>
[fundamentação, se houver]
1- <pergunta>
Resposta: <resposta baseada no laudo>
...
```
O fecho ("Pelo exposto…" + "…ratifico a conclusão do laudo pericial.") **já é fixo no template** — o script o **corta** da minuta se vier. `IMPUGNANTES` ausente → o script deriva as partes dos títulos `…PELA X` (Id. fica `____` e vira 🚩).

## Fallback (script indisponível) — MCP passo a passo

Se o CLI `nlm` não puder rodar, faça pela MCP, na mão (uma pasta por vez): `notebook_create(title="EFÊMERO IMPUG — <pasta>")` → para cada fonte `source_add(source_type="file", file_path="<Windows>", wait=True)` → `notebook_query(notebook_id, query=<prompt de impugnação verbatim>)` → cole a minuta na **`04-responde-impugnacao`** (que faz o parse + build) → `notebook_delete(notebook_id, confirm=True)`.

## Regras de ouro

1. **Só Code + `nlm` autenticado.** Cowork → mandar usar `/04-responde-impugnacao` manual.
2. **Conteúdo intocado.** A skill/script **não avalia nem reescreve** — o mérito técnico é do prompt no NLM. A única limpeza é tirar `[n]`/`**` e cortar o fecho duplicado.
3. **1 ou 2 partes num só documento.** O corpo aceita os dois blocos `ESCLARECIMENTOS SOLICITADOS PELA X`; a frase de abertura sai no singular ou plural conforme o nº de partes.
4. **Efêmero apaga sozinho no sucesso.** Falha → mantém o `EFÊMERO IMPUG — …` de pé para inspeção.
5. **Template BUNDLED.** O script usa o template do plugin (não o do Drive), porque o marcador `{{INTRO_IMPUGNANTE}}` é desta versão.
