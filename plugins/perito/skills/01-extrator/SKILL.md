---
name: perito-extrator
description: Use quando o perito colar os outputs do NotebookLM (Partes 1, 2, 3a, 3b, 4) ou disser "formulário de campo", "consolidar extração", "montar formulário", "extrair dados do processo". Consolida os 5 outputs do NLM no formulário de campo preenchido (.md), detecta o tipo de laudo pelo pedido da petição inicial e lista os campos não localizados.
---

# Perito Extrator — consolidação da extração do NotebookLM

Você consolida os outputs brutos do NotebookLM em **um formulário de campo preenchido**, pronto para a diligência do Eng. Irineu de Freitas Branco Junior. Você organiza — **nunca inventa**. Tudo que não veio dos autos vira `[NÃO LOCALIZADO]`.

## Passo 0 — Perfil do perito (`perito-config.json`)
Ler **`perito-config.json`** na **raiz do projeto** (schema em `_perito-config.md`):
- **Identidade** (nome, CREA, cidade) = `config.perito` — **nunca o dono da máquina/usuário**. Onde este SKILL.md disser "Irineu", usar **`config.perito.nome`**.
- **Caminhos** = `config.caminhos`: base de conhecimento em `base_conhecimento`, templates em `templates`, saída em `saida_laudos`. Os `Base Perícia Irineu/...` abaixo são o exemplo do Irineu — resolver sempre pelo config.
- Sem config → **parar** e instruir: *"rode `/configurar` uma vez."*

## Entrada — 5 outputs do NLM (em sequência)
1. **Parte 1** — Processo, empresa, vínculo (identificação por função, autuação, imprescrito) + **TIPO de laudo (pedido da Inicial)**.
2. **Parte 2** — Ambiente, afastamentos, atividades, citações, participantes.
3. **Parte 3a** — Tabela de EPI (Data | Qtd | Descrição | C.A.) + evidência de assinatura.
4. **Parte 3b** — Análise crítica, status de documentos ambientais, NR-6 (6 itens), pré-triagem de agentes.
5. **Parte 4** — Escopo e quesitos.

Faltou algum? Avise qual e prossiga; o ausente vira `[NÃO LOCALIZADO]`.

## Fluxo — 2 fases (o SCRIPT faz o braçal; VOCÊ faz só a análise)

> **Por que assim:** re-digitar as ~340 linhas do formulário (ficha de EPI, 13 agentes, quesitos, identificação) é o que torrava token. Isso agora é determinístico no `montar_formulario.py`. Você entra **só** na camada que exige julgamento (Status/Obs dos agentes, flags, fechamento). Economia de ~85-90% do output, sem perder a análise.

**Onde gravar:** pasta `config.caminhos.formularios_campo` (default `Formularios-Campo`), **na raiz do projeto conectado** — criar se não existir. Nome: `Formulario-Campo-<Reclamante>-<nº processo>.md`. **Nunca** gravar na pasta da skill (some no `/plugin update`).

### Fase 1 — script monta o esqueleto (você NÃO redige)
1. Salve os 5 outputs do NLM **VERBATIM** num bundle: `Write` em `<formularios_campo>/_bundle-<nº>.md` com o texto colado **como veio** (não consolidar, não reescrever — cópia crua; já vêm em `▶ subseções`).
2. Rode UM comando:
   `python3 <pasta desta skill>/montar_formulario.py <_bundle.md> -o <Formularios-Campo>/Formulario-Campo-<Reclamante>-<nº>.md --base <base_conhecimento>`
   - O script CRAVA, determinístico e fiel: TIPO (pedido da Inicial), PROCESSO, PARTICIPANTES (só Reclamante), EMPRESA/ambiente, IDENTIFICAÇÃO (todas as funções), ESCOPO, **ficha de EPI (só imprescrito, descrição verbatim)**, NR-6 (do NLM), **QUESITOS na íntegra**, e o bloco fixo dos 13 agentes + periculosidade **com TODOS os campos** (Status, Equipamento, Nível medido/IBUTG/AREN-VDVR, Taxa metabólica, Tipo, C.A., Vida útil, PPP…).
   - E roda o **guard `check_epi.py` por dentro** (C.A. é a chave, o nome NÃO classifica): 🔧 classifica por C.A. (dicionário→CAEPI→regra absoluta creme=An.13) · 📐 cobertura (Σ qtd×vida útil, creme e protetor auditivo) · 🚩 CA vencido/conferir · 📇 não catalogados · ⏰ base >90d.
   - **Reproduza o resultado 🔧/🚩/📇/📐 do script na resposta.** Não reabra o `.md` para conferir o que o script já fez.

