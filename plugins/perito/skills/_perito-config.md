# perito-config.json — perfil do perito (referência canônica do plugin)

Documento de referência **compartilhado** por todas as skills do plugin. Define o
schema do `perito-config.json` e o padrão "ler config / se não existir, configurar".

## O que é

Arquivo único, gravado na **RAIZ da pasta do projeto conectada**, que guarda **quem é
o perito** e **onde estão** a base de conhecimento, os templates, a planilha de
agendamento e a pasta de saída. É o que torna o plugin **reutilizável por qualquer
perito**: a identidade e os caminhos saem daqui, não ficam fixos no código das skills.

> ⚠️ **Onde gravar (crítico):** na **raiz da pasta do projeto** (a pasta que o usuário
> conecta no Cowork) — **nunca** no diretório de trabalho temporário do sandbox. A pasta
> do projeto persiste entre sessões; o sandbox é efêmero (apaga ao encerrar, junto com os
> pacotes `pip`). Gravar no lugar errado = config perdido a cada sessão.

## Schema

```json
{
  "perito": {
    "nome": "Nome Completo do Perito",
    "crea": "CREA-SP 0000000000",
    "cidade_base": "Cidade"
  },
  "caminhos": {
    "base_conhecimento": ".",
    "templates": "00-Template",
    "planilha_agendamento": "2026 - PLANEJAMENTO PERÍCIAS.xlsx",
    "saida_laudos": "Laudos-Gerados",
    "formularios_campo": "Formularios-Campo"
  },
  "email_alertas": "perito@exemplo.com"
}
```

**Campos:**
- `perito.nome` / `perito.crea` / `perito.cidade_base` — identidade. Substitui o "sempre
  Irineu" das travas de identidade: a skill usa `perito.nome` do config como o nome do
  perito do laudo (nunca o dono da máquina / usuário do Cowork).
- `perito.nomes_proibidos` *(opcional, lista)* — nomes que **nunca** podem aparecer como
  perito (ex.: o dono da máquina, em ambiente de teste). Os scripts `build_*.py` avisam
  `VAZAMENTO` se algum aparecer no documento. Ausente/vazio = sem checagem extra (caso do
  Irineu).
- `caminhos.*` — **relativos à raiz do projeto** (não usar `C:\...`: o sandbox enxerga o
  projeto montado, não o disco do Windows). `base_conhecimento` = pasta com `08-Textos-Padrao/`,
  `04-EPIs/`, etc. (`"."` quando o projeto já é a própria base). `templates` = pasta dos
  `.docx`. `planilha_agendamento` = a planilha que a Skill 7 lê. `saida_laudos` = onde os
  `.docx` gerados são gravados. `formularios_campo` = pasta onde o **Extrator** grava o
  formulário de campo `.md` (insumo da diligência); separada dos laudos finais. Ausente no
  config (perfis antigos) → o Extrator usa o default `Formularios-Campo`.
- `email_alertas` — destinatário do planejamento de prazos (Skill 7).

## Padrão "ler config / se não existir, configurar" (toda skill, no início)

1. Procurar `perito-config.json` na **raiz da pasta do projeto**.
2. **Existe** → carregar. Usar `perito.nome`/`crea`/`cidade_base` como identidade e
   `caminhos.*` para localizar base, templates, planilha e saída. Seguir.
3. **Não existe** → **parar** e instruir: *"Plugin ainda não configurado. Rode `/configurar`
   uma vez para criar o seu perfil (identidade + caminhos)."* Não chutar caminhos nem
   identidade.

> A identidade do perito **vem sempre do config** — as travas antigas ("perito = sempre
> Irineu") passam a significar "perito = `perito.nome` do config, nunca o usuário/dono da
> máquina". A **vara** continua vindo do **formulário** (a do processo), não do config.

## Execução dos scripts (Windows × Mac) — vale para TODAS as skills

Os comandos das skills usam `python3`. **No Windows**, se `python3` não existir no
terminal (Git Bash), usar **`python`** (ou `py -3`) — mesmo script, mesmos argumentos.
Piso: **Python 3.9+** (os scripts abortam com mensagem clara abaixo disso).
