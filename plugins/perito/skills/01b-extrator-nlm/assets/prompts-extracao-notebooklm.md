# Prompts de Extração — NotebookLM (Perícia Irineu)

> **Como usar:** dividir o PDF do processo em 4 partes, subir no NotebookLM e rodar os prompts abaixo **na ordem**. Cada prompt gera um output; copiar e colar cada output na Skill 1 (Extrator) do Cowork, em sequência. São **5 outputs**: Parte 1, Parte 2, Parte 3a, Parte 3b, Parte 4.
>
> **Divisão do PDF (4 partes):** 1) Petição inicial · 2) Contestação + documentos da empresa (PPRA/PGR/PPP/laudos) · 3) Ficha de EPI · 4) Quesitos + ata de audiência.
>
> **Calibração 31/05/2026:** prompts alinhados ao `formulario-pericia.md`. Mudanças: Parte 1 entrega a tabela de identificação por função + "Autuação"; Parte 3b fecha os 6 itens NR-6 e faz pré-triagem de agentes (provisória); Parte 4 extrai o escopo e os quesitos.
>
> **Calibração 08/06/2026 (absorção dos prompts Opensquad do Junior):** (1) **TIPO de laudo agora sai do PEDIDO da Inicial** (Parte 1), não da ata — a ata vem em modelo padrão e não reflete o que foi pleiteado; (2) CNAE formatado em subclasse oficial + descrição (Parte 1); (3) afastamento como SEQUÊNCIA — último dia trabalhado/benefício/limbo/retorno, nunca férias (Parte 2); (4) janela de exposição por agente e ressalva "código interno ≠ C.A. do MTE" (Parte 3b); (5) atribuição de autoria dos quesitos por intenção (Parte 4). O **resumo de EPI por agente** e a **validação cruzada de completude** são passos Claude-side na Skill 1 (Extrator), não prompts do NLM.

---

## REGRAS GERAIS (valem para todos os prompts)

```
FONTES POR CAMPO:
- Nº processo, vara, reclamante, reclamada, autuação, data/horário/local da diligência → petição inicial e documentos da reclamante; ata de audiência e quesitos.
- CNAE, ficha de registro, função, turno, setor, período trabalhado → contestação, ficha de registro, PPP, PGR e documentos da reclamada. Se não localizado, consultar a petição inicial como fonte secundária.

DOCUMENTOS EMBUTIDOS EM OUTROS PDFs:
PPP, PGR, PPRA, LTCAT, fichas de EPI podem aparecer como ANEXOS dentro do contestacao.pdf ou de outros PDFs. NÃO concluir ausência só porque não há arquivo standalone. Procurar cabeçalhos: "Perfil Profissiográfico Previdenciário"/"PPP"/"Quadro 13.x"/"Quadro 15.x"; "PGR"/"Programa de Gerenciamento de Riscos"/"Inventário de Riscos"; "PPRA"; "LTCAT"; "Ficha de EPI"/"Ficha de Fornecimento"/"Termo de Responsabilidade". Citar a página exata onde foi localizado.

REGRA DE OURO: se um campo não for localizável após esgotar as fontes, escrever "NÃO LOCALIZADO NOS AUTOS". NÃO inferir nem inventar. EXCEÇÃO: os campos de campo (Citações/Depoimentos, Participantes, medições por agente, Fotos) vêm EM BRANCO quando não há dado nos autos — nesses, NÃO escrever "NÃO LOCALIZADO" (cada bloco traz a instrução própria).
```

---

## ━━━ PARTE 1 — Processo, empresa e vínculo ━━━
*(rodar sobre: petição inicial; complementar com contestação/PPP)*

