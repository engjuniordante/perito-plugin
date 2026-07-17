---
name: perito-extrator-nlm
description: Use SÓ no Claude Code quando o perito disser "extrair do NotebookLM", "buscar do NLM", "extração automática", "montar formulário sem colar", "rodar o extrator no notebook do processo", "extrair da pasta do processo", "cria o notebook e extrai", ou informar um notebook/nº do processo OU uma PASTA com as 4 partes do processo. Faz o MESMO que a 01-extrator, mas busca as Partes 1, 2, 3a, 3b e 4 direto do NotebookLM via MCP em vez de o perito colar. Tem 2 modos: (A) notebook já pronto; (B) pasta com os 4 PDFs → cria um notebook EFÊMERO, sobe as 4 fontes, extrai e APAGA o notebook no fim. Não funciona no Cowork (que não enxerga o MCP).
---

# Perito Extrator NLM — extração automática do NotebookLM (exclusiva do Claude Code)

Esta skill faz **exatamente o que a `01-extrator` faz**, com **uma única diferença**: em vez de o perito colar manualmente os 5 outputs do NotebookLM, ela os **busca sozinha** via MCP `notebooklm-mcp` e monta o mesmo `_bundle`. Daí em diante, **o pipeline é o da `01-extrator`, intocado** (`montar_formulario.py` + Fase 2).

> **Fonte única das regras:** esta skill **NÃO** redefine as regras de extração. Tudo que é TIPO de laudo, agentes, EPI, quesitos, roteamento de anexo, formato Notas-do-iPhone, `[NÃO LOCALIZADO]`, AUTO-CHECK, etc. vive na `01-extrator/SKILL.md`. Aqui só trocamos a **entrada** (paste → MCP). Se algo divergir, vale a `01-extrator`.

## Dois modos de entrada

O que muda é **só como o notebook chega** — daí em diante (Passos 2→4) é idêntico.

- **Modo A — notebook já pronto** (comportamento original): o perito aponta um notebook que **já tem as 4 fontes subidas**. Segue direto para o **Passo 1A**.
- **Modo B — pasta → notebook efêmero** (novo): o perito aponta uma **pasta com os 4 PDFs do processo** (`1-INICIAL`, `2-CONTESTAÇÃO E DOCUMENTOS`, `3-EPI`, `4-ATA E QUESITOS`). A skill **cria** um notebook, **sobe as 4 fontes**, extrai e, no fim, **APAGA** o notebook automaticamente. Faça o **Passo 1B** no lugar do 1A.

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

## Passo 1B — (Modo B) Criar notebook efêmero a partir da pasta

> Modo efêmero **puro**: o notebook criado aqui existe só para esta extração e é **apagado no fim** (Passo 5). Confirmado pelo perito como padrão — **não** pare para pedir permissão de criar/apagar a cada rodada.

1. **Localizar a pasta.** O perito dá o **caminho absoluto** da pasta (ex.: `G:\Meu Drive\Base Perícia Irineu\Irineu teste\SAMANTA ...`) **ou** o nome de uma subpasta sob `config.notebooklm.pasta_processos` (se esse campo existir). Ausente → **pergunte** o caminho. ⚠ **Caminho do Windows real** (disco, não sandbox): o servidor MCP roda nesta máquina e lê `G:\...`, `C:\...` diretamente.
2. **Achar os 4 PDFs.** `ls`/`Glob` na pasta. Espere **4 partes**: **inicial**, **contestação (+docs)**, **EPI/ficha**, **ata+quesitos**. Os nomes variam (`1-INICIAL.pdf`, `2-CONTESTAÇÃO E DOCUMENTOS.pdf`, `3-EPI.pdf`, `4-ATA E QUESITOS.pdf` — ou `1-peticao inicial`, `4-ficha de epi`, etc.). Case pela **posição/número no nome** e pelo assunto. Ignore arquivos que **não** são das 4 partes (ex.: `FORMULÁRIO DE CAMPO.pdf`, `LAUDO.pdf` — são saída, não entrada).
   - **≠ 4 arquivos, ou não dá pra mapear as 4 partes com confiança** → **PARE e mostre ao perito** a lista de arquivos e o mapeamento que você inferiu; peça confirmação/ajuste antes de subir. Nunca chute fronteira de documento.
