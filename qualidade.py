"""
=============================================================================
AVALIAÇÃO DE QUALIDADE — Revisão Sistemática de UX Longitudinal
=============================================================================
Autor: [Omitido para revisão cega]
Orientador: [Omitido para revisão cega]
Instituição: [Omitido para revisão cega]
Versão: 2.0 — Questões revisadas após análise contrastiva (maio/2025)
=============================================================================

ESTRUTURA DE PASTAS ESPERADA:
    artigos/
    ├── ACM/           → PDFs da base ACM
    ├── ScienceDirect/ → PDFs da base ScienceDirect
    └── Springer/      → PDFs da base Springer

SAÍDA GERADA:
    qualidade/
    ├── ACM/
    │   ├── ACM_completo.csv
    │   ├── ACM_aprovados.csv
    │   ├── ACM_reprovados.csv
    │   ├── ACM_revisao_manual.csv
    │   └── logs/
    ├── ScienceDirect/ (mesma estrutura)
    ├── Springer/      (mesma estrutura)
    └── consolidado_*.csv

CRITÉRIOS DE APROVAÇÃO (v2):
    1. Score total > 7.0 (de um máximo de 9.0)
    2. Q4 = SIM obrigatório (justificativa do design temporal) — ELIMINATÓRIA
    3. Q6 = SIM obrigatório (visualização temporal da evolução de UX) — ELIMINATÓRIA
    Um artigo é aprovado apenas se atender aos três critérios simultaneamente.

COMO USAR:
    1. pip install google-generativeai pandas tqdm
    2. Defina sua GEMINI_API_KEY abaixo (ou via variável de ambiente)
    3. Aponte PASTA_ARTIGOS para o diretório raiz com as subpastas por base
    4. Execute: python qualidade_v2.py
=============================================================================
"""

import os
import re
import json
import time
import base64
import logging
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

import google.generativeai as genai
import pandas as pd
from tqdm import tqdm

# =============================================================================
# CONFIGURAÇÕES — ajuste aqui antes de rodar
# =============================================================================

GEMINI_API_KEY   = ""     # ou defina a variável GEMINI_API_KEY no ambiente
PASTA_ARTIGOS    = r""
PASTA_SAIDA      = r""
MODELO           = "gemini-2.5-flash"
BASES_VALIDAS    = ["ACM", "ScienceDirect", "Springer"]

# ── Critérios de aprovação (v2) ──────────────────────────────────────────────
SCORE_CORTE      = 6.0    # artigos com score > SCORE_CORTE são aprovados (máx: 9.0)
# Sem questões eliminatórias — critério único de score, conforme Kitchenham (2009)

DELAY_ENTRE_PDFS = 3      # segundos entre chamadas (evita rate limit)
MAX_TENTATIVAS   = 3

# =============================================================================
# PROMPT DE AVALIAÇÃO DE QUALIDADE — v2 (9 questões revisadas)
# =============================================================================

