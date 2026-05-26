import pandas as pd

df = pd.read_csv("triagem_1821_completa.csv")

print("Colunas disponíveis:")
print(list(df.columns))

def decidir(row):
    col_expert = 'round-2_Especialista_UX_evaluation'
    col_strict = 'round-1_Revisor_Rigoroso_evaluation'

    if col_expert in row and pd.notna(row.get(col_expert)):
        nota = row[col_expert]
    elif col_strict in row and pd.notna(row.get(col_strict)):
        nota = row[col_strict]
    else:
        return "NAO AVALIADO"

    return "APROVADO" if nota >= 4 else "REPROVADO"

df['Decisao_Final'] = df.apply(decidir, axis=1)

colunas_desejadas = [
    'title', 'abstract', 'Decisao_Final',
    'round-1_Revisor_Rigoroso_evaluation',
    'round-1_Revisor_Rigoroso_output',
    'round-2_Especialista_UX_evaluation',
    'round-2_Especialista_UX_output',
]

colunas_uteis = [c for c in colunas_desejadas if c in df.columns]
df_limpo = df[colunas_uteis]

renomear = {
    'title': 'Titulo',
    'abstract': 'Resumo',
    'round-1_Revisor_Rigoroso_evaluation': 'Avaliacao_Revisor',
    'round-1_Revisor_Rigoroso_output': 'Justificativa_Revisor',
    'round-2_Especialista_UX_evaluation': 'Avaliacao_Especialista',
    'round-2_Especialista_UX_output': 'Justificativa_Especialista',
}
df_limpo = df_limpo.rename(columns={k: v for k, v in renomear.items() if k in df_limpo.columns})
df_limpo = df_limpo.sort_values('Decisao_Final', ascending=True)
df_limpo.to_excel("triagem_limpa_1821_completa.xlsx", index=False)

total = len(df_limpo)
aprovados = (df_limpo['Decisao_Final'] == 'APROVADO').sum()
reprovados = (df_limpo['Decisao_Final'] == 'REPROVADO').sum()
nao_avaliados = (df_limpo['Decisao_Final'] == 'NAO AVALIADO').sum()

print(f"\nPlanilha triagem_limpa_TFC.xlsx gerada!")
print(f"Total: {total} | Aprovados: {aprovados} | Reprovados: {reprovados} | Nao avaliados: {nao_avaliados}")