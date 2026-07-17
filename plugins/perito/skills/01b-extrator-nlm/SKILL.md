---
name: perito-extrator-nlm
description: Use SÓ no Claude Code quando o perito disser "extrair do NotebookLM", "buscar do NLM", "extração automática", "montar formulário sem colar", "rodar o extrator no notebook do processo", ou informar o notebook/nº do processo para o plugin buscar sozinho. Faz o MESMO que a 01-extrator, mas em vez de o perito colar os 5 outputs, busca as Partes 1, 2, 3a, 3b e 4 direto do NotebookLM via MCP (notebook_query) e entrega ao pipeline da 01-extrator. Não funciona no Cowork (que não enxerga o MCP).
---

# Perito Extrator NLM — extração automática do NotebookLM (exclusiva do Claude Code)

Esta skill faz **exatamente o que a `01-extrator` faz**, com **uma única diferença**: em vez de o perito colar manualmente os 5 outputs do NotebookLM, ela os **busca sozinha** via MCP `notebooklm-mcp` e monta o mesmo `_bundle`. Daí em diante, **o pipeline é o da `01-extrator`, intocado** (`montar_formulario.py` + Fase 2).

> **Fonte única das regras:** esta skill **NÃO** redefine as regras de extração. Tudo que é TIPO de laudo, agentes, EPI, quesitos, roteamento de anexo, formato Notas-do-iPhone, `[NÃO LOCALIZADO]`, AUTO-CHECK, etc. vive na `01-extrator/SKILL.md`. Aqui só trocamos a **entrada** (paste → MCP). Se algo divergir, vale a `01-extrator`.

## Passo 0 — Pré-requisitos (Code + MCP + config)

1. **Só Claude Code.** Se as ferramentas `mcp__notebooklm-mcp__*` **não existirem** nesta sessão (é o caso do Cowork/app), **PARE** e diga: *"Extração automática só roda no Claude Code. No Cowork, use `/01-extrator` e cole os 5 outputs do NotebookLM manualmente."*
2. **MCP autenticado.** Chame `mcp__notebooklm-mcp__server_info` e olhe `auth_status`:
   - `configured` → segue.
   - `stale` / `not_configured` → **PARE** e instrua: *"O NotebookLM precisa de login nesta máquina. Rode no terminal: `nlm login` (na conta Google do perito) e tente de novo."* (No PC do Irineu, é o `nlm login` da conta dele — feito uma vez.)
   - `unverified` → tente seguir (as credenciais em cache podem funcionar); se a 1ª query falhar por auth, aí sim mande rodar `nlm login`.
3. **`perito-config.json`** na **raiz do projeto** — mesmo padrão das outras skills (schema em `_perito-config.md`). Identidade = `config.perito`; caminhos = `config.caminhos`.
4. **Caminho dos prompts** = `config.notebooklm.prompts_extracao` (**caminho ABSOLUTO** — no Code é disco real, não sandbox). Ausente no config → **pergunte** ao perito o caminho do arquivo de prompts (ex.: `G:\Meu Drive\Base Perícia Irineu\prompts-extracao-notebooklm.md`) e **ofereça salvar** no config (bloco `notebooklm.prompts_extracao`) para não perguntar de novo.

## Passo 1 — Identificar o notebook do processo

1. O perito informa **nº do processo**, **reclamante** ou **nome do notebook**.
2. `mcp__notebooklm-mcp__notebook_list` → casar pelo que ele deu.
3. **1 candidato claro** → **confirme com o perito** (mostre `nome` + `id`) **antes** de consultar.
4. **Vários / nenhum** → liste os candidatos e pergunte qual é.
5. ⛔ **NUNCA** rodar query sem o notebook **confirmado** — a consulta custa e precisa mirar o alvo certo. A divisão do PDF em 4 partes e o **upload das fontes no notebook continuam manuais** (julgamento de fronteira de documento); esta skill **assume que o notebook já tem as fontes**.

## Passo 2 — Ler os 5 prompts (verbatim, do arquivo)

1. `Read` no arquivo `config.notebooklm.prompts_extracao`.
2. Localize as **5 seções** pelos cabeçalhos `━━━ PARTE 1 ━━━` … `━━━ PARTE 4 ━━━` — o prompt de cada parte é o **bloco de código (``` … ```)** logo abaixo do cabeçalho. Localize também o bloco **`REGRAS GERAIS (valem para todos os prompts)`** no topo. (No fim do arquivo pode haver um prompt de Impugnação — **ignore-o aqui**, é da Skill 4.)
3. Faltou alguma das 5 → avise qual e siga com as que houver (a parte ausente vira `[NÃO LOCALIZADO]` lá na frente).
4. ⛔ Use os prompts **VERBATIM** do arquivo — **não reescreva, não "melhore", não resuma**. São o padrão calibrado do perito.

## Passo 3 — Rodar as 5 queries e montar o bundle

1. **1ª query (Parte 1):** `mcp__notebooklm-mcp__notebook_query(notebook_id=<confirmado>, query=<REGRAS GERAIS + prompt da Parte 1>)`. Prepende o bloco **REGRAS GERAIS** ao prompt da Parte 1. Guarde o `conversation_id` retornado.
2. **Partes 2, 3a, 3b, 4:** rode **em sequência**, **encadeadas no MESMO `conversation_id`** da Parte 1 (elas se cruzam — a 3a usa o imprescrito calculado na 1, a 3b referencia a 3a; o thread preserva esse contexto, como no chat manual do NLM). Não precisa repetir REGRAS GERAIS nas seguintes.
   - **Notebook grande / risco de timeout** → use `notebook_query_start` + poll em `notebook_query_status` até `completed` (a ficha de EPI, Parte 3a, costuma ser o maior output).
