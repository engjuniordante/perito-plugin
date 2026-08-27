---
name: perito-extrator-nlm
description: Use SÓ no Claude Code quando o perito disser "extrair lote", "extrair em lote", "rodar o lote", "processar lote", "extrair processo", "extrair do NotebookLM", "buscar do NLM", "extração automática", "montar formulário sem colar", "rodar o extrator no notebook do processo", "extrair da pasta do processo", "cria o notebook e extrai", ou informar um notebook/nº do processo OU uma PASTA com as 4 partes do processo. "extrair lote"/"extrair processo" (sem apontar pasta) = modo LOTE do script (fila da pasta Extração-notebooklm). Faz o MESMO que a 01-extrator, mas busca as Partes 1, 2, 3a, 3b e 4 direto do NotebookLM via MCP em vez de o perito colar. Tem 2 modos: (A) notebook já pronto; (B) pasta com os 4 PDFs → cria um notebook EFÊMERO, sobe as 4 fontes, extrai e APAGA o notebook no fim. Não funciona no Cowork (que não enxerga o MCP).
---

# Perito Extrator NLM — extração automática do NotebookLM (exclusiva do Claude Code)

Esta skill faz **exatamente o que a `01-extrator` faz**, com **uma única diferença**: em vez de o perito colar manualmente os 5 outputs do NotebookLM, ela os **busca sozinha** via MCP `notebooklm-mcp` e monta o mesmo `_bundle`. Daí em diante, **o pipeline é o da `01-extrator`, intocado** (`montar_formulario.py` + Fase 2).

> **Fonte única das regras:** esta skill **NÃO** redefine as regras de extração. Tudo que é TIPO de laudo, agentes, EPI, quesitos, roteamento de anexo, formato Notas-do-iPhone, `[NÃO LOCALIZADO]`, AUTO-CHECK, etc. vive na `01-extrator/SKILL.md`. Aqui só trocamos a **entrada** (paste → MCP). Se algo divergir, vale a `01-extrator`.

## Dois modos de entrada

O que muda é **só como o notebook (ou o bundle) chega**.

- **Modo A — notebook já pronto** (comportamento original): o perito aponta um notebook que **já tem as 4 fontes subidas**. Vá para o **Passo 1A** e siga os Passos 2→4 (você roda as 5 queries pela MCP). ⛔ O Modo A **nunca** é saída para um Modo B que tropeçou: notebook único = ficha de EPI não isolada. Se a entrada foi uma **pasta**, o desfecho é o script rodar ou a skill **parar**.
- **Modo B — pasta → notebook efêmero** (o "extrair processo"): o perito joga as subpastas de processo (nome = **nº do processo**; dentro, as partes que existirem — `1-INICIAL`, `2-CONTESTAÇÃO E DOCUMENTOS`, `3-EPI`, `4-ATA E QUESITOS`; **≥ 1 PDF já roda** — se a reclamada sumiu e só há a inicial, extrai igual e o resto vira `[NÃO LOCALIZADO]`) dentro de `config.notebooklm.pasta_processos` (a pasta `Extração-notebooklm`). Vá para o **Passo 1B**, que **dispara o script `extrai_processo.py`**: para cada subpasta ele cria o notebook, sobe as 4 fontes, roda os 5 prompts, grava o `_bundle`, **apaga** o notebook e **move a subpasta para `Processados/`** — **em fila, tudo no terminal, sem gastar token**. Você recebe os bundles prontos e vai ao **Passo 4** (pipeline + Fase 2) para cada um.

Como decidir: se o perito deu **caminho de pasta / nome de pasta / "os 4 arquivos"** → Modo B. **Uma vez em Modo B, não se troca de modo** — nem se o `nlm` parecer quebrado, nem se o script falhar. Se deu **nome de notebook / nº do processo já com notebook** → Modo A. Na dúvida, **pergunte**.

## Passo 0 — Pré-requisitos (Code + MCP + config)