```
Instrução de Sistema: Atue como assistente de extração de dados com 20 anos de experiência em perícias de insalubridade e periculosidade na Justiça do Trabalho.
Tarefa: Analise os autos passo a passo e preencha o template abaixo em Markdown, EXATAMENTE como estruturado. Se um campo não for localizável, escreva "NÃO LOCALIZADO NOS AUTOS". Não inferir nem inventar.

▶ PROCESSO E EMPRESA (Foco: Cabeçalhos, Inicial, Contestação e Ata/Despacho)
- Nº:
- Vara:
- Autuação (data de propositura da ação):  ← vai ao laudo E serve para calcular o período imprescrito
- Reclamante:
- Reclamada:
- CNAE da atividade principal:
  ↳ Buscar nesta ordem: (a) TRCT campo 08; (b) Ficha de Registro; (c) PPP — atividade da empresa; (d) FGTS/GFIP; (e) cabeçalho do CNPJ na Contestação.
  ↳ FORMATAR sempre como subclasse oficial `XXXX-X/XX` (restaurar o zero à esquerda) + descrição oficial. Ex.: "131800" → "0131-8/00 — Cultivo de laranja", nunca o número cru. Havendo divergência entre fontes, traga as duas formatadas + a fonte.
- Data da diligência: (buscar em despachos de agendamento/redesignação, se houver)
- Horário:
- Local:
- Data de entrega do laudo: (DATA-LIMITE para o perito TÉCNICO protocolar — buscar na ATA DE AUDIÊNCIA / despacho de nomeação. Uso INTERNO: NÃO vai ao laudo.)
  ↳ Devolva em `dd/mm/aaaa` + a redação original entre parênteses. Ex.: `29/05/2026 (ata: "prazo de 13/04/2026 a 29/05/2026")`.
  ↳ Se vier como JANELA ("prazo de X a Y"), a data-limite é a FINAL (Y), nunca a inicial. Se vier RELATIVO ("30 dias após a diligência"), devolva como veio, sem calcular.
  ⚠ A ata traz VÁRIOS prazos — pegue só o do laudo do perito TÉCNICO (insalubridade/periculosidade/engenharia). NÃO confunda com o do LAUDO PERICIAL MÉDICO, nem com impugnação, esclarecimentos, quesitos, réplica, honorários, ou a data-limite para AGENDAR a diligência. Havendo os dois, devolva o técnico e anote `[médico: dd/mm/aaaa]`.
  ⚠ Ata silente quanto ao laudo técnico → "NÃO LOCALIZADO NOS AUTOS". Não deduza de outro prazo.

▶ IDENTIFICAÇÃO / VÍNCULO — UMA LINHA POR FUNÇÃO (Foco: TRCT, Ficha de Registro, Inicial, Contestação, PPP)
Para CADA função exercida, gere uma linha na tabela abaixo:
| Função | Setor | Início | Término | Autuação | Período imprescrito |
| ------ | ----- | ------- | ------- | -------- | ------------------- |
(repita a "Autuação" e o "Período imprescrito" em todas as linhas; o "Período imprescrito" SEMPRE como intervalo fechado `dd/mm/aaaa a dd/mm/aaaa`, nunca uma data só)
- Período trabalhado (geral): de [data] até [data]
- Turno: [interno — não vai ao laudo]
  ↳ Onde buscar: (a) cartões/espelho de ponto; (b) PPP — jornada; (c) Ficha de Registro; (d) Contestação; (e) Inicial.
- Período imprescrito: SEMPRE como INTERVALO FECHADO `Período imprescrito: de dd/mm/aaaa até dd/mm/aaaa` — NUNCA uma data solta nem "todo o pacto é imprescrito" sem as duas pontas.
  - INÍCIO = a data MAIS RECENTE entre a admissão e (autuação − 5 anos). Se a admissão for posterior ao marco, o início é a admissão — ainda assim escreva as duas datas.
  - FIM = término do contrato; se ativo, a data da diligência (ou hoje, na falta).
  - Ex.: admissão 21/09/2023, autuação 17/11/2025 (−5a = 17/11/2020), rescisão 01/10/2025 → `de 21/09/2023 até 01/10/2025`.
  ⚠ Se a ata determinar avaliação de TODO o período (típico de ergonomia — ver Parte 4), use admissão até término, também fechado.

▶ TIPO DE LAUDO (FONTE CANÔNICA: o PEDIDO da PETIÇÃO INICIAL — "Dos Pedidos"/"Dos Requerimentos")
O escopo do laudo é o que foi PEDIDO, não a base documental de um agente nem o rótulo da ata.
- Localize na Inicial os pedidos de INSALUBRIDADE e/ou PERICULOSIDADE (e a causa de pedir). Cite a PÁGINA da Inicial.
- Marque uma opção: [ ] Insalubridade · [ ] Periculosidade · [ ] Insalubridade + Periculosidade · [ ] Ergonomia.
⚠ NÃO definir o tipo pela ATA DE AUDIÊNCIA nem pelo "objeto da perícia" nela rotulado — a ata vem em modelo padrão e NÃO reflete o que foi pedido; ela serve para escopo (Parte 4), quesitos e datas, jamais para o tipo.
⚠ NÃO ampliar o tipo só porque contestação/PPP/PGR menciona agente NÃO pleiteado — base documental ≠ pedido.
⚠ Sem a PETIÇÃO INICIAL entre as fontes → escrever "INICIAL não localizada — TIPO a confirmar pelo perito"; NÃO deduzir da ata/contestação.
⚠ Dúvida REAL sobre o pedido (texto ambíguo na própria Inicial) → marcar "Insalubridade + Periculosidade" + sinalizar a ambiguidade.
```