PROMPT_QUALIDADE = """
Você é um avaliador especialista em pesquisa científica sobre Experiência do Usuário (UX),
com profundo conhecimento em métodos de avaliação longitudinal contínua e retrospectiva.
Você está auxiliando em uma Revisão Sistemática da Literatura (RSL) conduzida segundo as
diretrizes de Kitchenham et al. (2009), cujo tema central é:

"Avaliação Longitudinal de UX: Métodos e Ferramentas para Abordagens Contínuas e Retrospectivas"

O objetivo desta RSL é identificar, analisar e comparar métodos e ferramentas utilizados
em avaliações longitudinais de UX, considerando estudos primários publicados nos últimos
dez anos em inglês.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUA TAREFA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Leia o artigo completo em anexo e responda ao questionário de avaliação de qualidade
abaixo. Para cada pergunta, você deve:

1. Atribuir uma classificação obrigatória: SIM / PARCIAL / NÃO
2. Fornecer uma justificativa objetiva e baseada em evidências extraídas diretamente do artigo
3. Transcrever obrigatoriamente o trecho ou indicar a seção exata do artigo que fundamenta
   a classificação atribuída. Nunca deixe este campo vazio.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITÉRIOS DE CLASSIFICAÇÃO (aplicar a TODAS as perguntas)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- SIM     → O artigo aborda o critério de forma clara, explícita e suficiente
- PARCIAL → O artigo menciona ou aborda o critério de forma incompleta, vaga ou implícita
- NÃO     → O artigo não aborda o critério, ou a ausência é explícita

⚠️ IMPORTANTE: Baseie cada classificação EXCLUSIVAMENTE no conteúdo do artigo anexado.
Não utilize conhecimento externo para presumir informações que não estejam no texto.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUESTIONÁRIO DE AVALIAÇÃO DE QUALIDADE (v2 — 9 questões)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Q1. O protocolo de coleta está claramente descrito, incluindo instrumentos utilizados,
    frequência das medições e justificativa para a escolha de métodos longitudinais em
    detrimento de abordagens transversais?

Q2. O estudo justifica o tamanho amostral considerando a natureza longitudinal da pesquisa,
    incluindo possível atrito de participantes (dropout) ao longo do período de coleta?

Q3. O estudo identifica e analisa explicitamente mudanças na experiência do usuário entre
    pelo menos dois pontos de coleta distintos, com discussão sobre a evolução temporal
    observada?

Q4. [CRITÉRIO CENTRAL] O estudo apresenta justificativa explícita para a duração total do
    período de acompanhamento e para a frequência das coletas, relacionando essas escolhas
    ao fenômeno de UX investigado?

Q5. O estudo utiliza técnicas analíticas adequadas para dados longitudinais ou repetidos
    (ex: ANOVA de medidas repetidas, modelos lineares mistos, análise de séries temporais,
    análise de trajetória)?

Q6. [CRITÉRIO CENTRAL] O estudo utiliza alguma forma de visualização temporal para
    representar a evolução da experiência do usuário ao longo do tempo (ex: UX Curves,
    gráficos de linha temporal, mapas de calor temporais, diagramas de trajetória)?

Q7. Os instrumentos ou métricas de UX utilizados são adequados para aplicação repetida ao
    longo do tempo, sem risco elevado de efeito de aprendizagem ou contaminação das
    respostas?

Q8. O estudo relata e discute desafios específicos do delineamento longitudinal, como atrito
    de participantes, efeitos de aprendizagem ou fadiga de resposta, e descreve como foram
    mitigados ou controlados?

Q9. O estudo discute as vantagens e limitações da abordagem de coleta utilizada
    (contínua/in-situ ou retrospectiva) no contexto da avaliação longitudinal de UX
    realizada?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATO OBRIGATÓRIO DE RESPOSTA — RETORNE APENAS O JSON ABAIXO, SEM TEXTO ADICIONAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{
  "titulo": "título completo do artigo",
  "ano": "ano de publicação",
  "questoes": {
    "Q1": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q2": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q3": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q4": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q5": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q6": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q7": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q8": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"},
    "Q9": {"classificacao": "SIM|PARCIAL|NÃO", "justificativa": "...", "trecho": "seção ou trecho literal do artigo"}
  },
  "observacoes": "observações gerais relevantes sobre o artigo para a RSL (pode ser vazio)"
}
"""

# =============================================================================
# MODELO DE DADOS — 9 questões
# =============================================================================

@dataclass
class ResultadoArtigo:
    arquivo:       str   = ""
    base:          str   = ""
    titulo:        str   = ""
    ano:           str   = ""
    q1:            str   = ""
    q1_just:       str   = ""
    q1_trecho:     str   = ""
    q2:            str   = ""
    q2_just:       str   = ""
    q2_trecho:     str   = ""
    q3:            str   = ""
    q3_just:       str   = ""
    q3_trecho:     str   = ""
    q4:            str   = ""   # ELIMINATÓRIA
    q4_just:       str   = ""
    q4_trecho:     str   = ""
    q5:            str   = ""
    q5_just:       str   = ""
    q5_trecho:     str   = ""
    q6:            str   = ""   # ELIMINATÓRIA
    q6_just:       str   = ""
    q6_trecho:     str   = ""
    q7:            str   = ""
    q7_just:       str   = ""
    q7_trecho:     str   = ""
    q8:            str   = ""
    q8_just:       str   = ""
    q8_trecho:     str   = ""
    q9:            str   = ""
    q9_just:       str   = ""
    q9_trecho:     str   = ""
    score_total:      float = 0.0   # máximo: 9.0
    aprovado:         str   = ""    # SIM se score  SCORE_CORTE
    observacoes:      str   = ""
    erro:             str   = ""
    revisao_manual:   str   = ""
    motivo_revisao:   str   = ""

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

NUM_QUESTOES = 9

