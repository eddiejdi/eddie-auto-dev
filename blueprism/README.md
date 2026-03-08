# Blue Prism - Excel to Web Input Automation

## Descrição
Automação Blue Prism que **lê dados de uma planilha Excel** e **insere automaticamente em um formulário web**, linha por linha.

## Arquivo
- `Excel_WebInput_Process.bprelease` — arquivo XML de release, importável diretamente no Blue Prism

## Como Importar no Blue Prism

1. Abra o **Blue Prism Studio**
2. Vá em **File → Import**
3. Selecione o arquivo `Excel_WebInput_Process.bprelease`
4. Confirme a importação dos 3 componentes:
   - **Process**: `Excel to Web Input`
   - **VBO**: `Utility - Excel VBO`
   - **VBO**: `Web Input VBO`

## Componentes Incluídos

### Processo: Excel to Web Input
Fluxo principal que orquestra a automação:
1. Abre a planilha Excel especificada
2. Lê todos os dados em uma Collection
3. Abre o navegador e navega para o formulário
4. Para cada linha do Excel:
   - Extrai os valores dos 5 campos
   - Preenche os campos no formulário web
   - Submete o formulário
   - Aguarda confirmação
   - Registra sucesso ou erro
5. Fecha navegador e planilha
6. Gera resumo final (total/sucesso/erros)

### VBO: Utility - Excel VBO
Ações disponíveis:
| Ação | Descrição |
|------|-----------|
| Abrir Planilha | Abre arquivo Excel e seleciona aba |
| Obter Total Linhas | Conta linhas com dados |
| Ler Dados Planilha | Lê todos os dados em Collection |
| Fechar Planilha | Fecha e libera recursos |

### VBO: Web Input VBO
Ações disponíveis:
| Ação | Descrição |
|------|-----------|
| Abrir Navegador | Inicia Chrome/IE/Edge |
| Navegar para URL | Acessa URL especificada |
| Aguardar Carregamento | Espera página carregar |
| Preencher Campo | Insere valor em campo (por id/name/xpath) |
| Clicar Botao | Clica em botão do formulário |
| Aguardar Elemento | Espera elemento ficar visível |
| Limpar Campos | Limpa inputs do formulário |
| Fechar Navegador | Encerra o browser |

## Parâmetros de Entrada do Processo

| Parâmetro | Tipo | Exemplo |
|-----------|------|---------|
| `Caminho Arquivo Excel` | Text | `C:\Dados\planilha_input.xlsx` |
| `URL Formulario` | Text | `https://sistema.exemplo.com/formulario` |

## Personalização

### Colunas do Excel
O processo espera 5 colunas (Campo1..Campo5). Para ajustar:
1. Abra o processo no Blue Prism Studio
2. Edite a Collection `Dados Excel` para adicionar/remover campos
3. Ajuste os stages de extração e preenchimento

### Identificadores dos Campos Web
Os campos do formulário web usam IDs padrão (`campo1`..`campo5`, `btnSubmit`, `msgSucesso`). Para ajustar:
1. Inspecione o HTML do formulário alvo
2. Altere os valores dos parâmetros `Identificador Campo` nos stages de preenchimento
3. Pode usar `id`, `name`, `xpath` ou `css` como tipo de identificador

## Tratamento de Erros
- Erros por linha são capturados individualmente (Recover/Resume)
- O processo continua processando as próximas linhas mesmo após erro
- Contadores separados de sucesso e erro
- Exceções críticas (Excel/Browser não abre) param o processo
