"""
=============================================================================
EXTRAÇÃO DE DADOS — RSL UX Longitudinal (v2)
=============================================================================
Autor: [Omitido para revisão cega]
Orientador: [Omitido para revisão cega]
Instituição: [Omitido para revisão cega]
Versão: 3.0 — Formato texto estruturado (sem JSON) para suportar trechos literais (maio/2025)
=============================================================================

MUDANÇA PRINCIPAL v2:
    Para cada campo, o Gemini extrai DOIS valores:
      - "sintese"  → resumo interpretativo (1-3 frases)
      - "trecho"   → cópia literal e exata do trecho do artigo que justifica
    O campo enviado ao Parsifal contém AMBOS, deixando a extração auditável.

CAMPOS DO PARSIFAL (14):
    1.  Objetivo Principal do Estudo
    2.  Contexto da Avaliação
    3.  Duração do Estudo Longitudinal
    4.  Número de Participantes
    5.  Tipo de Abordagem (Select: Continua / Híbrida/Ambas / Retrospectiva)
    6.  Nome do Método/Técnica/Ferramenta Descrita
    7.  Descrição da Abordagem
    8.  Vantagens/Benefícios Reportados
    9.  Desvantagens/Limitações/Desafios Reportados
    10. Métricas de Coleta de Dados Utilizadas
    11. Técnicas de Análise de Dados Utilizadas
    12. Formas de Visualização dos Dados
    13. Vestígios, ideias ou indícios para trabalhos futuros
    14. Comentários adicionais

SAÍDA:
    extracao/
    ├── extracao_completa.csv       → todos os artigos (síntese + trecho por campo)
    ├── extracao_ok.csv             → extrações bem-sucedidas
    └── extracao_revisao_manual.csv → falhas ou campos suspeitos

COMO USAR:
    1. pip install google-generativeai pandas tqdm
    2. Coloque os PDFs dos 64 aprovados em PASTA_APROVADOS
    3. Configure GEMINI_API_KEY
    4. Execute: python extracao_dados_v2.py
=============================================================================
"""

import os
import re
import time
import base64
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

import google.generativeai as genai
import pandas as pd
from tqdm import tqdm

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

GEMINI_API_KEY  = ""   # cole sua chave aqui ou use variável de ambiente
PASTA_APROVADOS = r""
PASTA_SAIDA     = r""
MODELO          = "gemini-2.5-flash"
DELAY_ENTRE_PDFS = 4
MAX_TENTATIVAS   = 3

TIPOS_VALIDOS = {"Continua", "Retrospectiva", "Hibrida/Ambas"}

# =============================================================================
# PROMPT — extração com trechos literais
# =============================================================================

PROMPT_EXTRACAO = """
Você é um pesquisador especialista em Interação Humano-Computador (IHC) e Experiência do
Usuário (UX), conduzindo uma Revisão Sistemática da Literatura (RSL) seguindo Kitchenham
et al. (2009). O tema é:

"Avaliação Longitudinal de UX: Métodos e Ferramentas para Abordagens Contínuas e Retrospectivas"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGRA FUNDAMENTAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Para cada campo, forneça DOIS valores:
  SINTESE: resumo interpretativo curto (1 a 3 frases)
  TRECHO:  cópia LITERAL do texto do artigo que fundamenta a síntese, com indicação da seção.
           NUNCA parafraseie. NUNCA invente. Copie o texto exato.

Se não houver informação: SINTESE: Não informado / TRECHO: Não encontrado no artigo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CAMPOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. objetivo_principal   → Objetivo principal do estudo
2. contexto_avaliacao   → Contexto do sistema/produto avaliado (domínio, tipo de sistema)
3. duracao_estudo       → Duração total do estudo longitudinal
4. numero_participantes → Número de participantes (total e grupos)
5. tipo_abordagem       → SOMENTE SINTESE, sem TRECHO. Escolha UMA: Continua / Retrospectiva / Hibrida/Ambas
                          Continua = coleta durante o uso (ESM, diários, logging)
                          Retrospectiva = coleta após o uso (entrevistas, questionários pós-uso)
                          Hibrida/Ambas = combina contínua E retrospectiva
6. nome_metodo          → Métodos/técnicas/ferramentas de avaliação longitudinal de UX
7. descricao_abordagem  → Como a avaliação foi conduzida (frequência, momentos, coleta)
8. vantagens            → Vantagens/benefícios relatados pelos autores (separe por ;)
9. desvantagens         → Desvantagens/limitações/desafios (separe por ;)
10. metricas_coleta     → Métricas/instrumentos de coleta (SUS, AttrakDiff, Likert, etc. — separe por ;)
11. tecnicas_analise    → Técnicas de análise dos dados (ANOVA, análise temática, etc. — separe por ;)
12. visualizacao_dados  → Formas de visualização dos resultados (gráficos, UX Curves, etc. — separe por ;)
13. trabalhos_futuros   → Sugestões dos autores para pesquisas futuras
14. comentarios_adicionais → Observações relevantes extras (ou: Não informado)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO OBRIGATÓRIO DE RESPOSTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Use EXATAMENTE este formato com os delimitadores @@CAMPO@@, @@SINTESE@@, @@TRECHO@@, @@FIM@@.
NÃO use JSON. NÃO use markdown. Apenas o formato abaixo:

@@TITULO@@
[título completo do artigo]
@@ANO@@
[ano]
@@CAMPO@@objetivo_principal@@SINTESE@@
[síntese]
[trecho literal do artigo — seção X]
@@CAMPO@@contexto_avaliacao@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@duracao_estudo@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@numero_participantes@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@tipo_abordagem@@SINTESE@@
[Continua OU Retrospectiva OU Hibrida/Ambas]
@@CAMPO@@nome_metodo@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@descricao_abordagem@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@vantagens@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@desvantagens@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@metricas_coleta@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@tecnicas_analise@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@visualizacao_dados@@SINTESE@@
[síntese]
[trecho literal ou: Não informado]
@@CAMPO@@trabalhos_futuros@@SINTESE@@
[síntese]
[trecho literal]
@@CAMPO@@comentarios_adicionais@@SINTESE@@
[síntese ou: Não informado]
[trecho literal ou: Não informado]
"""