1. **Só Claude Code.** Se as ferramentas `mcp__notebooklm-mcp__*` **não existirem** nesta sessão (é o caso do Cowork/app), **PARE** e diga: *"Extração automática só roda no Claude Code. No Cowork, use `/01-extrator` e cole os 5 outputs do NotebookLM manualmente."*
2. **MCP autenticado.** Chame `mcp__notebooklm-mcp__server_info` e olhe `auth_status`:
   - `configured` → segue.
   - `stale` / `not_configured` → **PARE** e instrua: *"O NotebookLM precisa de login nesta máquina. Rode no terminal: `nlm login` na **conta Google do próprio perito** (a dele, onde estão os notebooks dele — nunca a do desenvolvedor/dono da máquina) e tente de novo."* (No PC do Irineu, é o `nlm login` da conta **do Irineu** — feito uma vez.)
   - `unverified` → tente seguir (as credenciais em cache podem funcionar); se a 1ª query falhar por auth, aí sim mande rodar `nlm login`.
   - ⚠️ **Antes de mandar relogar, confira a versão pelo `--doctor` do item 3 (ele exige ≥ `0.9.4`).** O NotebookLM migrou para o domínio `notebook.google.com`; versões ≤ 0.8.9 não reconhecem o domínio novo e o `nlm login` fica 5 min em *"Still waiting for sign-in…"* e morre em **`Login timeout` mesmo com o navegador já logado** — mandar relogar de novo não resolve. Se estiver abaixo, instrua **nesta ordem**: `Get-Process | Where-Object { $_.ProcessName -match 'notebooklm' } | Stop-Process -Force` → `python -m pip install --user --upgrade notebooklm-mcp-cli` → `nlm login` → **reiniciar o Claude Code**.
3. **(Modo B) O gate do `nlm` é um COMANDO, não um julgamento seu.** Rode:
   ```
   python <plugin>/skills/01b-extrator-nlm/extrai_processo.py --doctor
   ```
   e **obedeça o VEREDITO** que ele imprime: `nlm UTILIZÁVEL` → siga para o Passo 1B; `nlm INDISPONÍVEL` → **PARE**, repasse ao perito o bloco CONSERTO que o próprio doctor imprime e **encerre o turno**.
   - ⛔ **Nunca** rode `nlm` cru para decidir isto. `command not found` no comando cru é o PATH quirk normal — o `nlm.exe` é instalado pelo `pip --user` numa pasta de Scripts que não está no PATH do shell —, e o doctor procura lá (é a mesma busca do `localizar_nlm()` do script, agora ancorada no `sysconfig` do interpretador, sem chutar número de versão do Python). Nesta casa o comando cru falha e o doctor responde `0.9.13`: máquina sadia.
   - ⛔ Gate reprovado **não** libera o Modo A, nem a MCP na mão, nem "só desta vez": o desfecho de um doctor reprovado é **PARAR**. Ver *Se o script não puder rodar*, no fim do Passo 1B.
4. **`perito-config.json`** na **raiz do projeto** — mesmo padrão das outras skills (schema em `_perito-config.md`). Identidade = `config.perito`; caminhos = `config.caminhos`.
5. **Caminho dos prompts** = `config.notebooklm.prompts_extracao` (**caminho ABSOLUTO** — no Code é disco real, não sandbox). O script resolve sozinho: o arquivo VIVO vence, e quando ele não é alcançável cai na **cópia bundled** `assets/prompts-extracao-notebooklm.md` (mesmo padrão da base CAEPI — o bash do Cowork não enxerga o Drive), avisando no console que pode estar atrás. Então **não trave o fluxo por isso**; ausente no config, siga com a bundled e **ofereça salvar** o caminho vivo (bloco `notebooklm.prompts_extracao`) para o perito passar a usar a dele. ⚠️ Ao editar os prompts VIVOS, rode `python test_contrato_prompts.py` — ele confere que o arquivo ainda pede as 15 seções e os 5 marcadores de que o parser depende, e que **nenhum prompt passa do teto de ~4,8k chars por query**; sem isso, um ▶ derrubado sai como **formulário vazio**, e um prompt que engordou sai como `INVALID_ARGUMENT` na via de emergência da ficha.

## Passo 1A — (Modo A) Identificar o notebook do processo

