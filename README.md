# 🔬 Automações para Revisão Sistemática da Literatura com IA

> Pipeline Python para automatizar as etapas de **triagem**, **avaliação de qualidade** e **extração de dados** de uma Revisão Sistemática da Literatura (RSL), desenvolvido pelo grupo de **Iniciação Científica da FASOFT – UniRV (Universidade de Rio Verde)**.

---

## 📌 Sobre este repositório

Este repositório disponibiliza um pipeline completo de automação para condução de RSLs seguindo as diretrizes de **Kitchenham et al. (2009)**. O pipeline cobre desde a triagem de artigos por título e abstract até a extração estruturada de dados dos PDFs aprovados, com sincronização automática na plataforma [Parsifal](https://parsif.al/).

O objetivo é que pesquisadores possam **reutilizar, adaptar e evoluir** esses scripts para suas próprias revisões sistemáticas, independentemente do tema de pesquisa.

---

## 🗂️ Estrutura do Repositório

```
automacoes_RSL/
│
├── 📄 triagem.py                             # PASSO 1 — Triagem automática por título e abstract (IA)
├── 📄 organiza_csv_triagem.py                # PASSO 2 — Organiza e exporta o resultado da triagem
├── 📄 automacao_triagem_para_parsifal.py     # PASSO 3 — Sincroniza decisões da triagem no Parsifal
│
├── 📄 qualidade.py                           # PASSO 4 — Avaliação de qualidade dos PDFs aprovados (IA)
├── 📄 automacao_qualidade_para_parsifal.py   # PASSO 5 — Sincroniza respostas de qualidade no Parsifal
├── 📄 csv_para_excel_qualidade.py            # PASSO 6 — Converte CSVs de qualidade em Excel formatado
│
├── 📄 extracao_dados.py                      # PASSO 7 — Extração de dados dos PDFs aprovados (IA)
├── 📄 automacao_extracao_parsifal.py         # PASSO 8 — Sincroniza dados extraídos no Parsifal
├── 📄 csv_para_excel_extracao.py             # PASSO 9 — Converte CSVs de extração em Excel formatado
│
├── 📄 diagnostico.py                         # 🔧 Utilitário — Diagnóstico do Parsifal (uso opcional)
├── 📄 requirements.txt                       # Dependências do projeto
└── 📄 README.md
```

---

## 🔄 Pipeline Completo — Ordem de Execução

```
[Base de dados: articles.xls]
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 1 — triagem.py                                       │
│  Triagem automática usando LLM (Gemini) via LatteReview     │
│  Entrada : articles.xls                                     │
│  Saída   : triagem_completa.csv                             │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 2 — organiza_csv_triagem.py                          │
│  Organiza resultados e adiciona coluna de decisão final     │
│  Entrada : triagem_completa.csv                             │
│  Saída   : triagem_limpa_completa.xlsx                      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 3 — automacao_triagem_para_parsifal.py               │
│  Sincroniza as decisões de triagem no Parsifal (Selenium)   │
│  Entrada : triagem_completa.csv                             │
│  Saída   : Artigos classificados no Parsifal                │
│            + log_automacao.txt                              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 4 — qualidade.py                                     │
│  Avaliação de qualidade dos PDFs aprovados via Gemini       │
│  Entrada : artigos/ACM/*.pdf                                │
│            artigos/ScienceDirect/*.pdf                      │
│            artigos/Springer/*.pdf                           │
│  Saída   : qualidade/consolidado_completo.csv + por base    │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 5 — automacao_qualidade_para_parsifal.py             │
│  Sincroniza as respostas Q1–Qn de qualidade no Parsifal     │
│  Entrada : qualidade/consolidado_completo.csv               │
│  Saída   : Quality Assessment preenchido no Parsifal        │
│            + log_qualidade_parsifal.txt                     │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 6 — csv_para_excel_qualidade.py                      │
│  Converte CSVs de qualidade em planilhas Excel formatadas   │
│  Entrada : qualidade/*.csv                                  │
│  Saída   : qualidade/*.xlsx (com cores e formatação)        │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 7 — extracao_dados.py                                │
│  Extração estruturada de dados dos PDFs aprovados via       │
│  Gemini, seguindo formulário de extração da RSL             │
│  Entrada : artigos/**/*.pdf                                 │
│  Saída   : extracao/consolidado_extracao.csv + por base     │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 8 — automacao_extracao_parsifal.py                   │
│  Sincroniza os dados extraídos no Parsifal (Selenium)       │
│  Entrada : extracao/consolidado_extracao.csv                │
│  Saída   : Data Extraction preenchido no Parsifal           │
│            + log_extracao_parsifal.txt                      │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  PASSO 9 — csv_para_excel_extracao.py                       │
│  Converte CSVs de extração em planilhas Excel formatadas    │
│  Entrada : extracao/*.csv                                   │
│  Saída   : extracao/*.xlsx (com cores e formatação)         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Descrição Detalhada dos Scripts

### 1. `triagem.py` — Triagem Automática com IA

Realiza a triagem de artigos (inclusão/exclusão) por título e abstract usando dois agentes LLM em sequência via [LatteReview](https://github.com/PouriaRouzrokh/LatteReview):

- **Revisor Rigoroso** (Round 1): aplica critérios de inclusão e exclusão com chain-of-thought
- **Especialista no tema** (Round 2): reavalia apenas os aprovados no Round 1 com raciocínio breve

Processa os artigos em lotes e salva checkpoints parciais para evitar perda de progresso em caso de interrupção.

**Configurar antes de rodar:**
- `api_key` da API Gemini
- Critérios de inclusão/exclusão conforme o protocolo da sua RSL

---

### 2. `organiza_csv_triagem.py` — Organização do Resultado da Triagem

Lê o CSV gerado pelo `triagem.py`, aplica a lógica de decisão final (priorizando o Round 2 sobre o Round 1), renomeia colunas para português e exporta uma planilha Excel limpa e ordenada.

---

### 3. `automacao_triagem_para_parsifal.py` — Sincronização da Triagem com o Parsifal

Automatiza o lançamento das decisões de triagem na plataforma [Parsifal](https://parsif.al/) usando Selenium. Faz login, navega pelos artigos com status *Unclassified* e aplica *Accepted* ou *Rejected* com base no CSV de triagem. Usa **fuzzy matching** para lidar com pequenas diferenças de título entre o CSV e o Parsifal.

**Configurar antes de rodar:**
- `PARSIFAL_USERNAME` e `PARSIFAL_PASSWORD`
- `PARSIFAL_REVIEW_URL` com a URL da sua revisão no Parsifal
- `PLANILHA` com o caminho do CSV de triagem

> ⚠️ **Segurança:** Nunca suba credenciais reais no repositório. Use variáveis de ambiente ou um arquivo `.env` (veja a seção de configuração abaixo).

---

### 4. `qualidade.py` — Avaliação de Qualidade dos PDFs

Avalia cada PDF aprovado na triagem respondendo às questões de qualidade (Q1–Qn) definidas no protocolo da RSL, usando o Gemini. Cada questão recebe **SIM / PARCIAL / NÃO** com justificativa e trecho do artigo. Gera um score numérico e classifica o artigo como aprovado, reprovado ou em revisão manual.

**Estrutura de pastas esperada:**
```
artigos/
├── ACM/            → PDFs da base ACM
├── ScienceDirect/  → PDFs da base ScienceDirect
└── Springer/       → PDFs da base Springer
```

**Configurar antes de rodar:**
- `GEMINI_API_KEY`
- `PASTA_ARTIGOS` — caminho da pasta com os PDFs
- `PASTA_SAIDA` — onde salvar os resultados
- `SCORE_CORTE` — nota mínima para aprovação

---

### 5. `automacao_qualidade_para_parsifal.py` — Sincronização da Qualidade com o Parsifal

Automatiza o preenchimento do **Quality Assessment** no Parsifal usando Selenium. Lê o `consolidado_completo.csv` gerado pelo `qualidade.py` e, para cada artigo, clica nas respostas SIM / PARCIAL / NÃO nas questões Q1–Qn diretamente na interface do Parsifal.

Funcionalidades principais:
- **Fuzzy matching** para casar títulos com pequenas variações entre o CSV e o Parsifal
- **Detecção de artigos já completos** — pula automaticamente artigos com todas as questões respondidas
- **Modo teste** via variável `LIMITE_TESTE` para validar o script em poucos artigos antes de rodar tudo
- **Log de falhas** salvo em `log_qualidade_parsifal.txt`
- Ignora artigos marcados para revisão manual (`revisao_manual = SIM`)

**Configurar antes de rodar:**
- `PARSIFAL_USERNAME` e `PARSIFAL_PASSWORD`
- `PARSIFAL_QUALITY_URL` com a URL da seção de qualidade da sua revisão
- `CSV_CONSOLIDADO` — caminho do `consolidado_completo.csv`
- `LIMITE_TESTE` — número de artigos para teste (use `None` para rodar todos)

---

### 6. `csv_para_excel_qualidade.py` — Conversão CSV → Excel (Qualidade)

Converte todos os CSVs gerados pelo `qualidade.py` em planilhas Excel com formatação visual: cabeçalhos coloridos, linhas alternadas, células coloridas por classificação (SIM = verde, PARCIAL = amarelo, NÃO = vermelho) e colunas com largura ajustada.

**Configurar antes de rodar:**
- `PASTA_QUALIDADE` — caminho da pasta com os CSVs de qualidade

---

### 7. `extracao_dados.py` — Extração de Dados dos PDFs

Realiza a extração estruturada de dados dos PDFs aprovados na avaliação de qualidade, seguindo o formulário de extração definido no protocolo da RSL. Cada campo é extraído via Gemini com justificativa e trecho do artigo. Gera um CSV consolidado com todos os dados extraídos, organizados por base de dados.

**Configurar antes de rodar:**
- `GEMINI_API_KEY`
- `PASTA_ARTIGOS` — caminho da pasta com os PDFs aprovados
- `PASTA_SAIDA` — onde salvar os resultados de extração
- Campos de extração conforme o formulário do seu protocolo de RSL

---

### 8. `automacao_extracao_parsifal.py` — Sincronização da Extração com o Parsifal

Automatiza o preenchimento do **Data Extraction** no Parsifal usando Selenium. Lê o CSV consolidado gerado pelo `extracao_dados.py` e preenche os campos de extração diretamente na interface do Parsifal para cada artigo aprovado.

Funcionalidades principais:
- **Fuzzy matching** para casar títulos entre o CSV e o Parsifal
- **Detecção de artigos já preenchidos** — pula automaticamente
- **Modo teste** via `LIMITE_TESTE`
- **Log de falhas** salvo em `log_extracao_parsifal.txt`

**Configurar antes de rodar:**
- `PARSIFAL_USERNAME` e `PARSIFAL_PASSWORD`
- `PARSIFAL_EXTRACTION_URL` com a URL da seção de extração da sua revisão
- `CSV_CONSOLIDADO` — caminho do CSV de extração consolidado

---

### 9. `csv_para_excel_extracao.py` — Conversão CSV → Excel (Extração)

Converte os CSVs gerados pelo `extracao_dados.py` em planilhas Excel formatadas, com cabeçalhos coloridos, colunas ajustadas e formatação visual para facilitar a análise dos dados extraídos.

**Configurar antes de rodar:**
- `PASTA_EXTRACAO` — caminho da pasta com os CSVs de extração

---

### 🔧 `diagnostico.py` — Diagnóstico do Parsifal (Utilitário)

Script auxiliar para inspecionar a estrutura HTML do Parsifal. Abre o Chrome com interface gráfica, faz login e salva o HTML das páginas relevantes como arquivos locais. Útil para depurar problemas com os scripts de automação do Parsifal quando a interface muda.

---

## ⚙️ Instalação e Configuração

### Pré-requisitos

- Python 3.10 ou superior
- Google Chrome instalado (para os scripts com Selenium)

### Instalando as dependências

```bash
pip install -r requirements.txt
```

Ou manualmente:

```bash
pip install pandas openpyxl lattereview google-generativeai tqdm selenium webdriver-manager fuzzywuzzy python-Levenshtein
```

### Configurando credenciais com segurança

Para não expor suas chaves de API no código, use variáveis de ambiente:

**Windows (PowerShell):**
```powershell
$env:GEMINI_API_KEY = "sua-chave-aqui"
$env:PARSIFAL_USERNAME = "seu-usuario"
$env:PARSIFAL_PASSWORD = "sua-senha"
```

**Linux/macOS:**
```bash
export GEMINI_API_KEY="sua-chave-aqui"
export PARSIFAL_USERNAME="seu-usuario"
export PARSIFAL_PASSWORD="sua-senha"
```

Ou crie um arquivo `.env` na raiz do projeto **(nunca commite este arquivo)**:
```
GEMINI_API_KEY=sua-chave-aqui
PARSIFAL_USERNAME=seu-usuario
PARSIFAL_PASSWORD=sua-senha
```

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| [LatteReview](https://github.com/PouriaRouzrokh/LatteReview) | Agentes de triagem automática com LLM |
| [Gemini 2.5 Flash](https://ai.google.dev/) | Modelo de linguagem para triagem, avaliação de qualidade e extração |
| [Selenium](https://selenium-python.readthedocs.io/) | Automação do navegador para sincronização com o Parsifal |
| [Pandas](https://pandas.pydata.org/) | Manipulação e organização dos dados |
| [OpenPyXL](https://openpyxl.readthedocs.io/) | Geração de planilhas Excel formatadas |
| [FuzzyWuzzy](https://github.com/seatgeek/fuzzywuzzy) | Matching aproximado de títulos entre CSV e Parsifal |
| [Parsifal](https://parsif.al/) | Plataforma de gerenciamento da RSL |

---

## ⚠️ Avisos Importantes

- Os scripts contêm caminhos e variáveis de configuração que **devem ser adaptados** para o seu ambiente antes de rodar. Consulte a seção *Configurar antes de rodar* de cada script.
- Nunca suba credenciais reais (API keys, senhas) para o repositório. Use variáveis de ambiente ou `.env`.
- Recomenda-se rodar cada script primeiro com `LIMITE_TESTE` ativado para validar o comportamento antes de processar todos os artigos.
- Os scripts de automação do Parsifal dependem da estrutura HTML da plataforma. Caso o Parsifal atualize sua interface, use o `diagnostico.py` para inspecionar as mudanças.

---

## 📄 Licença

Este projeto está disponível para uso acadêmico e de pesquisa. Se utilizar estes scripts em seu trabalho, considere citar este repositório.