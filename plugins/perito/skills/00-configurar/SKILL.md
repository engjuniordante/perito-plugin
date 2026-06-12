---
name: perito-configurar
description: Use na PRIMEIRA vez que o perito usa o plugin, ou quando disser "configurar", "configurar plugin", "setup inicial", "mudar configuração", "trocar e-mail/base/planilha/identidade". Cria ou atualiza o perito-config.json na raiz da pasta do projeto — identidade do perito (nome, CREA, cidade) + caminhos (base de conhecimento, templates, planilha de agendamento, pasta de saída) + e-mail dos alertas. Todas as outras skills leem esse arquivo; sem ele, elas pedem para rodar esta.
---

# Configurar — perfil do perito (`perito-config.json`)

Cria o **perfil persistente** do perito na raiz da pasta do projeto. Roda **uma vez** (ou
quando algo mudar). Todas as demais skills do plugin leem este arquivo para saber **quem é
o perito** e **onde estão** a base de conhecimento, os templates, a planilha de agendamento
e a pasta de saída dos laudos.

Schema completo e padrão de leitura: **`_plugin-skills/_perito-config.md`** (referência
canônica — ler antes).

## Onde gravar (CRÍTICO)

`perito-config.json` na **RAIZ da pasta do projeto conectada** — **nunca** no diretório
temporário do sandbox (esse apaga ao fim da sessão, junto com os pacotes `pip`). A raiz do
projeto persiste entre sessões via a pasta conectada no Cowork.

## Fluxo

1. **Procurar** `perito-config.json` na raiz do projeto.
2. **Existe** → mostrar um resumo legível (nome, CREA, cidade, caminhos, e-mail) e
   perguntar: *"Manter assim ou alterar algum campo?"* Alterar só o que o perito pedir;
   reescrever o JSON inteiro preservando o resto.
3. **Não existe** → fazer as perguntas abaixo e gravar o JSON.

## Perguntas (ao criar / editar)

Identidade:
- Nome completo do perito
- Registro CREA (ex.: `CREA-SP 5061052933`)
- Cidade-base

Caminhos (relativos à raiz do projeto — confira que existem na pasta):
- Pasta da **base de conhecimento** (onde estão `08-Textos-Padrao/`, `04-EPIs/`, etc.; use
  `.` se o projeto já é a própria base)
- Pasta dos **templates** `.docx` (ex.: `00-Template`)
- Nome/caminho da **planilha de agendamento** `.xlsx` (a que a Skill 7 lê)
- Pasta de **saída dos laudos** (ex.: `Laudos-Gerados`)

Alertas:
- **E-mail** para o planejamento de prazos (Skill 7)

## Gravar

- Montar o JSON no schema de `_perito-config.md`, **UTF-8, indentado**.
- Gravar em `perito-config.json` na **raiz do projeto**.
- **Validar** que os caminhos informados existem na pasta do projeto; se algum não for
  encontrado, gravar mesmo assim mas **avisar** qual caminho não foi localizado (o perito
  confere/cria a pasta).

## Relatório final

```
## ✅ PERFIL CONFIGURADO
Perito: [nome] · [CREA] · [cidade-base]
Base de conhecimento: [caminho]  [✓ encontrada / ⚠ não localizada]
Templates: [caminho]             [✓ / ⚠]
Planilha de agendamento: [caminho] [✓ / ⚠]
Saída dos laudos: [caminho]
E-mail dos alertas: [email]

Arquivo gravado: perito-config.json (raiz do projeto — persiste entre sessões).
As demais skills (laudo, ergonômico, impugnação, alertas) já vão usar este perfil.
```

> **Onboarding de perito novo (mentoria):** além de rodar esta skill, é preciso ter a
> **base de conhecimento dele** (textos-padrão, paradigmas) e os **templates `.docx` dele
> marcados no padrão do plugin** (`{{VARA}}`, `{{ANALISE_*}}`, …) dentro da pasta do
> projeto. Sem isso, os Redatores não têm o que ler. A marcação dos templates é trabalho de
> mentoria, feito uma vez por perito.
