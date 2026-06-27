# Manual do Plugin Perito — passo a passo

Guia bem simples, do começo ao fim. Faça uma coisa de cada vez, de cima para baixo.

Você fala com o programa **escrevendo frases normais**, como numa conversa.
Não precisa decorar nada. É só pedir o que você quer.

**Índice**
- [O que esse ajudante faz](#o-que-esse-ajudante-faz)
- [Parte 1 — Instalar (uma vez só)](#parte-1--instalar-uma-vez-só)
- [Parte 2 — Dizer quem você é (uma vez só)](#parte-2--dizer-quem-você-é-uma-vez-só)
- [Parte 3 — As ferramentas, uma por uma](#parte-3--as-ferramentas-uma-por-uma)
- [Parte 4 — Ensine o ajudante a trabalhar do seu jeito](#parte-4--ensine-o-ajudante-a-trabalhar-do-seu-jeito)
- [As 5 regras que nunca mudam](#as-5-regras-que-nunca-mudam)
- [Se der algum problema](#se-der-algum-problema)

---

## O que esse ajudante faz?

Pense nele como um **ajudante** que monta o rascunho dos seus laudos.

1. Você dá os papéis do processo pra ele.
2. Ele monta um **rascunho** do laudo no Word, do seu jeito.
3. **Você lê, conserta o que quiser, assina e manda no PJE.**

O ajudante **nunca** manda nada sozinho. Quem assina e envia é **sempre você**.

---

## Parte 1 — Instalar e configurar (o Junior já fez por você)

A instalação e a primeira configuração **já estão prontas** — o Junior deixou tudo no jeito
no seu computador. **Você não precisa fazer nada aqui.** Pode ir direto para a Parte 3.

<details>
<summary>Só por referência (se um dia precisar reinstalar) — clique para abrir</summary>

Abra o programa (Claude Code ou Cowork) e escreva, **uma linha de cada vez**:

```
/plugin marketplace add engjuniordante/perito-plugin
/plugin install perito@perito-jr
```

Depois, **uma vez**, escreva **configurar plugin** e responda:
- o seu **nome** e o seu **CREA**;
- a sua **cidade**;
- o seu **e-mail** (é pra onde vão os avisos de prazo);
- **onde ficam** a sua base de laudos, os seus modelos do Word e a sua planilha de prazos.

</details>

---

## Parte 2 — Se algo mudar

Se um dia mudar alguma coisa — **e-mail**, uma **pasta**, ou os seus dados — escreva:

> **mudar configuração**

e ajeite ali na hora. Fora isso, não precisa mexer.

---

## Parte 3 — As ferramentas, uma por uma

O ajudante tem **8 ferramentas**. Você não escolhe pelo nome — só **descreve o que quer**
ou **cola o material**, e ele usa a ferramenta certa sozinho. Aqui vai cada uma.

---

### 1. Montar o formulário de campo

**O que faz:** junta os papéis do processo num **formulário** pra você levar na visita.

**Como usar:**
1. Passe o processo no **NotebookLM**. Ele te devolve
   **5 pedaços de texto** (Partes 1, 2, 3a, 3b e 4).
2. **Cole os 5 pedaços** aqui na conversa.
3. Escreva: **montar o formulário de campo**

Ele monta o formulário. Onde faltar informação nos autos, ele escreve **[NÃO LOCALIZADO]** —
quer dizer "isso você vê na hora, na empresa". Ele **nunca inventa**.

> Depois disso você vai na empresa, olha, mede e preenche à mão o que faltou. Essa parte é sua. 😄

---

### 2. Gerar o laudo de insalubridade ou periculosidade

**O que faz:** monta o laudo no **Word**, do seu jeito, com a vara certa do processo.

**Como usar:**
1. Volte da visita com o formulário preenchido.
2. **Cole o formulário** aqui na conversa.
   *(Se tiver um laudo parecido já pronto, cole junto — ele copia o seu estilo dele.)*
3. Escreva: **gerar o laudo de insalubridade**
   *(ou "gerar o laudo de periculosidade")*

O laudo sai pronto em Word, na pasta de saída. Aí é só conferir e assinar.

---

### 3. Gerar o laudo ergonômico

**O que faz:** monta o laudo de ergonomia (NR-17) no Word, usando a sua planilha de avaliação.

⚠️ **A planilha tem várias abas — então ela não se cola, ela se salva numa pasta.**

**Como usar:**
1. Preencha a sua planilha de ergonomia do caso (copie o molde de `03-Ergonomia`,
   preencha e **salve em `03-Ergonomia/casos/`** — nome livre, ex.: "Fulano ergonomia.xlsx").
2. **Cole só o formulário** de campo aqui na conversa.
3. Escreva: **gerar o laudo ergonômico**

O ajudante acha a planilha sozinho na pasta `casos/`. Se tiver mais de uma lá, ele pergunta
qual é a deste caso. A planilha é quem calcula as notas; o ajudante só **copia** pro Word —
nunca recalcula nada.

---

### 4. Responder uma impugnação

**O que faz:** pega a resposta que o NotebookLM já escreveu e **arruma a aparência** no seu modelo.

**Como usar:**
1. Primeiro o **NotebookLM** escreve a resposta pra você.
2. **Cole essa resposta** aqui na conversa.
3. Escreva: **responder impugnação**

Ele só ajeita a forma; **não muda o que você escreveu**.

> Se você escrever isso **sem colar** a resposta, ele para e pede. É normal.

---

### 5. Guardar uma correção rápida (texto **ou** EPI)

**O que faz:** quando você conserta uma coisinha, ele **lembra** disso pra sempre. Serve para
duas coisas:

**a) Corrigir um texto do laudo**
1. **Cole o pedaço corrigido** aqui.
2. Escreva: **salvar essa correção**

Ele guarda só aquele pedaço, sem mexer no resto.

**b) Acertar a classificação de um EPI (pelo C.A.)** — *esta é importante e é o que deixa o
ajudante esperto com EPI.* Ele guarda o C.A., não o nome comercial — então uma vez corrigido,
**nunca mais erra naquele C.A.**

- **Classificou no agente errado?** Escreva, com suas palavras:
  > **o CA 35339 é químico, não solar**
  *(ou "classifiquei errado esse EPI", "cataloga esse CA")*

- **Quer registrar a vida útil de um C.A.?** (a vida útil **nunca** vem da base do governo —
  só você tem ela, do boletim do C.A.). Escreva:
  > **cataloga a vida útil do CA 35339: 12 meses**
  *(ou "CA 35339 vida útil 12 meses")*
  
  > 💡 Sem a vida útil cadastrada, o ajudante não consegue calcular se o EPI cobria o período
  > todo. Vale cadastrar sempre que tiver o boletim do C.A. na mão.

---

### 6. Ensinar o ajudante com laudos antigos

**O que faz:** lê seus laudos antigos e aprende o seu jeito de escrever. Quanto mais ele
conhece, melhor ele monta os próximos.

⚠️ **Atenção — esta é a única que pede um preparo:** o ajudante só lê laudo no formato
**`.md`** (um tipo de texto simples). Então, **antes**:

1. Se o laudo antigo for **PDF**, abra o site **https://www.pdftomarkdown.net/**
2. Jogue o PDF lá e baixe o arquivo **`.md`** que ele te dá.
3. Salve esse `.md` dentro da pasta **`09-Inbox`**.

*(Laudo que já está em `.md` é só salvar na `09-Inbox`, sem converter.)*

**Como usar (depois de salvar os `.md` na pasta):**
- Escreva: **povoar a base**

Ele lê os laudos, aprende e **te mostra o que vai guardar antes de salvar**. Nunca guarda
nada escondido.

---

### 7. Ver os prazos da semana

**O que faz:** olha a sua planilha de perícias e mostra o que está chegando nos próximos
15 dias — diligências, laudos a entregar, impugnações a responder, e os atrasados em destaque.

**Como usar:**
- Escreva: **prazos** *(ou "o que vence essa semana")*

Ele lê a planilha na hora e te mostra o planejamento aqui na conversa. **Só olha, nunca
escreve** na planilha.

> ⚠️ **Antes de confiar nela:** ela precisa ser testada na sua planilha de verdade. Eu
> (Junior) vou conferir com você os nomes das colunas e o caminho do arquivo num teste
> rápido ("rodar o alerta agora"). Até a gente validar, continue conferindo os prazos no PJE.

---

### 8. Configurar

**O que faz:** guarda quem é você e onde estão as suas pastas. **O Junior já deixou isso
pronto** (Parte 1). Só mexa aqui — escrevendo **mudar configuração** — se algo mudar.

---

## Parte 4 — Ensine o ajudante a trabalhar do seu jeito

O ajudante **aprende com você**. Quanto mais você o ensina, mais os laudos saem com a sua
cara — e você não precisa pedir nada pra ninguém. Tem dois jeitos de ensinar:

**1. Consertou e quer que ele lembre (na hora):**
Achou que ele escreveu algo que não é bem o seu jeito? Conserte no Word, **cole o pedaço
do jeito certo** aqui e escreva:

> **salvar essa correção**

Da próxima vez, ele já escreve do jeito que você ensinou.

**2. Ensinar bastante de uma vez (com laudos antigos):**
Quer que ele aprenda o seu estilo de montão? Junte vários laudos seus antigos (em `.md`,
na pasta `09-Inbox` — veja a ferramenta 6) e escreva:

> **povoar a base**

Ele lê tudo, aprende o seu jeito e **te mostra antes de guardar**.

> 💡 Pense assim: o ajudante começa bom e vai ficando **com a sua cara** conforme você usa.
> Cada correção que você ensina vale pra sempre, sozinha.

E se um dia você pedir algo que ele **ainda não sabe fazer**, ele é sincero e te avisa —
não promete o que não consegue.

---

## As 5 regras que nunca mudam

1. **Quem assina é você.** Sempre.
2. **Quem manda no PJE é você.** O ajudante nunca manda.
3. **O honorário você coloca à mão.** O ajudante não mexe nisso.
4. **Ele não inventa.** Se está escrito [NÃO LOCALIZADO], é você que preenche.
5. **A vara é a do processo.** Sempre a do caso.

---

## Se der algum problema

- **Apareceu "plugin não configurado"** → escreva **mudar configuração** (ou me avise — eu já deixei isso pronto).
- **O laudo saiu com nome ou cidade errados** → escreva **mudar configuração** e confira;
  se continuar, me avise.
- **A impugnação não fez nada** → você esqueceu de **colar a resposta** antes.
- **O ajudante não achou os laudos antigos** → confira se estão em `.md` na pasta `09-Inbox`.

---

*Travou em alguma coisa? Me chame (Junior). É pra isso que estou aqui.*