1. O perito informa **nº do processo**, **reclamante** ou **nome do notebook**.
2. `mcp__notebooklm-mcp__notebook_list` → casar pelo que ele deu.
3. **1 candidato claro** → **confirme com o perito** (mostre `nome` + `id`) **antes** de consultar.
4. **Vários / nenhum** → liste os candidatos e pergunte qual é.
5. ⛔ **NUNCA** rodar query sem o notebook **confirmado** — a consulta custa e precisa mirar o alvo certo. No Modo A, a skill **assume que o notebook já tem as 4 fontes** (upload feito antes, na mão). → siga para o **Passo 2**.
6. ⛔ **Se existir a pasta do processo com a ficha de EPI em arquivo separado, o Modo A está PROIBIDO** — vá para o **Passo 1B**. Um notebook com os 4 PDFs juntos não isola a ficha, e a Parte 3a sai plausível e errada (ver o bloco FICHA DE EPI EM NOTEBOOK PRÓPRIO no Passo 1B). O Modo A só serve quando não há pasta a processar — o notebook já existe e é tudo o que há.

## Passo 1B — (Modo B) Rodar o script `extrai_processo.py` (pasta → bundle, tudo mecânico)

> Modo efêmero **puro**: um script faz **toda a parte mecânica** — cria o notebook, sobe os 4 PDFs esperando indexar, roda os 5 prompts encadeados, limpa as citações, grava o `_bundle-<nº>.md` e **apaga o notebook**. Isso roda no **terminal, via o CLI `nlm`, sem gastar token de modelo**. Quando o perito disser "extrair processo" e apontar uma **pasta**, é isto que você dispara — você **não** faz as chamadas MCP uma a uma.

**Duas formas de disparar** (Windows/Code: **`python`**, não `python3`; o script auto-descobre o `perito-config.json` subindo do caminho e acha o `nlm` sozinho):

- **LOTE (o padrão do "extrair processo")** — processa **em fila** cada subpasta de `config.notebooklm.pasta_processos` (a pasta `Extração-notebooklm`) e, a cada sucesso, **move a subpasta para `Processados/`**:
  ```
  python <plugin>/skills/01b-extrator-nlm/extrai_processo.py --lote "<config.notebooklm.pasta_processos>"
  ```
  É o que você dispara quando o perito diz só **"extrair processo"** (sem apontar pasta específica). Cada subpasta = 1 processo (nome = nº do processo, 4 PDFs dentro). Passe o caminho explícito de `pasta_processos` (o auto-config precisa de um caminho-âncora).
- **UMA pasta** — quando o perito aponta uma pasta específica:
  ```
  python <plugin>/skills/01b-extrator-nlm/extrai_processo.py "<pasta>"
  ```

1. **Ler o stdout.** O script imprime o progresso (`✓ indexado`, `✓ P1…P4`, `🗑️ notebook apagado`, `📁 movido → Processados`) e, para **cada** pasta que der certo, uma linha `BUNDLE: <caminho>`. No lote, fecha com um **RESUMO** (✅ processados / ⏭️ pulados / ❌ falhas). Colete os `BUNDLE:` — são os insumos do Passo 4 (um por processo).
2. **Tratar as saídas** (o script continua a fila mesmo se uma pasta falhar):
   - `⏭️ PULADO — nenhum PDF` → a subpasta **não tem nenhum PDF de entrada** (só `FORMULÁRIO…`/`LAUDO…`, ou vazia); ele deixa no lugar e segue. **≥ 1 PDF já roda** — processo sem contestação/EPI (reclamada sumiu) extrai com o que tiver, e as partes ausentes saem como `[NÃO LOCALIZADO]` (o pipeline lida com isso). Só pula no zero.
   - `auth`/`nlm login` → credenciais expiraram: rode `nlm login` (conta do perito) e re-dispare. (A sessão do NLM é frágil — expira em dias e um corte de rede derruba; renovar é rápido.) **Se o `nlm login` der `Login timeout` mesmo com o navegador logado → é versão velha, veja a regra do `0.9.4` no Passo 0.**
   - `❌ FALHOU` (query vazia / `INVALID_ARGUMENT` / erro) → o script **mantém aquele notebook de pé** (título `EFÊMERO — …`, id no resumo) e **não move** a subpasta, para inspeção/re-run; segue para a próxima.
3. **Sucesso** → o notebook **já foi apagado** e a subpasta **já foi movida** pelo script. Vá para o **Passo 4** com cada bundle. **Pule os Passos 2, 3 e 5** (o script já fez). No lote, rode o Passo 4 (pipeline + Fase 2) **para cada** bundle da fila.

