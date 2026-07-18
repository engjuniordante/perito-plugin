---
name: perito-extrator-nlm
description: Use SÓ no Claude Code quando o perito disser "extrair processo", "extrair do NotebookLM", "buscar do NLM", "extração automática", "montar formulário sem colar", "rodar o extrator no notebook do processo", "extrair da pasta do processo", "cria o notebook e extrai", ou informar um notebook/nº do processo OU uma PASTA com as 4 partes do processo. Faz o MESMO que a 01-extrator, mas busca as Partes 1, 2, 3a, 3b e 4 direto do NotebookLM via MCP em vez de o perito colar. Tem 2 modos: (A) notebook já pronto; (B) pasta com os 4 PDFs → cria um notebook EFÊMERO, sobe as 4 fontes, extrai e APAGA o notebook no fim. Não funciona no Cowork (que não enxerga o MCP).
---

# Perito Extrator NLM — extração automática do NotebookLM (exclusiva do Claude Code)

Esta skill faz **exatamente o que a `01-extrator` faz**, com **uma única diferença**: em vez de o perito colar manualmente os 5 outputs do NotebookLM, ela os **busca sozinha** via MCP `notebooklm-mcp` e monta o mesmo `_bundle`. Daí em diante, **o pipeline é o da `01-extrator`, intocado** (`montar_formulario.py` + Fase 2).

> **Fonte única das regras:** esta skill **NÃO** redefine as regras de extração. Tudo que é TIPO de laudo, agentes, EPI, quesitos, roteamento de anexo, formato Notas-do-iPhone, `[NÃO LOCALIZADO]`, AUTO-CHECK, etc. vive na `01-extrator/SKILL.md`. Aqui só trocamos a **entrada** (paste → MCP). Se algo divergir, vale a `01-extrator`.

## Dois modos de entrada

O que muda é **só como o notebook (ou o bundle) chega**.

- **Modo A — notebook já pronto** (comportamento original): o perito aponta um notebook que **já tem as 4 fontes subidas**. Vá para o **Passo 1A** e siga os Passos 2→4 (você roda as 5 queries pela MCP).
- **Modo B — pasta → notebook efêmero** (o "extrair processo"): o perito aponta uma **pasta com os 4 PDFs do processo** (`1-INICIAL`, `2-CONTESTAÇÃO E DOCUMENTOS`, `3-EPI`, `4-ATA E QUESITOS`). Vá para o **Passo 1B**, que **dispara o script `extrai_processo.py`**: ele cria o notebook, sobe as 4 fontes, roda os 5 prompts, grava o `_bundle` e **apaga** o notebook — **tudo no terminal, sem gastar token**. Você recebe o bundle pronto e vai direto ao **Passo 4** (pipeline + Fase 2).

Como decidir: se o perito deu **caminho de pasta / nome de pasta / "os 4 arquivos"** → Modo B. Se deu **nome de notebook / nº do processo já com notebook** → Modo A. Na dúvida, **pergunte**.

## Passo 0 — Pré-requisitos (Code + MCP + config)

1. **Só Claude Code.** Se as ferramentas `mcp__notebooklm-mcp__*` **não existirem** nesta sessão (é o caso do Cowork/app), **PARE** e diga: *"Extração automática só roda no Claude Code. No Cowork, use `/01-extrator` e cole os 5 outputs do NotebookLM manualmente."*
2. **MCP autenticado.** Chame `mcp__notebooklm-mcp__server_info` e olhe `auth_status`:
   - `configured` → segue.
   - `stale` / `not_configured` → **PARE** e instrua: *"O NotebookLM precisa de login nesta máquina. Rode no terminal: `nlm login` (na conta Google do perito) e tente de novo."* (No PC do Irineu, é o `nlm login` da conta dele — feito uma vez.)
   - `unverified` → tente seguir (as credenciais em cache podem funcionar); se a 1ª query falhar por auth, aí sim mande rodar `nlm login`.
3. **`perito-config.json`** na **raiz do projeto** — mesmo padrão das outras skills (schema em `_perito-config.md`). Identidade = `config.perito`; caminhos = `config.caminhos`.
4. **Caminho dos prompts** = `config.notebooklm.prompts_extracao` (**caminho ABSOLUTO** — no Code é disco real, não sandbox). Ausente no config → **pergunte** ao perito o caminho do arquivo de prompts (ex.: `G:\Meu Drive\Base Perícia Irineu\prompts-extracao-notebooklm.md`) e **ofereça salvar** no config (bloco `notebooklm.prompts_extracao`) para não perguntar de novo.