> ⛔ **O script é a ÚNICA fonte da estrutura. NUNCA redigir o formulário à mão.** O `montar_formulario.py` **não depende do Drive nem da rede** — só lê o bundle (que você acabou de escrever, visível ao bash) e a base **bundled** em `assets/04-EPIs/`. **Logo, roda no Cowork.** Se ele parecer falhar: leia o erro real (bundle no caminho certo? Python 3?) e **rode de novo** — não pule para a redação manual.
> **Fallback (só se o script comprovadamente não rodar, com o erro colado na resposta):** reproduza a seção **▶ AGENTES — INSALUBRIDADE (NR-15)** e a **▶ PERICULOSIDADE** **copiando VERBATIM** o bloco do `formulario-pericia.md` (13 anexos A–M + periculosidade, **cada campo de cada agente**). **Jamais** uma versão resumida/achatada (ex.: só "Status/Obs/Medição") — achatar o agente é o erro que corrompe o laudo. Marque `[X] Presente` conforme a pré-triagem; medições em branco.

### Fase 2 — você adiciona SÓ a camada analítica (via `Edit` no form gerado)
⛔ **NUNCA re-digite estrutura** (ficha, quesitos, processo, identificação — o script já fez, fiel). `Read` o form gerado e faça `Edit`s pontuais só para acrescentar:
- **Status/Obs dos agentes:** ⚙️ **o `montar_formulario.py` já PRÉ-MARCA `[X] Presente` no Status** dos agentes que a pré-triagem trouxe com base documental — na Fase 2 você **confere e refina só o Obs**. Se o script não pegou um agente que você identificou (Inicial/PPP), marque você o checkbox — mas **na linha Status marque SÓ o checkbox** `[ ] Ausente  [X] Presente` (Ausente vazio). **NUNCA escrever prosa/verdito na linha Status** (ex.: `[Presente — alegado na Inicial…]`): isso afoga o checkbox — tira do perito o espaço pra pontuar in loco **e** faz o redator ler alegação como caracterização confirmada. Toda a fundamentação (indício, fonte/pág, roteamento, janela de exposição) vai no **Obs**. Medições **em branco** (salvo PPP/PGR com valor citado → preencher + fonte). Sem base → `[ ] Ausente  [ ] Presente` (ambos vazios, avaliar in loco). Regras de roteamento: ver Mapeamento abaixo (óleos/graxas/hidrocarbonetos → **An.13**; poeira → **An.12**; gases c/ LT → **An.11**).
- **PERICULOSIDADE:** marcar o checkbox `[X] Aplicável` + o do anexo conforme pré-triagem/objeto (abastecimento/comboio/pipa/combustível → **Anexo 2 — Inflamáveis**; eletricidade → **Anexo 4**); fundamentação no Obs — **sem prosa na linha Status**.
- **Observações sobre os EPIs:** as **4 flags de EPI** (ver Mapeamento) — EPI≠agente, entrega fora do imprescrito, EPI indicado mas não entregue, contestação×ficha.
- **DOCUMENTOS COLETADOS `[interno]`:** marcar conforme status ambiental (PPP/PGR/PPRA/LTCAT).
- **AFASTAMENTOS:** se o NLM disse que não há >15 dias, substituir o bloco em branco por **uma linha** ("Não há registro de afastamento previdenciário > 15 dias nas fontes juntadas.") + o ★ último dia.
- Fechar com `## ✅ AUTO-CHECK`, `## ⚠ CAMPOS A VERIFICAR IN LOCO`, `## 🚩 FLAGS PARA O PERITO` (modelo abaixo).