---

## ━━━ PARTE 2 — Ambiente, afastamentos, atividades, audiência ━━━
*(rodar sobre: PPP, Inicial, Contestação e Ata)*

```
Mantenha as diretrizes de perito judicial. Extraia a segunda parte, referente ao PERÍODO IMPRESCRITO (ou ao período definido na Parte 4).

FONTES: ambiente → contestação/PPP/PGR e inicial · afastamentos → ficha de registro/PPP/reclamada e inicial · atividades (reclamante) → inicial · atividades (reclamada) → contestação · citações/depoimentos/participantes → ata de audiência.

▶ DESCRIÇÃO DO AMBIENTE DE TRABALHO (marque com X a que melhor descreve os autos)
[ ] Imóvel comercial, em alvenaria, com ventilação e iluminação natural e artificial.
[ ] Fabril/industrial em alvenaria e estruturas metálicas, com ventilação e iluminação natural e artificial.
[ ] Trabalho em ambiente externo.
[ ] Outro:

▶ AFASTAMENTOS / PERÍODOS EXCLUÍDOS (Foco: Ficha de Registro, cartão/espelho de ponto, TRCT, CNIS, PPP, Defesa, Atestados)
(Somente afastamentos > 15 dias dentro do imprescrito: acidente, doença, auxílio-doença, licença, suspensão de contrato/COVID. **NUNCA contar férias.** O afastamento NÃO é uma linha única — é uma SEQUÊNCIA; extraia cada marco:)

★ DATA CRÍTICA — **Último dia efetivamente trabalhado** (é o que FECHA a exposição; data mais importante deste bloco): procure no último cartão/espelho de ponto, na data imediatamente anterior ao 1º benefício, no TRCT e no CNIS. **Esgote essas fontes antes de marcar [NÃO LOCALIZADO].**
↳ Quando houver CADEIA de benefícios SEM retorno até a rescisão, CONSOLIDE numa linha de cabeçalho: **"Último dia efetivamente trabalhado: [data]. Não houve retorno — contrato rescindido em [data]."** e detalhe os benefícios abaixo (não deixar a data crítica se perder entre os blocos).

- Último dia efetivamente trabalhado antes do afastamento: [data]
- Benefício previdenciário (espécie + datas): [data] até [data]
- Limbo previdenciário / suspensão (se o benefício cessou mas não houve retorno): [data] até [data]
- Retorno efetivo às atividades: [data]
- (repetir o bloco se houver mais de um afastamento)

▶ ATIVIDADES POR FUNÇÃO (Foco: Inicial vs Defesa e PPP)
- Descrição passo a passo (versão do Reclamante na Inicial):
- Descrição (versão da Reclamada na Contestação / divergências, se houver):

▶ CITAÇÕES / DEPOIMENTOS (Foco: Ata de Audiência)
⚠ EXCEÇÃO À REGRA DE OURO — campo de campo (o perito colhe na diligência). Se a ata for inicial / sem coleta de depoimento (ex.: "inconciliados", instrução designada para data futura), deixe os 3 campos EM BRANCO. NÃO escreva "NÃO LOCALIZADO NOS AUTOS" nem parágrafos de explicação. Só preencha se a ata efetivamente transcrever um depoimento.
- Reclamante disse:
- Reclamada disse:
- Paradigma (se houver): (pode ser citado no laudo quando relevante)

▶ PARTICIPANTES DA AUDIÊNCIA (Foco: Ata)
⚠ EXCEÇÃO À REGRA DE OURO — preencha SÓ o Reclamante (nome + "Reclamante"), depois deixe 4 blocos Nome/Papel EM BRANCO para o perito completar na diligência. NÃO escreva "NÃO LOCALIZADO" nem descrições entre parênteses (ex.: "comparecimento pessoal, acompanhado por advogado"). Formato EXATO:
Nome: [nome do reclamante]
Papel: Reclamante

Nome:
Papel:

Nome:
Papel:

Nome:
Papel:

Nome:
Papel:
```

