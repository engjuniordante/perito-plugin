# Fallback MCP na mão — SÓ sem ficha de EPI em arquivo separado

> ⛔ **Pare e releia antes de usar.** Este procedimento é a **exceção estreita** descrita no fim do Passo 1B da `SKILL.md`, e ele mora fora da SKILL exatamente para não estar à mão quando algo tropeça. Ele **só** vale quando as DUAS coisas são verdade:
>
> 1. o `extrai_processo.py --doctor` deu `nlm INDISPONÍVEL` e não há conserto na hora; **e**
> 2. a pasta do processo **não tem ficha de EPI em arquivo separado** — você **listou os PDFs** e confirmou que nenhum tem `ficha`/`epi` no nome, isto é, a ficha vem embutida na contestação.
>
> Se existe arquivo de ficha, **este arquivo não se aplica**: notebook único não isola a ficha, e a Parte 3a sai plausível e errada. Nesse caso o desfecho é **PARAR** e consertar o `nlm` (26/08 e 27/08 foram exatamente isso).

## Passo a passo (uma pasta por vez)

1. `notebook_create(title="EFÊMERO — <pasta>")`.
2. Para cada PDF: `source_add(source_type="file", file_path="<caminho Windows>", wait=True, wait_timeout=300)`.
3. `notebook_get` conferindo que **todas** as fontes subiram — fonte que faltou vira parte `[NÃO LOCALIZADO]` silenciosa.
4. **Passos 2 e 3** da SKILL (ler os 5 prompts verbatim e rodá-los encadeados no mesmo `conversation_id`).
5. **Passo 5** da SKILL: apagar o notebook efêmero.
6. Mover a subpasta para `Processados/`.

## Os dois limites que mordem aqui

- ⚠ **~4,8k chars por query.** **Não** cole REGRAS+P1 juntos (estoura → `INVALID_ARGUMENT`). Rode a **P1 sozinha** e cada Parte encadeada; querendo as REGRAS, mande-as como turno de priming separado.
- ⚠ **A 3a por chat tem teto de resposta.** Confira o total de entregas contra a ficha **antes** do Passo 4 e **registre a conferência para o perito** — dizendo em qual via a ficha foi extraída, para ele saber que aquela tabela merece conferência na diligência.