## Passo 1A — (Modo A) Identificar o notebook do processo

1. O perito informa **nº do processo**, **reclamante** ou **nome do notebook**.
2. `mcp__notebooklm-mcp__notebook_list` → casar pelo que ele deu.
3. **1 candidato claro** → **confirme com o perito** (mostre `nome` + `id`) **antes** de consultar.
4. **Vários / nenhum** → liste os candidatos e pergunte qual é.
5. ⛔ **NUNCA** rodar query sem o notebook **confirmado** — a consulta custa e precisa mirar o alvo certo. No Modo A, a skill **assume que o notebook já tem as 4 fontes** (upload feito antes, na mão). → siga para o **Passo 2**.

## Passo 1B — (Modo B) Rodar o script `extrai_processo.py` (pasta → bundle, tudo mecânico)

> Modo efêmero **puro**: um script faz **toda a parte mecânica** — cria o notebook, sobe os 4 PDFs esperando indexar, roda os 5 prompts encadeados, limpa as citações, grava o `_bundle-<nº>.md` e **apaga o notebook**. Isso roda no **terminal, via o CLI `nlm`, sem gastar token de modelo**. Quando o perito disser "extrair processo" e apontar uma **pasta**, é isto que você dispara — você **não** faz as chamadas MCP uma a uma.

1. **Localizar a pasta.** O perito dá o **caminho absoluto** da pasta (ex.: `G:\Meu Drive\Base Perícia Irineu\Irineu teste\SAMANTA ...`) **ou** o nome de uma subpasta sob `config.notebooklm.pasta_processos`. Ausente → **pergunte** o caminho.
2. **Disparar o script** (Windows/Code: **`python`**, não `python3`):
   ```
   python <plugin>/skills/01b-extrator-nlm/extrai_processo.py "<pasta>" --out "<config.caminhos.formularios_campo>/_bundle-<nº|auto>.md"
   ```
   - O script **auto-descobre** o `perito-config.json` (subindo a partir da pasta) e lê dele os `prompts_extracao` e a pasta de saída — então, se a pasta estiver **dentro** da base, basta `python extrai_processo.py "<pasta>"`. Passe `--prompts`/`--out`/`--config` só para sobrescrever.
   - Ele acha o `nlm` sozinho (inclusive o `nlm.exe` fora do PATH no Windows).
3. **Ler o resultado no stdout.** O script imprime o progresso (`✓ indexado`, `✓ P1…P4`, `🗑️ notebook apagado`) e, na **última linha**, `BUNDLE: <caminho>`. Pegue esse caminho — é o insumo do Passo 4.
4. **Tratar as saídas de erro** (o script sai com código ≠ 0 e mensagem clara):
   - `≠ 4 PDFs` na pasta → ele lista o que achou e **para**. Mostre ao perito e peça pra ajustar/renomear (o script **não** decide fronteira de documento; só sobe 4 arquivos já separados, ignorando `FORMULÁRIO…`/`LAUDO…`).
   - `auth`/`nlm login` → credenciais expiraram: rode `nlm login` (conta do perito) e re-dispare.
   - `query VAZIA` / `INVALID_ARGUMENT` / falha → o script **mantém o notebook de pé** (título `EFÊMERO — …`) e informa o id, para inspeção/re-run. Avise o perito qual parte falhou (costuma ser fonte faltando ou prompt longo demais).
5. **Sucesso** → o notebook **já foi apagado pelo script** (apaga assim que o bundle é gravado; o `montar_formulario.py` reprocessa a partir do bundle, não precisa do notebook). Vá para o **Passo 4** com o caminho do bundle. **Pule o Passo 2, 3 e 5** (o script já fez).

### Fallback (script indisponível) — MCP passo a passo
Se por algum motivo o script não puder rodar (CLI `nlm` ausente e sem conserto na hora), dá para fazer o mesmo pela MCP, **na mão**: `notebook_create(title="EFÊMERO — <pasta>")` → para cada PDF `source_add(source_type="file", file_path="<Windows>", wait=True, wait_timeout=300)` → `notebook_get` conferindo 4 fontes → siga o **Passo 2/3** (as 5 queries) → e o **Passo 5** (apagar). ⚠ Atenção ao **limite de ~4,8k chars por query**: mande as **REGRAS GERAIS como um turno de priming** próprio e cada Parte encadeada no mesmo `conversation_id` — **não** cole REGRAS+P1 juntos (estoura o limite e volta `INVALID_ARGUMENT`).

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