---

## ━━━ PARTE 3a — Ficha de EPI (extração integral) ━━━
*(rodar sobre: ficha de EPI; ou anexos da contestação)*

```
CONSULTA DIRIGIDA À FICHA DE EPI — extração integral.
Consulte EXCLUSIVAMENTE o arquivo com as fichas individuais de fornecimento de EPI da Reclamante (tipicamente "ficha epi.pdf"). Ignore os demais documentos nesta consulta. Se a ficha estiver embutida no contestacao.pdf, localize a seção de anexos com as fichas e extraia delas.

ANTES DE EXTRAIR — declare a origem do documento:
▶ ORIGEM DA FICHA: [ ] PDF digital nativo (texto selecionável — alta confiança) · [ ] Imagem escaneada / manuscrita / OCR (confiança reduzida — presunção de cautela)

TAREFA: Extrair TODAS as entregas de EPI registradas, cronologicamente, sem omitir. Não restrinja ao imprescrito — extraia o histórico completo; a separação do período é feita depois.

Formato obrigatório (TABELA Markdown — NÃO prosa):
| Data de Entrega | Quantidade | Descrição do EPI | C.A. |
| :--- | :---: | :--- | :---: |
| dd/mm/aaaa | N | Descrição literal do item | NNNNN ou "C.A. não informado" |

⚠ FORMATO É OBRIGATÓRIO — NÃO ACHATE A TABELA:
- CADA entrega em UMA linha própria, começando e terminando com `|`, com os 4 campos separados por `|`.
- NUNCA junte as entregas num parágrafo corrido nem omita os `|` (datas/quantidade/descrição/C.A. grudados quebram a leitura automática).
- Ficha longa (20, 30, 40+ entregas) → mantenha a tabela mesmo assim, uma linha por entrega. NÃO resuma em texto, NÃO use "etc.", NÃO agrupe.
- Se por limite de tamanho não couber tudo, continue a MESMA tabela (novas linhas `| … |`), jamais mude para prosa.

LINHA DIVISÓRIA DO IMPRESCRITO:
- Use o marco do período imprescrito já calculado na Parte 1 (5 anos retroativos da autuação; exceções da Parte 4).
- Ordene a tabela por data e insira uma linha divisória exatamente onde o imprescrito começa:
  | ▼▼▼ INÍCIO DO PERÍODO IMPRESCRITO — dd/mm/aaaa ▼▼▼ | | | |
- Tudo ACIMA dela = histórico anterior (registro). Tudo ABAIXO = período relevante.

REGRAS:
- Uma linha por entrega (uma data + um item = uma linha). Mesma data com 5 itens = 5 linhas.
- CÉLULA DE DATA COM DUAS DATAS = UMA ENTREGA SÓ. Quando a coluna DATA traz um período (ex.: "19/4/21 á 24/4/21" — entrega e troca), transcreva APENAS a data inicial e mantenha a quantidade que está ao lado, uma única vez. Transcrever cada extremo como uma entrega DOBRA o total de entregas e de unidades (caso real: 11 linhas e 63 unidades viraram 22 e 126, e o número dobrado chegou ao laudo).
- QUANTIDADE: transcreva o número exatamente como está escrito na ficha. Atenção: "1,000" é UMA unidade com três casas decimais, NÃO mil — ler como milhar multiplica por mil a cobertura daquele EPI.
- Transcreva o C.A. se registrado; senão "C.A. não informado". NUNCA inventar nem completar valor provável.
- PROIBIDO PREENCHER POR INFERÊNCIA: se C.A., data ou descrição estiverem ilegíveis (manuscrito, escaneamento ruim, campo cortado, rasura), NÃO complete com o valor mais plausível. Transcreva literalmente o que está visível entre colchetes, ex: C.A. [3?41], data 1[2/?]/2023.
- Mantenha a grafia original do item.
- Ao final: "▶ EVIDÊNCIA DE ASSINATURA: Sim — confirmado nas fichas" ou "Não — fichas sem assinatura visível".
- Se a ficha existe como fonte mas não foi possível extrair: escrever "FICHA EPI EXISTE COMO FONTE MAS NÃO INDEXADA — solicitar reupload no NotebookLM" e parar.

▶ CONFERÊNCIA OBRIGATÓRIA NA FICHA ORIGINAL (preencher só com os itens duvidosos):
Liste todo campo que NÃO foi transcrito com 100% de certeza, para o perito conferir contra a ficha física/PDF. Formato:
- [linha/data] — campo [C.A./data/descrição] — lido como [...]
Se não houver nenhum: escreva "Todos os campos transcritos com alta confiança."

NÃO faça análise crítica aqui — apenas a tabela, a linha divisória, a evidência de assinatura e a conferência obrigatória.
```

