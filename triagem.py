import asyncio
import pandas as pd
from lattereview.providers import OpenAIProvider
from lattereview.agents import TitleAbstractReviewer
from lattereview.workflows import ReviewWorkflow

INCLUSION_TEXT = (
    "REGRA ABSOLUTA: O artigo so pode ser APROVADO se atender a TODOS os criterios abaixo simultaneamente. "
    "Se QUALQUER criterio de inclusao nao for atendido, REPROVE imediatamente. "
    "CI1 - O estudo aborda experiencia do usuario (UX) com um produto, sistema ou servico interativo, "
    "incluindo usabilidade, satisfacao, percepcao, engajamento ou adocao. "
    "O foco principal do estudo deve ser IHC ou UX — estudos de marketing, redes, engenharia de sistemas "
    "ou saude clinica sem perspectiva de interacao humano-sistema devem ser reprovados pelo CE2. "
    "CI2 - O abstract descreve EXPLICITAMENTE coleta de dados em dois ou mais momentos distintos e planejados, "
    "com intervalo de tempo entre eles (ex: 'baseline e follow-up', 'semana 1 e semana 4', 'antes e depois', "
    "'three time points', 'two waves', 'longitudinal study with N sessions'). "
    "NAO aceite: mencoes a 'long-term', 'over time', 'temporal' como resultado ou achado. "
    "NAO aceite: variacao temporal emergindo de dados passivos, logs ou mineracao. "
    "DUVIDA sobre se ha coleta em multiplos momentos = REPROVAR. "
    "CI3 - O estudo descreve ou permite inferir pelo menos um metodo, tecnica ou ferramenta utilizado "
    "para coletar dados de UX (ex: questionario, entrevista, diario, think-aloud, ESM, in-app probe). "
    "CI4 - E um estudo primario com coleta de dados originais, nao revisao, mapeamento ou meta-analise."
)

EXCLUSION_TEXT = (
    "REGRA ABSOLUTA: Se o artigo se enquadrar em QUALQUER criterio abaixo, REPROVE imediatamente. "
    "CE1 - A longitudinalidade NAO e parte do design do estudo: aparece apenas como achado, variavel de "
    "resultado, mencao incidental a 'long-term', 'over time' ou variacao temporal em dados secundarios, "
    "logs, mineracao de texto, analytics, ou qualquer fonte que nao seja coleta direta e planejada em "
    "multiplos momentos. "
    "IMPORTANTE: se o abstract NAO descreve explicitamente coleta em dois ou mais momentos com intervalo "
    "de tempo (ex: 'baseline e follow-up', 'semana 1 e semana 4', 'antes e depois'), classifique como "
    "CE1 e REPROVE. Ambiguidade = rejeicao. "
    "CE2 - Nao ha avaliacao de UX como foco principal: o estudo e de marketing, comercio eletronico, "
    "redes sociais como plataforma de negocio, engenharia de redes/sistemas, ou saude clinica sem "
    "perspectiva de interacao humano-sistema. Mencionar UX superficialmente nao e suficiente para passar. "
    "CE3 - A coleta de dados ocorre em apenas um momento (estudo transversal, sessao unica, survey pontual, "
    "experimento de laboratorio com uma unica sessao). "
    "CE4 - A temporalidade emerge exclusivamente de dados passivos (logs, mineracao de texto, analytics, "
    "dados de forum, redes sociais) sem nenhuma coleta direta de percepcao do usuario em multiplos momentos. "
    "CE5 - O abstract nao descreve de forma inequivoca quando e quantas vezes os dados foram coletados. "
    "Se nao ha descricao explicita de pelo menos dois momentos de coleta separados por intervalo de tempo, REPROVE. "
    "CE6 - O produto avaliado nao e um sistema interativo digital nem envolve interacao humano-computador. "
    "CE7 - E um estudo secundario (revisao sistematica, mapeamento, survey de literatura, framework "
    "teorico sem coleta primaria)."
)