A descrição da ficha é **intocável** (nome do produto verbatim — o guard bloqueia agente na descrição). A classificação por agente vive só no bloco 🔧/EPI-RESUMO.

## Arquivos a ler (só estes)
- O **template** `formulario-pericia.md` está **embutido no `montar_formulario.py`** — você **NÃO** precisa lê-lo nem espelhá-lo (o script gera o form inteiro). Ele segue na pasta como referência humana.
- Na **Fase 2**, `Read` o **form GERADO** (em `Formularios-Campo/`) para fazer os `Edit`s da camada analítica.
- **NÃO** ler `check_epi.py`/`montar_formulario.py` (caixa-preta), nem `analise-epi-padrao.md` (cobertura é do `check_epi.py`), nem template `.docx`/laudos anteriores/gabaritos. **Não rodar `find`.**
- ⚙️ **Base EPI bundled — NÃO apagar:** `assets/04-EPIs/` (`caepi.sqlite` + `CA-dicionario.json`) viaja com o plugin porque o **bash do Cowork não enxerga a pasta do Drive** (sandbox isolado). O `check_epi.py` usa a base viva do `--base` quando alcançável (Claude Code nativo) e cai na bundled quando não (Cowork). Ao atualizar o CAEPI, **re-bundle aqui** e republique.

## Regras de ouro
1. **Formato Notas-do-iPhone:** sem tabelas markdown (`|`) — usar listas/bullets (`·` e `—`). Tabela quebra no Notas.
2. **Nunca inventar.** Campo ausente → `[NÃO LOCALIZADO]`. "NÃO LOCALIZADO NOS AUTOS" do NLM → `[NÃO LOCALIZADO]`.
3. **Preservar o texto do NLM** em campos descritivos (atividades, citações, quesitos) — organizar, não reescrever.
4. Campos `[interno]`/`[subsídio]` ficam no formulário, marcados (não vão ao laudo).

## Mapeamento NLM → formulário
> ⚙️ **Os campos MECÂNICOS abaixo (TIPO, PROCESSO, PARTICIPANTES, EMPRESA, IDENTIFICAÇÃO, ESCOPO, EPIs/ficha, NR-6, QUESITOS) já são cravados pelo `montar_formulario.py`** — as regras aqui são a referência de COMO ele faz (e o que conferir). Na Fase 2 você só intervém nos **agentes (Status/Obs)**, **periculosidade**, **flags de EPI**, **documentos coletados** e **fechamento**.

**TIPO DE LAUDO ★ (Parte 1 — PEDIDO da Inicial):** marcar o `[ ]` correspondente e indicar o template. Fonte canônica = "Dos Pedidos" da Inicial. **NÃO detectar pela ata** (modelo padrão). Não ampliar por agente que aparece em PPP/PGR/contestação mas não foi pleiteado. Inicial ausente → `[NÃO LOCALIZADO — confirmar o pedido na Inicial]`; pedido ambíguo → "Insal+Peric" + sinalizar.

**PROCESSO (Parte 1):** Nº · Vara · Data/Horário/Local da diligência · **Data da autuação** (vai ao laudo).

**HONORÁRIOS:** em branco (manual).

**PARTICIPANTES (Parte 2):** só o Reclamante (Nome/Papel); 4 blocos em branco. **Papel = apenas "Reclamante"** — sem parênteses nem descrição ("comparecimento pessoal", "acompanhado por advogado" etc.). Remover `[NÃO LOCALIZADO]` dos demais.

**EMPRESA (Parte 1+2):** CNAE em subclasse oficial `XXXX-X/XX` (restaurar zero à esquerda) + descrição. Divergência entre fontes → trazer as duas com a fonte + "(divergência — confirmar)". Marcar o ambiente conforme Parte 2.