---

## ━━━ PARTE 3b — Análise crítica, NR-6 e pré-triagem de agentes ━━━
*(rodar sobre: contestação + anexos ambientais)*

```
CONSULTA DIRIGIDA À CONTESTAÇÃO + ANEXOS — análise crítica.
A tabela de EPI já foi extraída (Parte 3a). Aqui cruze A Prática (fichas) com A Norma (defesa, PPP, PGR, PPRA). Atue como Auditor. Procure PPP/PGR/PPRA/LTCAT embutidos (ver Regras Gerais) e cite a página.

▶ EVIDÊNCIAS DOCUMENTAIS
- Treinamento de uso de EPI evidenciado? [ ] Sim [ ] Não — indique página/documento.
- Controle de entrega (ficha assinada) evidenciado? [ ] Sim [ ] Não — referir-se à tabela da Parte 3a.

▶ NEUTRALIZAÇÃO POR AGENTE (relação Agente × EPI)
- Físicos (ruído/calor/etc): o EPI correto foi entregue? A quantidade faz sentido para o período?
- Químicos (óleos/poeira/etc): idem.
- Biológicos: avaliar se aplicável.

▶ FALHAS DOCUMENTAIS
1. Omissão de C.A.: quantos itens da tabela sem C.A.?
2. Assinaturas: há controle com assinatura do Reclamante? Rasuras?
3. Divergências: EPIs citados em PPRA/PPP/Contestação NÃO entregues nas fichas? E o inverso?
4. Lacunas temporais: períodos do imprescrito sem qualquer entrega registrada?
5. Riscos do PGR/PPP para a função (em tabela; citar página se embutido).

▶ STATUS DOS DOCUMENTOS AMBIENTAIS (PPP / PGR / PPRA / LTCAT) — marque para cada um:
[ ] Juntado como arquivo separado (citar nome) · [ ] Embutido em outro PDF (citar PDF+página) · [ ] Citado mas não juntado · [ ] Totalmente ausente

▶ NR-6 — COMPROVAÇÃO (pré-preencha SÓ as 4 linhas documentáveis 🔄; sem evidência = NÃO. As 2 linhas 👤 são **juízo do perito in loco** — deixe EM BRANCO)
| Responsabilidade da Reclamada | SIM | NÃO |
| Ficha de EPI — registro do fornecimento 🔄 | [ ] | [ ] |
| Anotação do respectivo C.A. 🔄 (só entre EPI certificável; **código interno ≠ C.A. do MTE**) | [ ] | [ ] |
| Treinamento e orientação 🔄 | [ ] | [ ] |
| Frequência regular de fornecimento 🔄 | [ ] | [ ] |
| Adequado ao risco ambiental — agentes insalubres 👤 (perito) | [ ] | [ ] |
| Fiscalização do uso 👤 (perito) | [ ] | [ ] |

▶ PRÉ-TRIAGEM DE AGENTES (PROVISÓRIA — conforme PPP/PGR/PPRA/Inicial)
⚠ Provisório: a caracterização final é feita pelo perito na diligência. Regra:
- SE houver base documental para o agente → marque "[Presente — fonte: ___, pág. ___]" e traga o valor/medição citado, se houver.
- SE NÃO houver base documental → escreva "— avaliar in loco" (NÃO inferir, NÃO marcar).
- Para cada agente PRESENTE, indicar a JANELA de exposição (função/sub-período em que ocorre), não o contrato inteiro.
⚠ **Poeira/particulado → Anexo 12** (poeiras minerais), NÃO Anexo 11. O Anexo 11 é gases/vapores e químicos com LT quantitativo específico. Não jogar poeira no An.11.
Agentes NR-15: Ruído (An.1/2) · Calor (An.3) · Radiações ionizantes (An.5) · Hiperbáricas (An.6) · Radiações não ionizantes (An.7) · Vibrações (An.8) · Frio (An.9) · Umidade (An.10) · Químicos quantitativos (An.11) · Poeiras minerais (An.12) · Químicos qualitativos/dérmico (An.13) · Benzeno (An.13A) · Biológicos (An.14).
Periculosidade (NR-16): há base documental? Qual anexo (1 Explosivos / 2 Inflamáveis / 3 Violência / 4 Energia elétrica / 5 Motocicleta / * Radiações)?
```

