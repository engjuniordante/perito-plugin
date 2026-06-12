# FORMULÁRIO DE PERÍCIA — Eng. Irineu de Freitas Branco Junior

> **Fonte-mestra de dados.** A Skill 1 (Extrator) preenche este formulário em .md a partir dos 5 outputs do NotebookLM; o perito completa em loco os campos `[NÃO LOCALIZADO]`. Depois, a Skill 2/3 (Redatores) lê este formulário para montar o laudo no template correto.
>
> **Convenções:**
> - `[NÃO LOCALIZADO]` = campo não encontrado nos autos → verificar in loco.
> - `[interno]` = **não é transcrito literalmente** no laudo (uso do perito / cálculo).
> - `[subsídio]` = **não vai ao laudo na forma escrita, mas orienta a redação** — o Redator usa como base de raciocínio para a análise/conclusão (não copia o texto cru). Aplica-se ao campo OBSERVAÇÕES GERAIS e às "Obs:" de cada agente/seção.
> - `★` = obrigatório.
> - Marcar opção com `X` dentro do `[ ]`.
> - **Formato compatível com o Notas do iPhone:** sem tabelas markdown (`|`) — dados em **listas/bullets** com `·` e `—`. O perito carrega este `.md` no Notas, preenche in loco e cola de volta no Cowork para o Redator. Não usar tabelas (quebram no Notas e dão erro na volta).
> - **Estrutura é padronizada** (marcadores, listas, status `[ ]`); **conteúdo descritivo é texto livre, na voz do perito** — a skill preserva, não reescreve.

---

## ▶ TIPO DE LAUDO ★
> Detectado pelo **PEDIDO da petição inicial** (seção "Dos Pedidos" — é o que o reclamante efetivamente pleiteia). **NÃO** pela ata: ela vem em modelo padrão ("nomeio o perito para perícia de insalubridade/periculosidade") e não reflete o pedido. O Redator escolhe o template por aqui.

- [ ] Insalubridade → `template-insalubridade.docx`
- [ ] Periculosidade → `template-periculosidade.docx`
- [ ] Insalubridade + Periculosidade → `template-insal-peric.docx`
- [ ] Ergonomia → `template-ergonomico.docx`

## ▶ LAUDO BASE (opcional)
Laudo Base: (O perito irá colocar o laudo base caso tenha)

---

## ▶ PROCESSO
- Nº:
- Vara:
- Data da diligência:
- Horário:
- Local:
- **Data da autuação / ação:** *(vai ao laudo — coluna "Autuação" da tabela de identificação)*

## ▶ HONORÁRIOS *(manual — arbitrado pelo perito)*
- Valor (R$): 5.800,00
- Valor por extenso: Cinco mil e oitocentos reais

## ▶ PARTICIPANTES
*(Nome / Papel — uma linha por pessoa; o Reclamante é preenchido na extração, os demais em loco)*

Nome: 
Papel: 

Nome: 
Papel:

Nome: 
Papel:

Nome:
Papel:

Nome:
Papel:


---

## ▶ EMPRESA / ESTABELECIMENTO
- CNAE da atividade principal da Reclamada:

### Descrição do ambiente de trabalho *(marcar com X)*
- [ ] Imóvel comercial, feito em alvenaria, apresenta ventilação e iluminação natural e artificial.
- [ ] Fabril/industrial feito em alvenaria e estruturas metálicas, apresenta ventilação e iluminação natural e artificial.
- [ ] Trabalho em ambiente externo.
- [ ] Outro:

---

## ▶ RECLAMANTE
- Reclamante:
- Reclamada:

### Identificação / vínculo *(uma linha por função — alimenta a tabela de identificação do laudo)*
*(formato: Função · Setor · Início · Término · Autuação · Imprescrito)*
- Função: ____ · Setor: ____ · de ____ a ____ · Autuação: ____ · Imprescrito: ____
- Função: ____ · Setor: ____ · de ____ a ____ · Autuação: ____ · Imprescrito: ____

- Período trabalhado: de ____ até ____
- Turno: `[interno]`
- **Período imprescrito ★:** de ____ até ____

### ▶ Escopo da avaliação *(conforme ata — vai ao laudo)*
- [ ] Será avaliado **todo o período laboral**. Esse geralmente é para laudo ergonomico apenas
- [ ] Será avaliado **somente o período imprescrito** (últimos 5 anos da propositura da ação). Aplicável para insalubridade e periculosidade.

### ▶ Afastamentos / períodos a excluir
*(> 15 dias no imprescrito: acidente, doença, auxílio-doença, licença, suspensão/COVID. **Nunca contar férias.** Cada afastamento é uma SEQUÊNCIA — preencher os marcos:)*

★ **Último dia efetivamente trabalhado** (FECHA a exposição — data mais importante): ____  ·  Houve retorno? [ ] Sim  [ ] Não → rescisão em ____
*(cadeia de benefícios sem retorno → esta linha resume tudo; detalhar os benefícios abaixo)*

**Afastamento 1:**
- Último dia efetivamente trabalhado antes do afastamento: ____
- Benefício previdenciário (espécie + datas): de ____ até ____
- Limbo previdenciário / suspensão (se houve): de ____ até ____
- Retorno efetivo às atividades: ____

**Afastamento 2 (se houver):**
- Último dia trabalhado: ____ · Benefício: de ____ até ____ · Limbo: de ____ até ____ · Retorno: ____

---