> **FICHA DE EPI EM NOTEBOOK PRÓPRIO (padrão desde a v1.0.98).** O PDF da ficha (nome com `ficha` ou `epi`) **sai do notebook do lote** e sobe sozinho num segundo notebook efêmero (`EFÊMERO — ficha <pasta>`), onde roda a **Parte 3a**. Motivo, medido em processo real: dividindo o mesmo notebook com a contestação, a 3a devolveu **2 a 3 entregas de uma ficha que tem centenas** — a disputa é na **indexação**, não na pergunta, e por isso filtrar a fonte na consulta **não** substitui subir sozinha. É o pior modo de falhar que existe aqui, porque a ficha perdida não sai vazia, sai **plausível**: uma tabela bem formatada com 5 entregas de uma ficha que tem 29.
> No stdout isso aparece como `🧾 ficha de EPI em notebook PRÓPRIO: …` e `🆕 notebook da ficha: …`; no sucesso **os dois** notebooks são apagados, e numa falha **os dois** ficam de pé para inspeção. Como a 3a sai da conversa do lote, o script leva junto o **marco do imprescrito** apurado na P1 (a 3a precisa dele para a linha `▼▼▼`) e entrega à **3b** um **resumo** da ficha (nº de entregas, faixa de datas, C.A. distintos) no lugar da tabela inteira, que não caberia no limite da mensagem. Sem arquivo de ficha separado (ela vem embutida na contestação), ou quando a ficha é o **único** PDF da pasta, nada muda e a 3a roda no lote como antes. Para forçar o comportamento antigo: `--ficha-no-lote`.

> **A FICHA VEM POR ARTEFATO, NÃO POR CHAT (padrão desde a v1.0.99).** Dentro do notebook da ficha, a **Parte 3a** não é mais uma pergunta de chat: o script pede um **data-table do Studio** e **baixa o CSV**, que vira a tabela da 3a. Motivo: o notebook próprio resolve a *indexação*, mas **não** o **teto da resposta de chat**. Medido no 0015098-90 (195 fls., 255 entregas reais), seis tentativas de chat para o mesmo PDF deram `64 · 240 · 240 · 0 · 250` — seis prompts, seis resultados — e o artefato deu `253`. A causa é estrutural, não de prompt: **o artefato escreve em arquivo e não tem teto**. Medido nesta casa (0011183-33, ficha manuscrita de 20 fls.): **artefato = 395 entregas em ~3,5 min; o chat não devolveu nada, estourou o timeout de 300 s**.
> No stdout: `🧮 data-table pedido…` → `⬇ CSV baixado…` → `✓ P3a(artefato): N entregas`. **Se o artefato falhar por qualquer motivo, o script cai sozinho para o chat** e avisa em uma linha que a via de fallback **tem teto** — nesse caso confira o total de entregas contra a ficha. Para forçar a via antiga: `--ficha-por-chat`. Espera do artefato: `--artefato-timeout` (900 s por padrão).
> ⚠ Não use `nlm status artifacts` para saber se ficou pronto: **está quebrado na 0.9.13** (`TypeError: '<=' not supported between instances of 'int' and 'OptionInfo'`). O script sonda tentando o **download** direto, que funciona.
> Dois cuidados que a medição impôs e que já estão no código: a coluna do CSV é casada por **palavra-chave, nunca por posição** (o cabeçalho vem do modelo e varia — e a ferramenta ainda acrescenta uma coluna `Source` por conta própria); e **`1,000` é UMA unidade com três casas decimais, não mil** — ler como milhar multiplica a cobertura daquele EPI por mil. Toda linha que não vira entrega sai **nomeada** no bloco `▶ CONFERÊNCIA OBRIGATÓRIA NA FICHA ORIGINAL`, nunca em silêncio.

> **REGRAS GERAIS:** por padrão o script roda **sem** o bloco REGRAS (`--regras off`) — cada Parte já traz as próprias regras, e a P1 sai mais completa sozinha. Se algum dia precisar, `--regras priming` (turno próprio) ou `--regras inline` (cola na P1 se couber no limite).

### Se o script não puder rodar — o que fazer (e o que NÃO fazer)