def calcular_score(questoes: dict) -> float:
    """SIM=1.0, PARCIAL=0.5, NÃO=0.0. Máximo = 9.0."""
    pontos = {"SIM": 1.0, "PARCIAL": 0.5, "NÃO": 0.0, "NAO": 0.0}
    total = 0.0
    for q in questoes.values():
        classificacao = q.get("classificacao", "NÃO").strip().upper()
        total += pontos.get(classificacao, 0.0)
    return round(total, 1)





def pdf_para_base64(caminho_pdf: Path) -> str:
    with open(caminho_pdf, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def limpar_json(texto: str) -> str:
    texto = texto.strip()
    texto = re.sub(r"^```json\s*", "", texto)
    texto = re.sub(r"^```\s*",    "", texto)
    texto = re.sub(r"\s*```$",    "", texto)
    return texto.strip()


def configurar_logs(pasta_saida: Path):
    pasta_saida.mkdir(parents=True, exist_ok=True)
    log_path = pasta_saida / f"execucao_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def salvar_log_individual(pasta_logs: Path, nome_arquivo: str, conteudo: str):
    pasta_logs.mkdir(parents=True, exist_ok=True)
    nome_limpo = re.sub(r'[<>:"/\\|?*]', '_', nome_arquivo)
    with open(pasta_logs / f"{nome_limpo}.txt", "w", encoding="utf-8") as f:
        f.write(conteudo)

# =============================================================================
# AVALIADOR PRINCIPAL
# =============================================================================

class AvaliadorQualidade:
    def __init__(self, api_key: str, modelo: str = MODELO):
        genai.configure(api_key=api_key)
        self.modelo = genai.GenerativeModel(modelo)
        self.logger = logging.getLogger(__name__)

    def _verificar_qualidade_resposta(self, resultado: ResultadoArtigo, questoes: dict) -> tuple[bool, str]:
        """
        Detecta situações que exigem revisão manual:
        - Falha total de processamento
        - Menos de 9 questões respondidas
        - Justificativas ou trechos vazios
        - Todas as respostas idênticas (possível resposta automática do Gemini)
        """
        motivos = []

        if resultado.erro:
            return True, f"ERRO DE PROCESSAMENTO: {resultado.erro}"

        respondidas = len(questoes)
        if respondidas < NUM_QUESTOES:
            motivos.append(f"Apenas {respondidas}/{NUM_QUESTOES} questões respondidas")

        vazios = []
        for num in range(1, NUM_QUESTOES + 1):
            q = questoes.get(f"Q{num}", {})
            if not q.get("justificativa", "").strip() or q.get("justificativa", "").strip() in ("...", "-", "N/A"):
                vazios.append(f"Q{num} sem justificativa")
            if not q.get("trecho", "").strip() or q.get("trecho", "").strip() in ("...", "-", "N/A"):
                vazios.append(f"Q{num} sem trecho")
        if vazios:
            motivos.append("Campos vazios: " + "; ".join(vazios[:5]))

        classificacoes = [
            questoes.get(f"Q{n}", {}).get("classificacao", "").upper()
            for n in range(1, NUM_QUESTOES + 1)
        ]
        if len(set(classificacoes)) == 1 and classificacoes[0] in ("SIM", "NÃO", "PARCIAL"):
            motivos.append(f"Todas as {NUM_QUESTOES} respostas são '{classificacoes[0]}' — possível resposta automática")

        if motivos:
            return True, " | ".join(motivos)
        return False, ""

    def avaliar_pdf(self, caminho_pdf: Path, base: str) -> ResultadoArtigo:
        resultado = ResultadoArtigo(arquivo=caminho_pdf.name, base=base)

        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                self.logger.info(f"  [{tentativa}/{MAX_TENTATIVAS}] Avaliando: {caminho_pdf.name}")

                pdf_data = pdf_para_base64(caminho_pdf)
                resposta = self.modelo.generate_content(
                    [{"mime_type": "application/pdf", "data": pdf_data}, PROMPT_QUALIDADE],
                    generation_config={"temperature": 0.0}
                )

                dados = json.loads(limpar_json(resposta.text))

                resultado.titulo      = dados.get("titulo", "")
                resultado.ano         = dados.get("ano", "")
                resultado.observacoes = dados.get("observacoes", "")

                questoes = dados.get("questoes", {})

                # Score (máx 9.0)
                resultado.score_total = calcular_score(questoes)

                # Preenchimento Q1–Q9
                for num in range(1, NUM_QUESTOES + 1):
                    q    = questoes.get(f"Q{num}", {})
                    attr = f"q{num}"
                    setattr(resultado, attr,             q.get("classificacao", "NÃO"))
                    setattr(resultado, f"{attr}_just",   q.get("justificativa", ""))
                    setattr(resultado, f"{attr}_trecho", q.get("trecho", ""))

                # Aprovação: score > SCORE_CORTE (critério único — Kitchenham 2009)
                resultado.aprovado = "SIM" if resultado.score_total > SCORE_CORTE else "NÃO"

                # Verificação da qualidade da resposta (revisão manual)
                precisa_revisao, motivo_rev = self._verificar_qualidade_resposta(resultado, questoes)
                resultado.revisao_manual = "SIM" if precisa_revisao else "NÃO"
                resultado.motivo_revisao = motivo_rev
                if precisa_revisao:
                    self.logger.warning(f"  ⚠ REVISÃO MANUAL: {caminho_pdf.name} | {motivo_rev}")

                return resultado

            except json.JSONDecodeError as e:
                self.logger.warning(f"  JSON inválido na tentativa {tentativa}: {e}")
                resultado.erro = f"JSONDecodeError: {e}"
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(5)

            except Exception as e:
                self.logger.warning(f"  Erro na tentativa {tentativa}: {e}")
                resultado.erro = str(e)
                if tentativa < MAX_TENTATIVAS:
                    time.sleep(10)

        resultado.revisao_manual  = "SIM"
        resultado.motivo_revisao  = f"FALHA TOTAL: {MAX_TENTATIVAS} tentativas sem sucesso."
        resultado.aprovado        = "NÃO"
        resultado.motivo_reprovacao = "Falha de processamento — revisar manualmente"
        self.logger.error(f"  ✗ FALHA TOTAL: {caminho_pdf.name}")
        return resultado

# =============================================================================
# COLUNAS E SALVAMENTO
# =============================================================================

COLUNAS_CSV = [
    "arquivo", "base", "titulo", "ano",
    "q1", "q1_just", "q1_trecho",
    "q2", "q2_just", "q2_trecho",
    "q3", "q3_just", "q3_trecho",
    "q4", "q4_just", "q4_trecho",   # eliminatória
    "q5", "q5_just", "q5_trecho",
    "q6", "q6_just", "q6_trecho",   # eliminatória
    "q7", "q7_just", "q7_trecho",
    "q8", "q8_just", "q8_trecho",
    "q9", "q9_just", "q9_trecho",
    "score_total", "aprovado", "revisao_manual", "motivo_revisao", "observacoes", "erro"
]

def _df_from_resultados(resultados: list) -> pd.DataFrame:
    rows = [asdict(r) for r in resultados]
    return pd.DataFrame(rows, columns=COLUNAS_CSV)


def salvar_csv_base(resultados: list, pasta_base_saida: Path, base: str):
    pasta_base_saida.mkdir(parents=True, exist_ok=True)
    df = _df_from_resultados(resultados)
    df.to_csv(pasta_base_saida / f"{base}_completo.csv",      index=False, encoding="utf-8-sig")
    df[(df["aprovado"] == "SIM") & (df["revisao_manual"] == "NÃO")].to_csv(
        pasta_base_saida / f"{base}_aprovados.csv",            index=False, encoding="utf-8-sig")
    df[(df["aprovado"] == "NÃO") & (df["revisao_manual"] == "NÃO")].to_csv(
        pasta_base_saida / f"{base}_reprovados.csv",           index=False, encoding="utf-8-sig")
    df[df["revisao_manual"] == "SIM"].to_csv(
        pasta_base_saida / f"{base}_revisao_manual.csv",       index=False, encoding="utf-8-sig")


def salvar_consolidado(todos: list, pasta_saida: Path):
    pasta_saida.mkdir(parents=True, exist_ok=True)
    df = _df_from_resultados(todos)
    df.to_csv(pasta_saida / "consolidado_completo.csv",       index=False, encoding="utf-8-sig")
    df[(df["aprovado"] == "SIM") & (df["revisao_manual"] == "NÃO")].to_csv(
        pasta_saida / "consolidado_aprovados.csv",             index=False, encoding="utf-8-sig")
    df[(df["aprovado"] == "NÃO") & (df["revisao_manual"] == "NÃO")].to_csv(
        pasta_saida / "consolidado_reprovados.csv",            index=False, encoding="utf-8-sig")
    df[df["revisao_manual"] == "SIM"].to_csv(
        pasta_saida / "consolidado_revisao_manual.csv",        index=False, encoding="utf-8-sig")

# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Avaliação de qualidade RSL UX Longitudinal — v2")
    parser.add_argument("--artigos",  default=PASTA_ARTIGOS)
    parser.add_argument("--saida",    default=PASTA_SAIDA)
    parser.add_argument("--api-key",  default=GEMINI_API_KEY)
    parser.add_argument("--corte",    default=SCORE_CORTE, type=float,
                        help="Score mínimo para aprovação (padrão: >7.0 de 9.0)")
    args = parser.parse_args()

    pasta_artigos = Path(args.artigos)
    pasta_saida   = Path(args.saida)
    logger = configurar_logs(pasta_saida)

    logger.info("=" * 65)
    logger.info("AVALIAÇÃO DE QUALIDADE v2 — RSL UX Longitudinal")
    logger.info(f"Pasta de artigos  : {pasta_artigos}")
    logger.info(f"Pasta de saída    : {pasta_saida}")
    logger.info(f"Score de corte    : >{args.corte} (máximo: {NUM_QUESTOES}.0)")
    logger.info("=" * 65)

    api_key = args.api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error("GEMINI_API_KEY não configurada.")
        return

    avaliador = AvaliadorQualidade(api_key=api_key)
    todos_resultados = []

    for base in BASES_VALIDAS:
        pasta_base = pasta_artigos / base
        if not pasta_base.exists():
            logger.warning(f"Pasta não encontrada, pulando: {pasta_base}")
            continue

        pdfs = sorted(pasta_base.glob("*.pdf"))
        if not pdfs:
            logger.warning(f"Nenhum PDF em: {pasta_base}")
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"BASE: {base} — {len(pdfs)} artigos")
        logger.info(f"{'='*50}")

        resultados_base = []
        pasta_logs_base = pasta_saida / base / "logs"

        for pdf in tqdm(pdfs, desc=f"{base}", unit="artigo"):
            resultado = avaliador.avaliar_pdf(pdf, base)
            resultados_base.append(resultado)
            todos_resultados.append(resultado)

            log_individual = (
                f"Arquivo          : {resultado.arquivo}\n"
                f"Base             : {resultado.base}\n"
                f"Título           : {resultado.titulo}\n"
                f"Score            : {resultado.score_total} / {NUM_QUESTOES}.0\n"
                f"Aprovado         : {resultado.aprovado}\n"
                f"Revisão manual   : {resultado.revisao_manual}\n"
                f"Erro             : {resultado.erro}\n"
            )
            salvar_log_individual(pasta_logs_base, pdf.stem, log_individual)
            salvar_csv_base(resultados_base, pasta_saida / base, base)
            time.sleep(DELAY_ENTRE_PDFS)

        aprovados  = sum(1 for r in resultados_base if r.aprovado == "SIM" and r.revisao_manual == "NÃO")
        reprovados = sum(1 for r in resultados_base if r.aprovado == "NÃO" and r.revisao_manual == "NÃO")
        rev_base   = sum(1 for r in resultados_base if r.revisao_manual == "SIM")
        score_med  = sum(r.score_total for r in resultados_base) / len(resultados_base)

        logger.info(f"\nBase {base} concluída:")
        logger.info(f"  Total         : {len(resultados_base)}")
        logger.info(f"  Aprovados     : {aprovados}")
        logger.info(f"  Reprovados    : {reprovados}")
        logger.info(f"  Revisão manual: {rev_base}")
        logger.info(f"  Score médio   : {score_med:.2f} / {NUM_QUESTOES}.0")

    if todos_resultados:
        salvar_consolidado(todos_resultados, pasta_saida)

        total     = len(todos_resultados)
        total_ap  = sum(1 for r in todos_resultados if r.aprovado == "SIM" and r.revisao_manual == "NÃO")
        total_rep = sum(1 for r in todos_resultados if r.aprovado == "NÃO" and r.revisao_manual == "NÃO")
        total_rev = sum(1 for r in todos_resultados if r.revisao_manual == "SIM")
        score_g   = sum(r.score_total for r in todos_resultados) / total

        logger.info(f"\n{'='*65}")
        logger.info("RESUMO GERAL")
        logger.info(f"  Total avaliados   : {total}")
        logger.info(f"  Aprovados         : {total_ap}  ({total_ap/total*100:.1f}%)")
        logger.info(f"  Reprovados        : {total_rep} ({total_rep/total*100:.1f}%)")
        logger.info(f"  Revisão manual    : {total_rev} ({total_rev/total*100:.1f}%)")
        logger.info(f"  Score médio geral : {score_g:.2f} / {NUM_QUESTOES}.0")
        logger.info("=" * 65)


if __name__ == "__main__":
    main()