---

## ━━━ PARTE 4 — Objeto da perícia, escopo e quesitos ━━━
*(rodar sobre: ata de audiência + despacho de nomeação + quesitos)*

```
FONTES: objeto/escopo e quesitos do Juízo → ata de audiência e despacho de nomeação · quesitos do Reclamante → ata/quesitos; senão inicial · quesitos da Reclamada → ata/quesitos; senão contestação.

▶ TIPO DE LAUDO — extraído na PARTE 1 (pedido da Inicial), NÃO aqui.
A ata vem em modelo padrão ("nomeio o perito para perícia de insalubridade/periculosidade") e não define o tipo. Aqui só confirma o ESCOPO e os quesitos.

▶ ESCOPO DA AVALIAÇÃO (Foco: ata)
[ ] Todo o período laboral  [ ] Somente o período imprescrito (5 anos da autuação)
- Se a ata for expressa, seguir a ata (transcrever a determinação + página).
- Se a ata for silente: ergonomia → todo o período; insalubridade/periculosidade → período imprescrito.

ATRIBUIÇÃO DE AUTORIA DOS QUESITOS — não confie no rótulo do arquivo (um doc "quesitos" pode trazer os de uma só parte). Decida de QUEM é cada bloco pela INTENÇÃO (árbitro final), com a autoria como reforço:
- INTENÇÃO (decisivo): quesito do RECLAMANTE pergunta o que CONSTRÓI a insalubridade/periculosidade (exige medição, exposição, agentes, falha de EPI). Quesito da RECLAMADA pergunta o que DESMONTA ou presume que o EPI funcionou — tom cético/ônus-invertido ("apresentar documentação que comprove", "o autor recebeu/usou os EPIs em quantidade adequada").
- AUTORIA (reforço): timbre de assistente técnico de SST/ergonomia (ex.: "WES Ergonomia & Saúde Ocupacional") normalmente é da RECLAMADA; petição do advogado do autor é do RECLAMANTE. Autoria × intenção em conflito → vale a INTENÇÃO.
- Dúvida residual → marcar "[autoria provável: ___ — confirmar]" em vez de atribuir errado.

REGRA DE ESCOPO DOS QUESITOS — POR BLOCO (não quesito a quesito): a decisão é do BLOCO inteiro. NÃO avaliar quesito por quesito.
- Bloco de perícia MÉDICA/ergonômica (pelo rótulo/orientação, ex.: "Quesitos do Juízo – Perícia Médica") → NÃO transcrever nada; escrever só: "Bloco de perícia médica — não pertinente ao perito técnico."
- Bloco técnico (insalubridade/periculosidade) ou genérico/sem rótulo → transcrever o bloco INTEIRO, com a numeração original.
- Reclamada com dois blocos separados ("Quesitos de Insalubridade" + "Quesitos Médicos") → transcrever integralmente o de insalubridade; do médico, só a linha-resumo.

▶ QUESITOS DO JUÍZO  (se nada: "Não localizado")
▶ QUESITOS DO RECLAMANTE  (se nada: "Não localizado no PJE")
▶ QUESITOS DA RECLAMADA  (se nada: "Não localizado no PJE")
```