3. **Limpe cada retorno antes de gravar** (o `answer` do MCP vem em markdown cru, com o que o perito NÃO colaria da UI web do NLM): **remova os marcadores de citação** inline `[1]`, `[1, 2]`, `[2-5]` (senão eles vazam para dentro dos valores do formulário, ex.: `Autuação: 24/08/2025 [4]`). O negrito `**…**` **pode ficar** — o parser da v1.0.75 tolera —, mas tirar deixa o bundle idêntico a um paste manual; fica a seu critério. Regex prático: apagar `\[[\d,\s\-–]+\]` (e, se quiser, `\*\*`). **Preserve** `[X]`, `[ ]`, `[NÃO LOCALIZADO]`, `[Presente — …]`. Não mexa em mais nada — subseções `▶`, tabelas de EPI e checkboxes intactos.
4. Grave os 5 retornos normalizados, **na ordem** 1, 2, 3a, 3b, 4, concatenados no bundle: `<config.caminhos.formularios_campo>/_bundle-<nº do processo>.md` — igual ao que ficaria se o perito colasse os 5 outputs em sequência. **Não** invente marcadores/cabeçalhos extras.
5. ⚠ Parte que **falhou / voltou vazia / "não encontrei nas fontes"** → registre-a como veio (o `montar_formulario.py` trata ausência como `[NÃO LOCALIZADO]`) e **avise o perito qual parte falhou** — costuma ser **fonte faltando no notebook** (ex.: a ficha de EPI não subiu) e ele decide se sobe e re-roda.

## Passo 4 — Entregar ao pipeline da `01-extrator` (INTOCADO)

A partir do `_bundle`, siga a **`01-extrator/SKILL.md` letra por letra** (é a skill irmã, `skills/01-extrator/`, no mesmo plugin):

- **Fase 1 (script):**
  - No Windows/Code use **`python`** (ou `py -3`), **não `python3`** — é a convenção do plugin (ver `_perito-config.md` › "Execução dos scripts"). Os scripts já reconfiguram o stdout para UTF-8 (v1.0.75), então **não** é preciso `PYTHONUTF8`.
  - Comando: `python <plugin>/skills/01-extrator/montar_formulario.py <_bundle-<nº>.md> -o <formularios_campo>/Formulario-Campo-<Reclamante>-<nº>.md --base <config.caminhos.base_conhecimento>`
  - Reproduza na resposta o resultado **🔧 / 🚩 / 📇 / 📐** do guard, como manda a 01-extrator. Não reabra o `.md` para conferir o que o script já cravou. Alvo verde = a última linha é **`VALIDAÇÃO OK`**.
- **Fase 2 (camada analítica):** `Read` do form gerado e faça os `Edit`s pontuais — Status/Obs dos agentes, periculosidade, as 4 flags de EPI, documentos coletados, afastamentos, e o fechamento (`✅ AUTO-CHECK`, `⚠ CAMPOS A VERIFICAR IN LOCO`, `🚩 FLAGS PARA O PERITO`). **Regras idênticas às da 01-extrator** — não reimplemente aqui.

⛔ **NÃO copie nem reescreva as regras de extração nesta skill.** Se você se pegar decidindo TIPO de laudo, roteamento de anexo ou classificação de EPI "na mão", pare — isso é trabalho do `montar_formulario.py` + Fase 2 da `01-extrator`. Esta skill entrega o bundle; a `01-extrator` faz o resto.

## Regras de ouro

1. **Só Code + MCP autenticado.** Sem MCP (Cowork) → mandar usar `/01-extrator` manual. Auth `stale` → `nlm login`.
2. **Conteúdo intocado.** Nunca inventar nem reescrever o conteúdo (mesma trava da 01-extrator: organiza, não cria). A única limpeza permitida é tirar as citações `[n]` (e opcionalmente `**`) do Passo 3.
3. **Encadear as 5 queries no mesmo `conversation_id`** (os prompts se cruzam) e **confirmar o notebook antes de consultar** (query custa e precisa mirar o alvo certo).
4. **Bundle na ordem 1→2→3a→3b→4**, concatenado como um paste manual. O gate do script confirma no fim: alvo é `VALIDAÇÃO OK`.
5. **Upload das fontes no notebook = manual.** A skill não sobe PDF nem decide fronteira de documento; assume o notebook pronto.

## Relatório final

```
## 📥 EXTRAÇÃO AUTOMÁTICA (NotebookLM → formulário)
Notebook: [nome] · [id]
Partes buscadas: P1 [✓/⚠] · P2 [✓/⚠] · P3a [✓/⚠] · P3b [✓/⚠] · P4 [✓/⚠]
Bundle: _bundle-<nº>.md  (cópia crua dos 5 outputs)
```
Em seguida, **o relatório normal da `01-extrator`** (resultado 🔧/🚩/📇/📐 do guard + AUTO-CHECK + CAMPOS A VERIFICAR + FLAGS).