> ⛔ **O desfecho de um `--doctor` reprovado é PARAR.** Não existe plano B para o Modo B: nem Modo A, nem `notebook` + fontes na mão pela MCP, nem "só desta vez para não perder a viagem". Não é preferência, é medição: (a) na mão os PDFs vão todos para **um** notebook, e a Parte 3a dividindo indexação com a contestação devolveu **2 a 3 entregas de uma ficha que tem centenas**; (b) na mão não há **artefato do Studio**, então a 3a vai por chat, que **tem teto de resposta**; (c) o prompt da 3a é o maior do arquivo e passa raspando o **limite de ~4,8k chars por query** — acima dele volta `INVALID_ARGUMENT` e a 3a **não roda**. Os três somados dão o pior desfecho desta skill: uma tabela **bem formatada e errada**, que o perito só descobre com a ficha na mão, na diligência.
> Aconteceu **duas vezes** — 26/08 e 27/08, instalação nova no PC do perito — e nas duas o gatilho foi o mesmo `command not found` no `nlm` cru, numa máquina sadia. É esse julgamento que o `--doctor` tira das suas mãos: **não o repita**.
> **O que fazer, na ordem:** repasse ao perito o bloco CONSERTO impresso pelo doctor → apague qualquer notebook `EFÊMERO — …` que tenha ficado de pé → **descarte o bundle** daquela rodada (ele está contaminado) → **encerre o turno**. Consertado o `nlm`, re-rode o Passo 1B do zero.

**A única exceção** é a pasta **sem ficha de EPI em arquivo separado** (a ficha vem embutida na contestação — aí não há o que isolar e a 3a rodaria no lote de qualquer jeito). O passo a passo dela mora **fora deste arquivo**, em `assets/fallback-mcp-na-mao.md`, de propósito: enquanto o procedimento estiver escrito aqui, ele é a saída fácil de qualquer tropeço. **Só abra esse arquivo depois de listar os PDFs da pasta e confirmar que não existe arquivo de ficha/EPI.** Existindo, ele não se aplica — vale o ⛔ acima.

## Passo 2 — Ler os 5 prompts (verbatim, do arquivo)

> **Passos 2 e 3 são do MODO A** (e da exceção estreita do `assets/fallback-mcp-na-mao.md`). Vindo do **Modo B**, você **não passa por aqui**: o script já rodou as 5 queries e o seu próximo passo é o **4**. Se o Modo B tropeçou, o desfecho é **PARAR** — não é descer para cá.

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
3. **Modo B = disparar o script. Ponto.** O `extrai_processo.py` faz create→upload(wait)→5 queries encadeadas→bundle→delete no terminal, **sem token**, e é o único caminho que **isola a ficha de EPI** num notebook próprio. Script fora do ar = **PARAR** e consertar o `nlm` (`--doctor`), **nunca** descer para a MCP na mão nem para o Modo A. A exceção única (pasta sem ficha em arquivo separado) está em `assets/fallback-mcp-na-mao.md`.
4. **Limite de ~4,8k chars por query.** Cada Parte encadeada no mesmo `conversation_id`; **nunca** colar REGRAS+P1 juntos (5,2k estoura → `INVALID_ARGUMENT`). Por padrão as REGRAS **não** vão (`--regras off`) — cada Parte já traz as próprias, e a P1 sai mais completa. O script já respeita isso; na exceção do `assets/fallback-mcp-na-mao.md`, rode a P1 sozinha.
5. **Bundle na ordem 1→2→3a→3b→4.** O gate do `montar_formulario.py` (Passo 4) confirma no fim: alvo é `VALIDAÇÃO OK`.
6. **Roda com o que tiver (≥ 1 PDF).** O script sobe **todos** os PDFs de entrada da pasta (ignora `FORMULÁRIO…`/`LAUDO…`) — 4, 2 ou só a inicial. Processo sem contestação/EPI extrai igual; as partes ausentes viram `[NÃO LOCALIZADO]`. Só pula no **zero** PDF. Não divide PDF nem chuta fronteira de documento. **Nº do processo:** se a extração não achar (comum quando só há a inicial — o nº é do protocolo), o script usa o **nome da subpasta** (por isso nomeie a subpasta pelo nº do processo).
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
