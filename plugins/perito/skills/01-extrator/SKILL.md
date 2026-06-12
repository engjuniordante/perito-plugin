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

## Saída
Um `.md` espelhando **exatamente** seções, ordem e campos do `formulario-pericia.md` — **um campo por linha** (não compactar). Fecha com `## ✅ AUTO-CHECK`, `## ⚠ CAMPOS A VERIFICAR IN LOCO` e `## 🚩 FLAGS`.

## Arquivos a ler (só estes)
- `formulario-pericia.md` — estrutura a espelhar (seções que **não** sejam a de agentes).
- `_esqueleto-agentes.md` — bloco fixo de agentes: **copiar VERBATIM** para a saída, sempre completo (13 anexos NR-15 A–M + Periculosidade), mesmo os não citados pelo NLM. Depois sobrepor Status/Obs/medições só nos agentes com base documental.
- `04-EPIs/analise-epi-padrao.md` — **só se houver tabela de EPI** (vida útil por CA, para o EPI-resumo).
- **NÃO** abrir template `.docx`, laudos anteriores nem gabaritos de teste — não são insumo do Extrator.

## Regras de ouro
1. **Formato Notas-do-iPhone:** sem tabelas markdown (`|`) — usar listas/bullets (`·` e `—`). Tabela quebra no Notas.
2. **Nunca inventar.** Campo ausente → `[NÃO LOCALIZADO]`. "NÃO LOCALIZADO NOS AUTOS" do NLM → `[NÃO LOCALIZADO]`.
3. **Preservar o texto do NLM** em campos descritivos (atividades, citações, quesitos) — organizar, não reescrever.
4. Campos `[interno]`/`[subsídio]` ficam no formulário, marcados (não vão ao laudo).

## Mapeamento NLM → formulário

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
- Exceções (ergonomia = todo período; ata que manda avaliar tudo; data de extinção) resolvidas aqui.
- Propagar o alerta de origem da ficha (PDF digital × OCR). Reproduzir a CONFERÊNCIA OBRIGATÓRIA como checklist.

**EPI — RESUMO por agente `[interno]`** (pré-cálculo, não veio do NLM): **trazer SÓ os agentes pertinentes ao caso** (alegados na Inicial ou com indício documental). **NÃO listar agentes que não estão no caso** (ex.: frio, biológico se não há alegação nem indício). Classificar cada EPI pelo **agente que protege** (protetor → ruído; creme/luva impermeável química → óleo/álcali An.13; PFF/cartucho → poeira/químico inalável An.12/11; máscara/lente de solda → radiação An.7; vestimenta térmica → frio An.9). **Vestimenta impermeável genérica (capa, calça/blusão impermeável) → UMIDADE (An.10)**; só classificar como **defensivos (An.13)** quando o EPI for explicitamente para pulverização/hidrorrepelente/aplicação de agrotóxico — **na dúvida, umidade**. Sem EPI neutralizante: calor (An.3) e periculosidade. **Biológico (An.14) não é elidido por EPI** — só listar se houver agente biológico no caso. Cobertura = qtd × vida útil por CA (`04-EPIs/analise-epi-padrao.md`) vs meses do imprescrito (menos afastamentos): `✓` cobre · `⚠ gap N meses` · `✗` insuficiente · `[incompleto — ver ficha]`. Coluna "Neutraliza?" **em branco** (perito decide).
**4 flags de EPI** (vão para "Observações sobre os EPIs"): (1) **EPI ≠ agente que protege** (ex.: luva anticorte = proteção mecânica, não é luva impermeável química → não serve p/ An.13); (2) **entrega FORA do imprescrito** (EPI adequado só antes/depois do período → não cobre); (3) **EPI indicado (OS/PPP) mas nunca entregue** (ex.: PFF2 obrigatório na OS, sem entrega na ficha); (4) **inconsistência contestação × ficha** (defesa alega fornecimento que a ficha não comprova).

**NR-6 (Parte 3b):** transferir os 6 itens SIM/NÃO. Os dois itens 👤 (adequado ao risco / fiscalização) ficam em branco (perito).