---

## Prompt de Impugnação (NLM: laudo + impugnação → minuta de esclarecimentos)

> **Fontes no NLM:** subir o **laudo pericial original** + a **petição de impugnação/esclarecimentos** da parte. Rodar o prompt abaixo. O output é colado na Skill 4 do Cowork, que formata no template .docx.
>
> **Calibração 02/06/2026:** identidade do Irineu preenchida. Formato de resposta alinhado ao padrão real ("**Resposta:**", não "R."). Fecho = "Pelo exposto, espero ter eliminado..." + "ratifico a conclusão do laudo pericial."

```
Instrução de Sistema: Atue como o Engenheiro Perito Judicial Irineu Branco Junior.

Tarefa: Analise a "Petição de Impugnação/Esclarecimentos" apresentada pelas partes e o meu "Laudo Pericial" original anexado nestas fontes. Redija a petição de Esclarecimentos Periciais seguindo ESTRITAMENTE o meu estilo de escrita em tom humanizado e o template abaixo separando o que for impugnação de Reclamante do que for impugnação de Reclamada. Haverá situações de ter as duas ou apenas uma das partes.

Regras de Redação (Obrigatórias):
1. Tom de voz: Técnico, objetivo, polido, focado puramente nas Normas Regulamentadoras (NRs) e na metodologia pericial. IGNORE argumentações puramente jurídicas ou jurisprudências citadas por advogados.
2. Argumentação em Texto: Se a impugnação for um texto argumentativo, crie um ou dois parágrafos iniciais rebatendo tecnicamente a alegação, usando a fundamentação que já está no Laudo Original.
3. Resposta aos Quesitos: Se houver perguntas diretas (quesitos suplementares), responda-as uma a uma. Inicie SEMPRE as respostas com "Resposta:" em negrito, seguido de remissão ao laudo com expressões como: "Conforme já descrito no laudo pericial...", "Conforme avaliado in loco...", ou "Sim, porém...".
4. NÃO invente dados. Use apenas os dados de medição, avaliação e inspeção que constam no meu Laudo original.

Extraia do processo e preencha estes campos no início do output (a Skill 4 do Cowork usará para montar o .docx):
- CIDADE_VARA: [cidade da Vara do Trabalho]
- NUMERO_PROCESSO: [número completo do processo]
- NOME_RECLAMANTE: [nome do reclamante em MAIÚSCULAS]
- NOME_RECLAMADA: [nome da reclamada em MAIÚSCULAS]
- IMPUGNANTES: [parte(s) impugnante(s) com o Id. de cada uma, no formato "Parte (Id. xxx)". UMA parte: "Reclamada (Id. abc123)". AS DUAS (quando ambas impugnaram): "Reclamante (Id. abc); Reclamada (Id. xyz)". Id. não encontrado → "Parte (Id. NÃO LOCALIZADO)"]

Depois dos campos, redija o conteúdo dos esclarecimentos no formato abaixo. Se AMBAS as partes impugnaram, repita o bloco "ESCLARECIMENTOS SOLICITADOS PELA …" uma vez para cada parte (um para o RECLAMANTE e outro para a RECLAMADA, na ordem); se só uma impugnou, apenas o bloco dela:

---
ESCLARECIMENTOS SOLICITADOS PELA [RECLAMADA / RECLAMANTE]

[Se a parte apresentou texto discordante antes dos quesitos, redija aqui os parágrafos de fundamentação técnica rebatendo a parte com base no laudo. Se não houver, pule direto para os quesitos.]

1- [Texto da pergunta da parte]
Resposta: [Resposta técnica baseada no laudo, iniciando com "Conforme descrito no laudo..." ou similar]

2- [Texto da pergunta da parte]
Resposta: [Resposta técnica baseada no laudo]

[continuar para todos os quesitos]

[quando AMBAS impugnaram, repita aqui o bloco "ESCLARECIMENTOS SOLICITADOS PELA <a outra parte>" com os quesitos dela]

Pelo exposto, espero ter eliminado quaisquer dúvidas remanescentes, concluindo assim, que o laudo está baseado em dados colhidos "in loco", demonstrando a veracidade dos fatos que se encontram documentados.
Em razão de todo o exposto, ratifico a conclusão do laudo pericial.
---
```
