# RPA4ALL Test Mass Autofill (Chrome + Firefox)

Extensao WebExtension para consultar massa de testes no ambiente RPA4ALL e preencher formularios automaticamente, incluindo `https://www.rpa4all.com/marketing-studio.html`.

## Recursos

- Busca registros de massa de teste por endpoint configuravel.
- Fallback para massa local (`sample-masses.json`).
- Preenchimento com:
  - mapeamento explicito para campos do Marketing Studio
  - mapeamento generico por `id`, `name`, `label`, `placeholder` e `aria-label`.

## Estrutura

- `manifest.json`: configuracao da extensao (MV3)
- `autofill-core.js`: heuristica compartilhada de preenchimento
- `background.js`: consulta API e cache local
- `content-script.js`: preenche os formularios da pagina
- `popup.*`: interface de uso rapido
- `options.*`: configuracao de endpoint e token
- `sample-masses.json`: massa local de exemplo

## Instalar no Chrome

1. Abra `chrome://extensions`.
2. Ative `Developer mode`.
3. Clique em `Load unpacked`.
4. Selecione a pasta:
   - `tools/rpa4all-form-autofill-extension`

## Instalar no Firefox

1. Abra `about:debugging#/runtime/this-firefox`.
2. Clique em `Load Temporary Add-on`.
3. Selecione o arquivo:
   - `tools/rpa4all-form-autofill-extension/manifest.json`

## Configuracao da API

Na pagina de opcoes da extensao, ajuste:

- `Base URL da API`: exemplo `https://api.rpa4all.com/agents-api`
- `Path do endpoint`: exemplo `/marketing/test-masses`
- `Query padrao`: opcional, por exemplo `form=marketing-studio&env=qa`
- `Bearer token`: opcional, quando endpoint exigir autenticacao

## Formato esperado do endpoint

A extensao aceita estes formatos:

1. `{ "records": [{"id":"...","label":"...","data": {...}}] }`
2. `{ "items": [...] }`
3. `[{...}, {...}]`
4. `{ "data": [...] }` ou `{ "data": {...} }`

Cada registro vira um item do seletor no popup.

## Uso rapido

1. Abra a pagina alvo (ex.: Marketing Studio).
2. Abra o popup da extensao.
3. Clique em `Carregar massa (API)` ou `Usar massa local`.
4. Escolha o registro.
5. Clique em `Preencher pagina atual`.

## QA local

Para validar a heuristica de preenchimento sem depender do ambiente externo:

1. Habilite `Allow access to file URLs` na extensao carregada.
2. Abra [test-form.html](./test-form.html).
3. No popup, use `Usar massa local`.
4. Teste os registros `marketing-001`, `marketing-002` e `storage-001`.
5. Confirme o preenchimento dos campos mapeados por seletor e dos campos cobertos apenas pela heuristica.

## Self-test

Para uma regressao rapida do nucleo de autofill sem navegador:

1. Execute `node selftest.js` dentro de `tools/rpa4all-form-autofill-extension`.
2. O teste monta um DOM sintetico, carrega `autofill-core.js` e valida campos explicitos, heuristica, `select` e emissao de eventos.

## Observacoes

- O preenchimento nao clica em botao de submit.
- Campos preenchidos disparam eventos `input` e `change`.
- Se o endpoint real de massa de teste for diferente, basta ajustar em `Options`.