# =============================================================================================================
# MODELO DE DADOS — um campo por dimensão (sintese + trecho)
# =============================================================================

CAMPOS = [
    "objetivo_principal", "contexto_avaliacao", "duracao_estudo",
    "numero_participantes", "nome_metodo", "descricao_abordagem",
    "vantagens", "desvantagens", "metricas_coleta", "tecnicas_analise",
    "visualizacao_dados", "trabalhos_futuros", "comentarios_adicionais",
]
CAMPO_SEM_TRECHO = "tipo_abordagem"

@dataclass
class ResultadoExtracao:
    arquivo:                       str = ""
    titulo:                        str = ""
    ano:                           str = ""
    # campo 1
    objetivo_principal:            str = ""
    objetivo_principal_trecho:     str = ""
    # campo 2
    contexto_avaliacao:            str = ""
    contexto_avaliacao_trecho:     str = ""
    # campo 3
    duracao_estudo:                str = ""
    duracao_estudo_trecho:         str = ""
    # campo 4
    numero_participantes:          str = ""
    numero_participantes_trecho:   str = ""
    # campo 5 (select — sem trecho)
    tipo_abordagem:                str = ""
    # campo 6
    nome_metodo:                   str = ""
    nome_metodo_trecho:            str = ""
    # campo 7
    descricao_abordagem:           str = ""
    descricao_abordagem_trecho:    str = ""
    # campo 8
    vantagens:                     str = ""
    vantagens_trecho:              str = ""
    # campo 9
    desvantagens:                  str = ""
    desvantagens_trecho:           str = ""
    # campo 10
    metricas_coleta:               str = ""
    metricas_coleta_trecho:        str = ""
    # campo 11
    tecnicas_analise:              str = ""
    tecnicas_analise_trecho:       str = ""
    # campo 12
    visualizacao_dados:            str = ""
    visualizacao_dados_trecho:     str = ""
    # campo 13
    trabalhos_futuros:             str = ""
    trabalhos_futuros_trecho:      str = ""
    # campo 14
    comentarios_adicionais:        str = ""
    comentarios_adicionais_trecho: str = ""
    # controle
    status:         str = ""
    motivo_revisao: str = ""
    erro:           str = ""

# =============================================================================
# HELPERS
# =============================================================================

