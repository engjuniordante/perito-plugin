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

## Parte 1 — Instalar (uma vez só)

Abra o programa (Claude Code ou Cowork). Escreva estas duas linhas, **uma de cada vez**,
apertando Enter depois de cada:

```
/plugin marketplace add engjuniordante/perito-plugin
/plugin install perito@perito-jr
```

Pronto, está instalado. Você só faz isso uma vez.

---

## Parte 2 — Dizer quem você é (uma vez só)

Antes de usar, o ajudante precisa saber **quem é você** e **onde estão as suas pastas**.

Escreva:

> **configurar plugin**

Ele vai te perguntar:
- o seu **nome** e o seu **CREA**;
- a sua **cidade**;
- **onde ficam** a sua base de laudos, os seus modelos do Word e a sua planilha de prazos.

Responda e pronto. **Você só faz isso uma vez.**
Se um dia mudar alguma coisa (e-mail, uma pasta), escreva **mudar configuração** e ajeite.

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

**Como usar:**
1. **Cole o formulário** de campo **junto** com a sua **planilha de ergonomia** preenchida.
2. Escreva: **gerar o laudo ergonômico**

A planilha é quem calcula as notas; o ajudante só **copia** pro Word. Ele nunca recalcula nada.

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

### 5. Guardar uma correção rápida

**O que faz:** quando você conserta uma coisinha num laudo, ele **lembra** disso pra próxima vez.

**Como usar:**
1. **Cole o pedaço corrigido** aqui.
2. Escreva: **salvar essa correção**

Ele guarda só aquele pedaço, sem mexer no resto.

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

**O que faz:** olha a sua planilha de perícias e mostra o que está chegando.

**Como usar:**
- Escreva: **prazos** *(ou "o que vence essa semana")*

Ele **só olha, nunca escreve** na planilha.

> ⚠️ Essa ferramenta **ainda precisa ser testada na sua planilha de verdade.**
> Antes de confiar nela, faça um teste comigo (Junior) junto.

---

### 8. Configurar (você já viu na Parte 2)

**O que faz:** guarda quem é você e onde estão as suas pastas. É a primeira coisa que você
fez. Só volta aqui (escrevendo **mudar configuração**) se algo mudar.

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

- **Apareceu "plugin não configurado"** → escreva **configurar plugin** (Parte 2).
- **O laudo saiu com nome ou cidade errados** → escreva **mudar configuração** e confira;
  se continuar, me avise.
- **A impugnação não fez nada** → você esqueceu de **colar a resposta** antes.
- **O ajudante não achou os laudos antigos** → confira se estão em `.md` na pasta `09-Inbox`.

---

*Travou em alguma coisa? Me chame (Junior). É pra isso que estou aqui.*