3. **Criar o notebook.** `mcp__notebooklm-mcp__notebook_create(title="EFÊMERO — <nome da pasta>")`. O prefixo `EFÊMERO —` é a rede de segurança: se o Passo 5 não apagar (falha na extração), dá pra achar e limpar depois. Guarde o `notebook_id`.
4. **Subir as 4 fontes, esperando a indexação.** Para **cada** PDF: `mcp__notebooklm-mcp__source_add(notebook_id=<id>, source_type="file", file_path="<caminho Windows do PDF>", wait=True, wait_timeout=300)`. O `wait=True` **segura até o NotebookLM terminar de processar** aquela fonte — é o que impede query cedo demais (que voltaria vazia e viraria `[NÃO LOCALIZADO]` silencioso). Se um `source_add` **estourar o timeout** ou voltar erro, **repita** aquele arquivo (ou aumente `wait_timeout`); PDF pesado (contestação com docs) pode demorar.
5. **Conferir que as 4 indexaram.** `mcp__notebooklm-mcp__notebook_get(notebook_id=<id>)` → confirme **4 fontes** presentes/processadas. **< 4 fontes prontas** → **não consulte ainda**: re-suba a que faltou (Passo 1B.4) e só então avance. Consultar com fonte faltando = formulário pela metade.
6. Notebook pronto e confirmado → siga para o **Passo 2** (daqui é igual ao Modo A). Leve o `notebook_id` e a **flag "efêmero"** até o Passo 5.

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

## Passo 5 — (só Modo B) Apagar o notebook efêmero

Só quando veio do **Passo 1B** (flag "efêmero"). No Modo A **nunca** apague — o notebook é do perito.

**Trava de sucesso — apague só quando a extração deu certo.** Considere sucesso quando: as 5 partes retornaram conteúdo real (nenhuma vazia por auth/indexação) **E** a Fase 1 chegou em **`VALIDAÇÃO OK`** com o bundle gravado. Isso protege o pedaço caro (construir o notebook): se algo falhou antes, o notebook fica de pé para você inspecionar/re-rodar sem reconstruir.

- **Sucesso** → `mcp__notebooklm-mcp__notebook_delete(notebook_id=<id>, confirm=True)`. A escolha do perito pelo fluxo efêmero **é** a aprovação padrão — **não** pare para perguntar "posso apagar?" a cada rodada; apague e **registre no relatório** que apagou (nome + id).
- **Falhou** (parte vazia, timeout de indexação, `VALIDAÇÃO` não-OK, ou você não tem certeza de que o formulário saiu bom) → **NÃO apague**. Mantenha o notebook, diga o **nome + id** (`EFÊMERO — …`) e o que falhou, e ofereça: re-rodar as queries no mesmo notebook, ou apagar mesmo assim se ele confirmar.

⚠ `notebook_delete` é **IRREVERSÍVEL**. Confira que o `notebook_id` é o que **você criou no Passo 1B** (título `EFÊMERO — …`) — nunca apague um notebook do Modo A nem outro qualquer.

## Regras de ouro

1. **Só Code + MCP autenticado.** Sem MCP (Cowork) → mandar usar `/01-extrator` manual. Auth `stale` → `nlm login`.
2. **Conteúdo intocado.** Nunca inventar nem reescrever o conteúdo (mesma trava da 01-extrator: organiza, não cria). A única limpeza permitida é tirar as citações `[n]` (e opcionalmente `**`) do Passo 3.
3. **Encadear as 5 queries no mesmo `conversation_id`** (os prompts se cruzam) e **confirmar o notebook antes de consultar** (query custa e precisa mirar o alvo certo).
4. **Bundle na ordem 1→2→3a→3b→4**, concatenado como um paste manual. O gate do script confirma no fim: alvo é `VALIDAÇÃO OK`.
5. **Fronteira de documento nunca se chuta.** No Modo A o upload é manual (notebook já pronto). No Modo B a skill sobe os 4 PDFs **já separados na pasta** — ela **não divide** PDF; se não achar as 4 partes claras, para e confirma com o perito.
6. **Efêmero só apaga no sucesso** (Modo B). Notebook `EFÊMERO — …`, apagado com `confirm=True` após `VALIDAÇÃO OK`; falhou → fica de pé. Modo A **nunca** apaga.

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