def pdf_para_base64(caminho: Path) -> str:
    with open(caminho, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def parse_resposta(texto: str) -> dict:
    """
    Faz o parse do formato estruturado com delimitadores @@.
    Robusto: funciona com ou sem @@FIM@@, usando o proximo @@CAMPO@@ como delimitador.
    """
    resultado = {}

    # Extrai titulo e ano
    titulo_m = re.search(r"@@TITULO@@\s*(.+?)\s*@@ANO@@", texto, re.DOTALL)
    ano_m    = re.search(r"@@ANO@@\s*(.+?)\s*@@CAMPO@@", texto, re.DOTALL)
    resultado["titulo"] = titulo_m.group(1).strip() if titulo_m else ""
    resultado["ano"]    = ano_m.group(1).strip() if ano_m else ""

    # Divide o texto por @@CAMPO@@ e processa cada bloco
    blocos = re.split(r"@@CAMPO@@", texto)
    for bloco in blocos[1:]:
        # Extrai nome do campo e conteudo
        m_nome = re.match(r"([\w]+)@@SINTESE@@\s*(.*)", bloco, re.DOTALL)
        if not m_nome:
            continue

        campo = m_nome.group(1).strip()
        resto = m_nome.group(2)

        # Remove @@FIM@@ se existir no final
        if "@@FIM@@" in resto:
            resto = resto.split("@@FIM@@")[0]

        # Separa sintese e trecho
        if "@@TRECHO@@" in resto:
            partes  = resto.split("@@TRECHO@@", 1)
            sintese = partes[0].strip()
            trecho  = partes[1].strip()
        else:
            sintese = resto.strip()
            trecho  = "Nao encontrado no artigo"

        resultado[campo] = {"sintese": sintese, "trecho": trecho}

    return resultado


def preencher_resultado(resultado: ResultadoExtracao, dados: dict):
    """Popula o dataclass a partir do dicionário parseado."""
    resultado.titulo = dados.get('titulo', '')
    resultado.ano    = dados.get('ano', '')

    for campo in CAMPOS:
        bloco = dados.get(campo, {})
        if isinstance(bloco, dict):
            sintese = bloco.get('sintese', 'Não informado')
            trecho  = bloco.get('trecho',  'Não encontrado no artigo')
        else:
            sintese = str(bloco)
            trecho  = 'Não encontrado no artigo'
        setattr(resultado, campo,             sintese)
        setattr(resultado, f"{campo}_trecho", trecho)

    # tipo_abordagem (sem trecho)
    bloco_tipo = dados.get(CAMPO_SEM_TRECHO, {})
    if isinstance(bloco_tipo, dict):
        resultado.tipo_abordagem = bloco_tipo.get('sintese', '').strip()
    else:
        resultado.tipo_abordagem = str(bloco_tipo).strip()


def validar_extracao(resultado: ResultadoExtracao) -> tuple[bool, str]:
    """
    Verifica integridade da extração. Manda para revisão manual se:
    - Campos obrigatórios estão vazios ou 'Não informado'
    - tipo_abordagem não é um valor válido
    - Trechos literais estão vazios em campos críticos
    - Falha total de processamento
    """
    if resultado.erro:
        return True, f"ERRO DE PROCESSAMENTO: {resultado.erro}"

    motivos = []

    obrigatorios = [
        "objetivo_principal", "contexto_avaliacao",
        "duracao_estudo", "numero_participantes",
        "nome_metodo", "descricao_abordagem",
    ]
    for campo in obrigatorios:
        val = getattr(resultado, campo, "").strip().lower()
        if not val or val in ("não informado", "nao informado", "...", "-", ""):
            motivos.append(f"Síntese vazia: {campo}")
        trecho = getattr(resultado, f"{campo}_trecho", "").strip().lower()
        if not trecho or trecho in ("não encontrado no artigo", ""):
            motivos.append(f"Trecho ausente: {campo}")

    if resultado.tipo_abordagem not in TIPOS_VALIDOS:
        motivos.append(
            f"tipo_abordagem inválido: '{resultado.tipo_abordagem}' "
            f"(esperado: Continua | Retrospectiva | Hibrida/Ambas)"
        )

    if motivos:
        return True, " | ".join(motivos)
    return False, ""


def montar_campo_parsifal(sintese: str, trecho: str) -> str:
    """
    Formata o conteúdo que será enviado ao Parsifal:
    síntese interpretativa + trecho literal do artigo.
    """
    return f"{sintese}\n\n[Trecho do artigo]: {trecho}"


def configurar_logs(pasta_saida: Path):
    pasta_saida.mkdir(parents=True, exist_ok=True)
    log_path = pasta_saida / f"extracao_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def salvar_csvs(resultados: list, pasta_saida: Path):
    """Salva CSVs completo, OK e revisão manual. Checkpoint a cada artigo."""
    pasta_saida.mkdir(parents=True, exist_ok=True)
    colunas = list(ResultadoExtracao.__dataclass_fields__.keys())
    rows = [asdict(r) for r in resultados]
    df   = pd.DataFrame(rows, columns=colunas)

    df.to_csv(pasta_saida / "extracao_completa.csv",
              index=False, encoding="utf-8-sig")
    df[df["status"] == "OK"].to_csv(
        pasta_saida / "extracao_ok.csv",
        index=False, encoding="utf-8-sig")
    df[df["status"] == "REVISAR"].to_csv(
        pasta_saida / "extracao_revisao_manual.csv",
        index=False, encoding="utf-8-sig")

# =============================================================================
# EXTRATOR PRINCIPAL
# =============================================================================

class ExtratorDados:
    def __init__(self, api_key: str, modelo: str = MODELO):
        genai.configure(api_key=api_key)
        self.modelo = genai.GenerativeModel(modelo)
        self.logger = logging.getLogger(__name__)

    def extrair_pdf(self, caminho_pdf: Path) -> ResultadoExtracao:
        resultado = ResultadoExtracao(arquivo=caminho_pdf.name)

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                self.logger.info(
                    f"  [{tentativa}/{MAX_TENTATIVAS}] Extraindo: {caminho_pdf.name}"
                )

                pdf_data = pdf_para_base64(caminho_pdf)
                resposta = self.modelo.generate_content(
                    [{"mime_type": "application/pdf", "data": pdf_data}, PROMPT_EXTRACAO],
                    generation_config={"temperature": 0.0}
                )

                dados = parse_resposta(resposta.text)
                preencher_resultado(resultado, dados)

                precisa_revisao, motivo = validar_extracao(resultado)
                resultado.status         = "REVISAR" if precisa_revisao else "OK"
                resultado.motivo_revisao = motivo

                if precisa_revisao:
                    self.logger.warning(
                        f"  ⚠ REVISÃO: {caminho_pdf.name} | {motivo}"
                    )
                else:
                    self.logger.info(f"  ✓ OK: {caminho_pdf.name}")

                return resultado

            except (ValueError, KeyError) as e:
                self.logger.warning(f"  Parse inválido na tentativa {tentativa}: {e}")
                resultado.erro = f"ParseError: {e}"
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(5)

            except Exception as e:
                self.logger.warning(f"  Erro na tentativa {tentativa}: {e}")
                resultado.erro = str(e)
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(10)

        resultado.status         = "REVISAR"
        resultado.motivo_revisao = f"FALHA TOTAL: {MAX_TENTATIVAS} tentativas."
        self.logger.error(f"  ✗ FALHA TOTAL: {caminho_pdf.name}")
        return resultado

# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

def main():
    pasta_aprovados = Path(PASTA_APROVADOS)
    pasta_saida     = Path(PASTA_SAIDA)
    logger          = configurar_logs(pasta_saida)

    logger.info("=" * 65)
    logger.info("EXTRAÇÃO DE DADOS v2 — RSL UX Longitudinal")
    logger.info(f"Pasta de aprovados : {pasta_aprovados}")
    logger.info(f"Pasta de saída     : {pasta_saida}")
    logger.info("Modo: síntese + trecho literal por campo")
    logger.info("=" * 65)

    api_key = GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY não configurada.")
        return

    pdfs = sorted(pasta_aprovados.glob("*.pdf"))
    if not pdfs:
        logger.error(f"Nenhum PDF encontrado em: {pasta_aprovados}")
        return

    logger.info(f"\n{len(pdfs)} PDFs encontrados.\n")

    extrator   = ExtratorDados(api_key=api_key)
    resultados = []

    for pdf in tqdm(pdfs, desc="Extraindo", unit="artigo"):
        resultado = extrator.extrair_pdf(pdf)
        resultados.append(resultado)
        salvar_csvs(resultados, pasta_saida)   # checkpoint a cada artigo
        time.sleep(DELAY_ENTRE_PDFS)

    ok      = sum(1 for r in resultados if r.status == "OK")
    revisar = sum(1 for r in resultados if r.status == "REVISAR")

    logger.info(f"\n{'='*65}")
    logger.info("RESUMO FINAL")
    logger.info(f"  Total processado  : {len(resultados)}")
    logger.info(f"  Extrações OK      : {ok}")
    logger.info(f"  Revisão manual    : {revisar}")
    logger.info(f"  Arquivos em       : {pasta_saida}")

    if revisar > 0:
        logger.info("\nARTIGOS PARA REVISÃO:")
        for r in resultados:
            if r.status == "REVISAR":
                logger.info(f"  {r.arquivo}")
                logger.info(f"    → {r.motivo_revisao}")

    logger.info("=" * 65)


if __name__ == "__main__":
    main()