## ▶ ATIVIDADES POR FUNÇÃO
*(descrever passo a passo o que o trabalhador faz; uma sub-lista por função/período)*

**Função [Nome]:**


**Função [Nome] (se houver segunda função):**


## ▶ CITAÇÕES / DEPOIMENTOS *(campo de campo — preencher in loco com o que as partes disserem; vem EM BRANCO da extração, salvo se a ata já trouxer depoimento)*
**Reclamante disse:**


**Reclamada disse:**


**Paradigma (se houver):** *(só se a ata trouxer; pode ser citado no laudo quando relevante)*


---

## ▶ EPIs FORNECIDOS
- Evidenciado treinamento de uso de EPI? [ ] Sim  [ ] Não
- Evidenciado controle de entrega (ficha assinada)? [ ] Sim  [ ] Não

### Fornecimento de EPIs *(uma entrega por linha — alimenta a tabela de EPI do laudo)*
*(formato: Data · Qtd · Descrição do EPI · C.A.)*
- ____ · ____ · ____ · CA ____
- ____ · ____ · ____ · CA ____
- (repetir uma linha por entrega — abaixo da divisória do imprescrito ▼)

Observações sobre os EPIs:

### EPI — RESUMO por agente `[interno]` *(pré-cálculo do Extrator — apoio à decisão do perito; o VEREDICTO de neutralização é do perito in loco)*
> Cobertura = quantidade × vida útil por CA (ver `04-EPIs/analise-epi-padrao.md`) confrontada com os meses do período imprescrito (descontados os afastamentos). Só entram agentes com EPI que protege; calor e periculosidade não têm EPI neutralizante; **biológico não é elidido por EPI**. Marcar `✓` cobre · `⚠ gap N meses` parcial · `✗` insuficiente · `[incompleto — ver ficha]` quando faltar qtd/CA/data. **Nunca dar o veredicto aqui** — é mecânico/contagem.

*(uma linha por agente — formato: Agente — EPI que protege — cobertura — Neutraliza? [perito])*
- ____ — ____ — ____ — Neutraliza? [ ]
- ____ — ____ — ____ — Neutraliza? [ ]

### NR-6 — Comprovação *(alimenta a tabela NR-6 do laudo; pré-preenchível pela skill na extração)*

> 🔄 = extrator pré-preenche (documentável) · 👤 = **perito decide in loco** (deixar em branco na extração)

*(Responsabilidade da Reclamada — marcar Sim/Não)*
- Ficha de EPI — registro do fornecimento 🔄 — [ ] Sim  [ ] Não
- Anotação do respectivo C.A. 🔄 — [ ] Sim  [ ] Não
- Treinamento e orientação 🔄 — [ ] Sim  [ ] Não
- Frequência regular de fornecimento 🔄 — [ ] Sim  [ ] Não
- Adequado ao risco ambiental 👤 (perito) — [ ] Sim  [ ] Não
- Fiscalização do uso 👤 (perito) — [ ] Sim  [ ] Não

---

## ▶ AGENTES — INSALUBRIDADE (NR-15) + PERICULOSIDADE (NR-16)
> Bloco fixo dos 13 anexos NR-15 (A–M) + Periculosidade. A Skill 1 (Extrator) copia
> VERBATIM o arquivo `_plugin-skills/01-extrator/_esqueleto-agentes.md` para a saída —
> sempre completo, mesmo agentes não alegados — e sobrepõe Status/Obs/medições só nos
> que têm base documental. Fonte única de verdade dos agentes = aquele esqueleto.

---

## ▶ ERGONOMIA (NR-17)
> **Preencher somente se a ata de audiência designar perícia ergonômica.** A análise (Biomecânica / Membros Superiores / Coluna Vertebral) vem da **planilha** `03-Ergonomia/planilha-avaliacao-ergonomica.xlsx` — este formulário fornece apenas os dados do processo e o escopo.

- Designada perícia ergonômica pela ata? [ ] Sim  [ ] Não
- Posto(s)/atividade(s) a avaliar:
- Planilha de avaliação ergonômica preenchida? [ ] Sim  [ ] Não
- Obs:

---

## ▶ DOCUMENTOS COLETADOS `[interno]`
- [ ] PPP
- [ ] Documentos ambientais (LTCAT / PGR / PPRA)
- [ ] Fichas de EPI
- [ ] Ordem de serviço
- Obs:

---

## ▶ REGISTRO FOTOGRÁFICO
*(descrever cada foto — as imagens são inseridas manualmente no laudo; estas descrições viram as legendas)*
- Foto 01:
- Foto 02:
- Foto 03:
- Foto 04:
- Foto 05:
- Foto 06:

---

## ▶ QUESITOS

### Quesitos do Juízo
*(se não houve: "Não houve.")*


### Quesitos do Reclamante
*(se não encontrado: "Não encontrado no PJE.")*


### Quesitos da Reclamada
*(se não encontrado: "Não encontrado no PJE.")*


---

## ▶ OBSERVAÇÕES GERAIS / IMPRESSÕES IN LOCO (DITADO) `[subsídio]`
> Dite no Notas do iPhone e cole o texto aqui. **Complementa** as atividades já descritas e dá a **direção** da conclusão. (A caracterização de cada agente fica no quadro de agentes; aqui é só o contexto e o porquê.)

🎙️ **Em ~1 min, diga:**
1. O que constatei in loco (o que complementa as atividades e o ambiente).
2. Divergências que pesam, se houver.
3. Para onde aponta a conclusão e por quê.