**IDENTIFICAÇÃO (Parte 1):** transcrever **todas** as funções/contratos (uma linha: Função · Setor · Início · Término · Autuação · Imprescrito). **Negrito nas funções dentro do imprescrito** + nota: "Foco da análise: apenas os contratos no imprescrito; anteriores fora do escopo." Setor ausente → `[NÃO LOCALIZADO]`. Turno = `[interno]`.

**ESCOPO (Parte 4):** marcar **só a opção** (todo período **ou** só imprescrito). Regra: ergonomia → todo período; insal/peric → imprescrito; ata expressa prevalece. **NÃO trazer a nota pericial/justificativa do NLM ao formulário** — só o checkbox marcado.

**AFASTAMENTOS (Parte 2, >15 dias):** **Se NÃO houver afastamento previdenciário > 15 dias nas fontes** → escrever **uma única linha** ("Não há registro de afastamento previdenciário > 15 dias nas fontes juntadas.") + preencher o ★ último dia efetivamente trabalhado. **Não trazer os campos vazios** de benefício/limbo/retorno (só poluem). **Se houver** → aí sim transcrever a **sequência completa** (último dia trabalhado / benefício+espécie / limbo / retorno). **Destacar "último dia efetivamente trabalhado"** (fecha a exposição). Cadeia sem retorno → consolidar no cabeçalho. ★ ausente → levar aos CAMPOS A VERIFICAR como prioridade. **Nunca incluir férias.**

**ATIVIDADES (Parte 2):** por função (reclamante/reclamada) + paradigma.

**CITAÇÕES (Parte 2):** ata com depoimento → transcrever; ata inicial sem depoimento → **deixar EM BRANCO** (não marcar `[NÃO LOCALIZADO]`). Se o NLM preencheu com `[NÃO LOCALIZADO]` + explicação, **apagar tudo e deixar o campo vazio** — **sem justificativa em lugar nenhum** (não poluir; o perito preenche in loco).

**EPIs (Parte 3a+3b):** treinamento e controle de entrega ← Parte 3b. **Separar o período UMA vez (a redatora não refaz):**
- *EPIs — período imprescrito:* entregas ABAIXO da divisória da Parte 3a.
- *Histórico anterior:* entregas ACIMA — resumir, não descartar.
- ⛔ **Descrição = NOME DO PRODUTO verbatim da ficha** (ex.: "CREME PROT PELE G3...", "PROTETOR AUDITIVO SILICONE PLUGUE") — **NUNCA, em NENHUMA etapa**, substituir pelo agente/anexo ("Ruído (An.1)", "Químico dérmico (An.13)"). **Nem ao montar, nem depois de rodar o guard.** Motivo: o perito **lê a ficha** para conferir e tirar dúvidas, e isso **reflete no laudo** — trocar o nome corrompe os dois. A classificação por agente vive **só** no bloco 🔧 (e no EPI-RESUMO, que referencia por agente); a coluna Descrição fica intocada. O `check_epi.py` **BLOQUEIA** (🚩 + exit 2) se achar agente na descrição — corrija restaurando o nome do produto da ficha.
- Exceções (ergonomia = todo período; ata que manda avaliar tudo; data de extinção) resolvidas aqui.
- Propagar o alerta de origem da ficha (PDF digital × OCR). Reproduzir a CONFERÊNCIA OBRIGATÓRIA como checklist.

**EPI — RESUMO por agente `[interno]`** (pré-cálculo, não veio do NLM): **trazer SÓ os agentes pertinentes ao caso** (alegados na Inicial ou com indício documental) — **não listar** agentes ausentes do caso. **Classificação e cobertura = do `check_epi.py`** (passo final): ele resolve o agente pelo **C.A.** (o nome comercial NUNCA classifica — "G3", "Luz Negra", "Protek" são marca, não agente) e cospe o bloco `🚩 VERIFICAÇÃO AUTOMÁTICA DE EPI` com 🔧 classificação · 📐 cobertura (Σ qtd × vida útil — creme e protetor auditivo) · 🚩 conferir. **NÃO classificar nem calcular cobertura em prosa** — deixe o agente provisório e o script resolve pelo C.A. Coluna "Neutraliza?" **em branco** (perito decide in loco).
> **Direção que o script enforce** (não precisa repetir em prosa; respeite-a — errar EXCLUINDO corrompe o laudo, errar incluindo +flag é tolerável): creme/pomada = **An.13** (exceto "protetor solar" = UV); capa/impermeável genérico = **Umidade An.10** (só "defensivos An.13" se for pulverização/hidrorrepelente/agrotóxico); **biológico não é elidido por EPI**; calor e periculosidade sem EPI neutralizante.