**AGENTES (Parte 3b + Inicial) — PROCEDIMENTO:**
⚠ A "PRÉ-TRIAGEM DE AGENTES" da Parte 3b é **INSUMO, não formato de saída**. **Nunca copiá-la como a seção de agentes** — a seção é montada SEMPRE pelo esqueleto completo abaixo:
1. Copiar VERBATIM o `_esqueleto-agentes.md` (todos os 13 anexos + periculosidade, completos — mesmo os não citados pelo NLM).
2. Sobrepor a pré-triagem do NLM: agente com base documental → Status `[Presente — fonte/pág — confirmar in loco]` + Obs (alegação da Inicial / indício de EPI) + janela de exposição. **Medições em branco** (dB, IBUTG, AREN/VDVR, concentração, C.A., vida útil…) para o perito preencher — **SALVO quando há PPP/PGR/PPRA com valores citados**: aí **preencher os campos de medição com esses valores** + fonte/pág, marcando `[Presente — conforme PPP/PGR, pág __ — confirmar in loco]`.
3. Agente sem base → Status em branco + Obs "avaliar in loco". **Nunca encolher nem suprimir bloco.**
Lógica das fontes: **Inicial = pedido** (o que verificar). **Contestação defende** → negativa **não** prova ausência (nunca marcar [Ausente] por causa dela). **PPP/PGR/PPRA** = única base p/ `[Presente]` + medições. O perito decide [Ausente]/[Presente] in loco — a skill **sugere** o agente (Status `[Presente — confirmar in loco]` + Obs) mas **mantém os campos de medição em branco** para ele preencher.
**Roteamento de anexo (regra fixa):**
- Poeira/particulado → **An.12**.
- Gases/vapores com LT quantitativo → **An.11** (somente).
- **Óleos, graxas minerais e hidrocarbonetos aromáticos → SEMPRE Anexo 13** (contato dérmico), **NUNCA An.11**. No bloco L (An.13), marcar o checkbox **"Óleos e graxas minerais"** quando alegados, além de **"Outros"** (defensivos/agrotóxicos). Se o NLM pôs óleos/graxas/hidrocarbonetos no An.11, **mover para o An.13** ao consolidar (e deixar o An.11 sem esses agentes).

**PERICULOSIDADE:** status/anexo conforme pré-triagem (3b) e objeto (Parte 4). **Abastecimento / comboio / pipa / tanque / manuseio de combustível (típico de usina e atividade rural com máquinas) → marcar Anexo 2 (Inflamáveis) como `[Presente — confirmar in loco]`**, ainda que a alegação seja genérica. Eletricidade alegada → Anexo 4. Sem qualquer base → em branco.

**DOCUMENTOS COLETADOS `[interno]`:** marcar conforme status ambiental (PPP/PGR/PPRA/LTCAT).

**REGISTRO FOTOGRÁFICO:** Foto 01–06 em branco.

**QUESITOS (Parte 4) — DECISÃO POR BLOCO (não quesito a quesito):** não confiar no rótulo do arquivo — autoria pela **intenção**: Reclamante **constrói** (exige medição, exposição, falha de EPI); Reclamada **desmonta/presume EPI eficaz** (tom cético, ônus invertido, timbre de assistente técnico). Conflito → vale a intenção; dúvida → "[autoria provável: ___ — confirmar]". Bloco **médico/ergonômico** → só a linha "Bloco de perícia médica — não pertinente ao perito técnico." Bloco **técnico ou genérico** → transcrever **INTEIRO**, numeração original. **Reclamada com dois blocos** (insalubridade + médico) → trazer o de insalubridade inteiro; do médico, só a linha-resumo. "Não localizado no PJE" quando for o caso.

**OBSERVAÇÕES GERAIS / DITADO `[subsídio]`:** deixar em branco com o roteiro curto visível.

## Fechamento (auto-validação Claude-side)
```
## ✅ AUTO-CHECK DA EXTRAÇÃO
- TIPO de laudo veio do PEDIDO da Inicial (não da ata)? [Sim/Não]
- Agentes: 13 blocos NR-15 (A–M) + Periculosidade completos (esqueleto verbatim, não encolhido)? [Sim/Não]
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