provider = OpenAIProvider(
    model="gemini-2.5-flash",
    api_key="",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

reviewer_strict = TitleAbstractReviewer(
    provider=provider,
    name="Revisor_Rigoroso",
    backstory=(
        "Voce e um revisor cientifico experiente em revisoes sistematicas de IHC e UX. "
        "Sua regra de ouro: so APROVE se o abstract descrever EXPLICITAMENTE coleta de dados "
        "em dois ou mais momentos distintos com intervalo de tempo entre eles. "
        "Qualquer ambiguidade sobre a longitudinalidade = REPROVAR. "
        "Mencoes a 'long-term', 'over time' como resultado ou achado = REPROVAR pelo CE1. "
        "Estudos com sessao unica ou avaliacao pontual = REPROVAR pelo CE3. "
        "O foco do estudo deve ser IHC/UX, nao marketing ou engenharia de redes."
    ),
    inclusion_criteria=INCLUSION_TEXT,
    exclusion_criteria=EXCLUSION_TEXT,
    reasoning="cot",
    model_args={"temperature": 0.0},
    max_concurrency=4
)

reviewer_expert = TitleAbstractReviewer(
    provider=provider,
    name="Especialista_UX",
    backstory=(
        "Voce e um professor senior especializado em UX longitudinal e metodos de pesquisa em IHC. "
        "Sua regra de ouro: so APROVE se o abstract descrever EXPLICITAMENTE coleta de dados "
        "em dois ou mais momentos distintos com intervalo de tempo entre eles. "
        "Qualquer ambiguidade sobre a longitudinalidade = REPROVAR. "
        "Mencoes a 'long-term', 'over time' como resultado ou achado = REPROVAR pelo CE1. "
        "Estudos com sessao unica ou avaliacao pontual = REPROVAR pelo CE3. "
        "O foco do estudo deve ser IHC/UX, nao marketing ou engenharia de redes."
    ),
    inclusion_criteria=INCLUSION_TEXT,
    exclusion_criteria=EXCLUSION_TEXT,
    reasoning="brief",
    model_args={"temperature": 0.0},
    max_concurrency=4
)

workflow = ReviewWorkflow(
    workflow_schema=[
        {
            "round": "1",
            "reviewers": [reviewer_strict],
            "text_inputs": ["title", "abstract"]
        },
        {
            "round": "2",
            "reviewers": [reviewer_expert],
            "text_inputs": ["title", "abstract", "round-1_Revisor_Rigoroso_output"],
            "filter": lambda row: (row["round-1_Revisor_Rigoroso_evaluation"] or 0) >= 4
        }
    ]
)

async def main():
    try:
        input_file = "articles.xls"
        df = pd.read_excel(input_file, engine="xlrd")
        df.columns = [c.strip().lower() for c in df.columns]

        required_cols = {"title", "abstract"}
        missing = required_cols - set(df.columns)
        if missing:
            print("Colunas faltando: " + str(missing))
            print("Colunas encontradas: " + str(list(df.columns)))
            return

        print("Arquivo carregado: " + str(len(df)) + " artigos.")
        print("Iniciando triagem completa de todos os artigos...")

        LOTE = 100
        todos_resultados = []

        for inicio in range(0, len(df), LOTE):
            fim = min(inicio + LOTE, len(df))
            df_lote = df.iloc[inicio:fim]
            print(f"\nProcessando artigos {inicio+1} a {fim}...")

            resultado = await workflow(df_lote)
            todos_resultados.append(resultado)

            # Salva checkpoint parcial a cada lote
            parcial = pd.concat(todos_resultados, ignore_index=True)
            parcial.to_csv("triagem_parcial.csv", index=False, encoding="utf-8-sig")
            aprovados = (parcial['round-1_Revisor_Rigoroso_evaluation'].fillna(0) >= 4).sum()
            print(f"Checkpoint salvo: {len(parcial)} artigos | Aprovados ate agora: {aprovados}")

        final = pd.concat(todos_resultados, ignore_index=True)
        final.to_csv("triagem_1821_completa.csv", index=False, encoding="utf-8-sig")

        aprovados_final = (final['round-1_Revisor_Rigoroso_evaluation'].fillna(0) >= 4).sum()
        print(f"\nSucesso! Total processado: {len(final)} artigos.")
        print(f"Aprovados: {aprovados_final} ({aprovados_final/len(final)*100:.1f}%)")
        print(f"Reprovados: {len(final)-aprovados_final} ({(len(final)-aprovados_final)/len(final)*100:.1f}%)")
        print("Resultado salvo em triagem_1821_completa.csv")

    except Exception as e:
        import traceback
        print("Erro: " + str(e))
        traceback.print_exc()
        print("\nProgresso parcial salvo em triagem_parcial.csv")

if __name__ == "__main__":
    asyncio.run(main())