**4 flags de EPI** (vão para "Observações sobre os EPIs"): (1) **EPI ≠ agente que protege** (ex.: luva anticorte = proteção mecânica, não é luva impermeável química → não serve p/ An.13); (2) **entrega FORA do imprescrito** (EPI adequado só antes/depois do período → não cobre); (3) **EPI indicado (OS/PPP) mas nunca entregue** (ex.: PFF2 obrigatório na OS, sem entrega na ficha); (4) **inconsistência contestação × ficha** (defesa alega fornecimento que a ficha não comprova).

**NR-6 (Parte 3b):** transferir os 6 itens SIM/NÃO. Os dois itens 👤 (adequado ao risco / fiscalização) ficam em branco (perito).

**AGENTES (Parte 3b + Inicial) — PROCEDIMENTO:**
⚠ A "PRÉ-TRIAGEM DE AGENTES" da Parte 3b é **INSUMO, não formato de saída**. **Nunca copiá-la como a seção de agentes** — a seção é o **bloco fixo já embutido no `formulario-pericia.md`** (que o script crava). Em nenhuma hipótese achatar o agente para `Status/Obs/Medição`: **cada anexo mantém todos os seus campos** (Equipamento, Nível medido/IBUTG/AREN-VDVR, Taxa metabólica, Tipo, C.A., Vida útil, PPP…).
1. Manter o bloco de AGENTES do `formulario-pericia.md` completo (todos os 13 anexos + periculosidade — mesmo os não citados pelo NLM).
2. Sobrepor a pré-triagem do NLM (**o `montar_formulario.py` já pré-marca o checkbox** — você confere): agente com base documental → na linha Status **só o checkbox** `[ ] Ausente  [X] Presente` (Ausente vazio; **nunca prosa na linha Status**) + Obs (alegação da Inicial / indício de EPI / fonte-pág / janela de exposição). **Medições em branco** (dB, IBUTG, AREN/VDVR, concentração, C.A., vida útil…) para o perito preencher — **SALVO quando há PPP/PGR/PPRA com valores citados**: aí **preencher os campos de medição com esses valores** + fonte/pág no Obs, mantendo o Status `[X] Presente`.
3. Agente sem base → Status `[ ] Ausente  [ ] Presente` (ambos vazios) + Obs "avaliar in loco". **Nunca encolher nem suprimir bloco.**
4. ⛔ **NÃO inventariar EPI dentro das seções de agente** (J/K/L = An.11/12/13): o campo `EPI: ver bloco EPI — RESUMO (An.N)` é um **ponteiro fixo** do `formulario-pericia.md` — deixar como está, **NUNCA listar EPIs ali**. EPI×agente vive numa **fonte única**: o bloco EPI — RESUMO (lastreado pelo guard 🔧). Listar a ficha na seção do agente duplica a verdade e **vaza EPI de outro risco pro agente errado** (ex.: capa/PFF2 de umidade/pulverização caindo no An.13 de óleo).
Lógica das fontes: **Inicial = pedido** (o que verificar). **Contestação defende** → negativa **não** prova ausência (nunca marcar `[X] Ausente` por causa dela). **PPP/PGR/PPRA** = única base p/ marcar `[X] Presente` + medições. O perito decide Ausente/Presente in loco — a skill **sugere** marcando `[X] Presente` no checkbox (+ fundamentação no Obs) mas **mantém os campos de medição em branco** para ele preencher.
**Roteamento de anexo (regra fixa):**
- Poeira/particulado → **An.12**.
- Gases/vapores com LT quantitativo → **An.11** (somente).
- **Óleos, graxas minerais e hidrocarbonetos aromáticos → SEMPRE Anexo 13** (contato dérmico), **NUNCA An.11**. No bloco L (An.13), marcar o checkbox **"Óleos e graxas minerais"** quando alegados, além de **"Outros"** (defensivos/agrotóxicos). Se o NLM pôs óleos/graxas/hidrocarbonetos no An.11, **mover para o An.13** ao consolidar (e deixar o An.11 sem esses agentes).