## Passo 5 — (só Modo B, caminho MCP/fallback) Apagar o notebook efêmero

> No caminho normal do **Passo 1B o próprio `extrai_processo.py` já apagou** o notebook — **pule este passo**. Ele só vale para o **fallback MCP** (quando você criou/subiu na mão).

Só quando o notebook foi criado na mão pela MCP (fallback). No Modo A **nunca** apague — o notebook é do perito.

**Trava de sucesso — apague só quando a extração deu certo.** Considere sucesso quando: as 5 partes retornaram conteúdo real (nenhuma vazia por auth/indexação) **E** a Fase 1 chegou em **`VALIDAÇÃO OK`** com o bundle gravado. Isso protege o pedaço caro (construir o notebook): se algo falhou antes, o notebook fica de pé para você inspecionar/re-rodar sem reconstruir.

- **Sucesso** → `mcp__notebooklm-mcp__notebook_delete(notebook_id=<id>, confirm=True)`. A escolha do perito pelo fluxo efêmero **é** a aprovação padrão — **não** pare para perguntar "posso apagar?" a cada rodada; apague e **registre no relatório** que apagou (nome + id).
- **Falhou** (parte vazia, timeout de indexação, `VALIDAÇÃO` não-OK, ou você não tem certeza de que o formulário saiu bom) → **NÃO apague**. Mantenha o notebook, diga o **nome + id** (`EFÊMERO — …`) e o que falhou, e ofereça: re-rodar as queries no mesmo notebook, ou apagar mesmo assim se ele confirmar.

⚠ `notebook_delete` é **IRREVERSÍVEL**. Confira que o `notebook_id` é o que **você criou no Passo 1B** (título `EFÊMERO — …`) — nunca apague um notebook do Modo A nem outro qualquer.

## Regras de ouro

1. **Só Code + `nlm` autenticado.** Sem MCP/CLI (Cowork) → mandar usar `/01-extrator` manual. Auth expirado → `nlm login` (conta do perito).
2. **Conteúdo intocado.** Nunca inventar nem reescrever o conteúdo (mesma trava da 01-extrator: organiza, não cria). A única limpeza é tirar as citações `[n]` (e `**`) — o script já faz isso.
3. **Modo B = disparar o script, não fazer MCP na mão.** O `extrai_processo.py` faz create→upload(4, wait)→5 queries encadeadas→bundle→delete no terminal, **sem token**. Só caia para a MCP passo a passo se o script não puder rodar (fallback do Passo 1B).
4. **Limite de ~4,8k chars por query.** REGRAS GERAIS vão como **turno de priming** próprio; cada Parte encadeada no mesmo `conversation_id`. **Nunca** colar REGRAS+P1 juntos (estoura → `INVALID_ARGUMENT`). O script já respeita isso; no fallback MCP, você também.
5. **Bundle na ordem 1→2→3a→3b→4.** O gate do `montar_formulario.py` (Passo 4) confirma no fim: alvo é `VALIDAÇÃO OK`.
6. **Fronteira de documento nunca se chuta.** O script sobe os 4 PDFs **já separados na pasta** (ignora `FORMULÁRIO…`/`LAUDO…`); se não houver exatamente 4, **para** e você confirma com o perito. Não divide PDF.
7. **Efêmero apaga sozinho no sucesso** (Modo B). O script apaga assim que grava o bundle (o pipeline reprocessa do bundle, não precisa do notebook). Falha → mantém o `EFÊMERO — …` de pé para inspeção. Modo A **nunca** apaga.

## Relatório final

```
## 📥 EXTRAÇÃO AUTOMÁTICA (NotebookLM → formulário)
Modo: [A — notebook pronto] | [B — pasta → efêmero]
Notebook: [nome] · [id]   (Modo B: "EFÊMERO — …")
Fontes (Modo B): 4 subidas · indexadas [✓/⚠]
Partes buscadas: P1 [✓/⚠] · P2 [✓/⚠] · P3a [✓/⚠] · P3b [✓/⚠] · P4 [✓/⚠]
Bundle: _bundle-<nº>.md  (cópia crua dos 5 outputs)
Notebook efêmero: [APAGADO ✓ | MANTIDO — <motivo>]   (só Modo B)
```
Em seguida, **o relatório normal da `01-extrator`** (resultado 🔧/🚩/📇/📐 do guard + AUTO-CHECK + CAMPOS A VERIFICAR + FLAGS).