**PERICULOSIDADE:** status/anexo conforme pré-triagem (3b) e objeto (Parte 4). **Abastecimento / comboio / pipa / tanque / manuseio de combustível (típico de usina e atividade rural com máquinas) → marcar o checkbox `[X] Aplicável` + o do Anexo 2 (Inflamáveis)**, ainda que a alegação seja genérica; fundamentação no Obs (sem prosa no Status). Eletricidade alegada → Anexo 4. Sem qualquer base → checkboxes vazios.

**DOCUMENTOS COLETADOS `[interno]`:** marcar conforme status ambiental (PPP/PGR/PPRA/LTCAT).

**REGISTRO FOTOGRÁFICO:** Foto 01–06 em branco.

**QUESITOS (Parte 4) — DECISÃO POR BLOCO (não quesito a quesito):** não confiar no rótulo do arquivo — autoria pela **intenção**: Reclamante **constrói** (exige medição, exposição, falha de EPI); Reclamada **desmonta/presume EPI eficaz** (tom cético, ônus invertido, timbre de assistente técnico). Conflito → vale a intenção; dúvida → "[autoria provável: ___ — confirmar]". Bloco **médico/ergonômico** → só a linha "Bloco de perícia médica — não pertinente ao perito técnico." Bloco **técnico ou genérico** → transcrever **INTEIRO**, numeração original. **Reclamada com dois blocos** (insalubridade + médico) → trazer o de insalubridade inteiro; do médico, só a linha-resumo. "Não localizado no PJE" quando for o caso.

**OBSERVAÇÕES GERAIS / DITADO `[subsídio]`:** deixar em branco com o roteiro curto visível.

## Fechamento (auto-validação Claude-side)

> Gate determinístico (v1.0.48): o `montar_formulario.py` já roda o `validate_form.py` por dentro (após o guard) e trava 3 invariantes SEM token — imprescrito ⊆ contrato (início≥admissão, fim≤demissão), nº do processo form×bundle, e guard de EPI carimbado. O checklist abaixo cobre o que o gate ainda NÃO valida (tipo de laudo, blocos de agente completos, CNAE, etc.).

```
## ✅ AUTO-CHECK DA EXTRAÇÃO
- TIPO de laudo veio do PEDIDO da Inicial (não da ata)? [Sim/Não]
- Agentes: 13 blocos NR-15 (A–M) + Periculosidade completos, **cada agente com todos os seus campos** (Equipamento, medição, Tipo, C.A., Vida útil…) — não achatado para só Status/Obs? [Sim/Não]
- Saída sem tabelas markdown — tudo em bullets `·`/`—`? [Sim/Não]
- Tabela de EPI cobre todo o imprescrito? [Sim/Não — período coberto × descoberto]
- Quesitos Juízo/Reclamante/Reclamada localizados? [Sim/Não]
- Afastamentos (>15 dias) com a sequência? [Sim/Não]
- CNAE em fonte primária + subclasse oficial? [Sim/Não]
- Documentos críticos (PPP/PGR/PPRA/LTCAT/Ficha EPI): status real

## ⚠ CAMPOS A VERIFICAR IN LOCO
- [todos os [NÃO LOCALIZADO] + agentes provisórios + janela de exposição]

## 🚩 FLAGS PARA O PERITO (até 5)
- [contradições documentais, lacunas de EPI, períodos descobertos, divergência defesa × provas]
```
