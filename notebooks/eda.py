"""
EDA + VALUE_COUNTS — LW-DATASET.xlsx

Este script:
1. Carrega a base Excel.
2. Exibe informações gerais da estrutura.
3. Apresenta missing values e duplicidades.
4. Exibe estatísticas descritivas.
5. Executa value_counts() para cada coluna.
6. Faz uma análise exploratória curta e automática.
7. Identifica possíveis colunas numéricas, categóricas e de data.

Dependências:
    pip install pandas openpyxl
"""

from pathlib import Path
import pandas as pd


# ============================================================
# CONFIGURAÇÃO
# ============================================================

# Artefato das sprints 1/2 — analise exploratoria isolada, fora do pipeline.
# O caminho e resolvido a partir da raiz do repo (este arquivo esta em notebooks/).
ARQUIVO = Path(__file__).resolve().parent.parent / "data" / "LW-DATASET.xlsx"
ABA = 0  # Primeira aba. Altere para o nome da aba se necessário.


# ============================================================
# 1. CARREGAMENTO
# ============================================================

def carregar_dados():
    """Carrega a base Excel."""
    df = pd.read_excel(ARQUIVO, sheet_name=ABA)
    return df


# ============================================================
# 2. INFORMAÇÕES GERAIS
# ============================================================

def informacoes_gerais(df):
    print("\n" + "=" * 80)
    print("INFORMAÇÕES GERAIS DA BASE")
    print("=" * 80)

    print(f"Quantidade de linhas: {df.shape[0]:,}")
    print(f"Quantidade de colunas: {df.shape[1]:,}")
    print(f"Total de células: {df.size:,}")

    print("\nTipos de dados:")
    print(df.dtypes)

    print("\nInformações do DataFrame:")
    df.info()


# ============================================================
# 3. MISSING VALUES
# ============================================================

def analisar_missing(df):
    print("\n" + "=" * 80)
    print("MISSING VALUES")
    print("=" * 80)

    missing = df.isna().sum()
    percentual = (missing / len(df) * 100).round(2)

    resultado = pd.DataFrame({
        "missing": missing,
        "percentual": percentual
    }).sort_values("missing", ascending=False)

    print(resultado)

    print("\nColunas sem valores ausentes:")
    print(list(resultado[resultado["missing"] == 0].index))


# ============================================================
# 4. DUPLICIDADES
# ============================================================

def analisar_duplicados(df):
    print("\n" + "=" * 80)
    print("DUPLICIDADES")
    print("=" * 80)

    duplicados = df.duplicated().sum()

    print(f"Linhas duplicadas: {duplicados:,}")
    print(
        f"Percentual de duplicidade: "
        f"{duplicados / len(df) * 100:.2f}%"
    )


# ============================================================
# 5. ESTATÍSTICAS DESCRITIVAS
# ============================================================

def estatisticas_descritivas(df):
    print("\n" + "=" * 80)
    print("ESTATÍSTICAS DESCRITIVAS")
    print("=" * 80)

    print("\nVariáveis numéricas:")
    numericas = df.select_dtypes(include="number")

    if numericas.shape[1] > 0:
        print(numericas.describe().T)
    else:
        print("Nenhuma variável numérica encontrada.")

    print("\nVariáveis categóricas:")
    categoricas = df.select_dtypes(include=["object", "category", "bool"])

    if categoricas.shape[1] > 0:
        print(categoricas.describe().T)
    else:
        print("Nenhuma variável categórica encontrada.")


# ============================================================
# 6. VALUE_COUNTS PARA TODAS AS COLUNAS
# ============================================================

def value_counts_todas_colunas(df):
    print("\n" + "=" * 80)
    print("VALUE_COUNTS — TODAS AS COLUNAS")
    print("=" * 80)

    for coluna in df.columns:
        print("\n" + "-" * 80)
        print(f"COLUNA: {coluna}")
        print(f"TIPO: {df[coluna].dtype}")
        print(f"VALORES ÚNICOS: {df[coluna].nunique(dropna=False):,}")
        print("-" * 80)

        # Inclui NaN no levantamento de frequência
        frequencias = df[coluna].value_counts(dropna=False)

        print(frequencias)

        # Percentual das categorias
        percentuais = (
            df[coluna]
            .value_counts(dropna=False, normalize=True)
            .mul(100)
            .round(2)
        )

        print("\nPercentual:")
        print(percentuais)


# ============================================================
# 7. CARDINALIDADE
# ============================================================

def analisar_cardinalidade(df):
    print("\n" + "=" * 80)
    print("CARDINALIDADE DAS COLUNAS")
    print("=" * 80)

    cardinalidade = pd.DataFrame({
        "tipo": df.dtypes.astype(str),
        "valores_unicos": df.nunique(dropna=False),
        "percentual_unico": (
            df.nunique(dropna=False) / len(df) * 100
        ).round(2)
    }).sort_values("valores_unicos", ascending=False)

    print(cardinalidade)


# ============================================================
# 8. POSSÍVEIS COLUNAS DE ALTA CARDINALIDADE
# ============================================================

def identificar_alta_cardialidade(df):
    print("\n" + "=" * 80)
    print("POSSÍVEIS COLUNAS DE ALTA CARDINALIDADE")
    print("=" * 80)

    limite = 0.80

    for coluna in df.columns:
        proporcao = df[coluna].nunique(dropna=False) / len(df)

        if proporcao >= limite:
            print(
                f"- {coluna}: "
                f"{df[coluna].nunique(dropna=False):,} valores únicos "
                f"({proporcao * 100:.2f}% das linhas)"
            )


# ============================================================
# 9. DETECÇÃO BÁSICA DE DATAS
# ============================================================

def identificar_datas(df):
    print("\n" + "=" * 80)
    print("POSSÍVEIS COLUNAS DE DATA")
    print("=" * 80)

    encontradas = []

    for coluna in df.columns:
        nome = str(coluna).lower()

        if any(
            termo in nome
            for termo in [
                "data",
                "date",
                "dia",
                "mes",
                "mês",
                "ano"
            ]
        ):
            encontradas.append(coluna)

    if encontradas:
        for coluna in encontradas:
            print(f"- {coluna} | tipo atual: {df[coluna].dtype}")
    else:
        print("Nenhuma coluna aparentemente relacionada a data foi identificada.")


# ============================================================
# 10. EDA CURTO / DIAGNÓSTICO AUTOMÁTICO
# ============================================================

def resumo_eda(df):
    print("\n" + "=" * 80)
    print("RESUMO EDA")
    print("=" * 80)

    print("\n1. DIMENSÃO")
    print(f"A base possui {len(df):,} registros e {df.shape[1]:,} colunas.")

    print("\n2. TIPOS DE DADOS")
    numericas = df.select_dtypes(include="number").shape[1]
    categoricas = df.select_dtypes(
        include=["object", "category", "bool"]
    ).shape[1]

    print(f"Colunas numéricas: {numericas}")
    print(f"Colunas categóricas/textuais: {categoricas}")

    print("\n3. QUALIDADE DOS DADOS")

    total_missing = df.isna().sum().sum()
    total_duplicados = df.duplicated().sum()

    print(f"Total de valores ausentes: {total_missing:,}")
    print(f"Total de registros duplicados: {total_duplicados:,}")

    print("\n4. VARIABILIDADE")

    for coluna in df.columns:
        unicos = df[coluna].nunique(dropna=False)

        if unicos <= 10:
            print(
                f"- {coluna}: {unicos} valores únicos "
                "→ boa candidata para análise categórica."
            )

    print("\n5. POSSÍVEIS ALERTAS")

    alertas = []

    for coluna in df.columns:
        missing_pct = df[coluna].isna().mean() * 100

        if missing_pct >= 30:
            alertas.append(
                f"- {coluna}: {missing_pct:.2f}% de valores ausentes."
            )

    if df.duplicated().sum() > 0:
        alertas.append(
            f"- Existem {df.duplicated().sum():,} registros duplicados."
        )

    if alertas:
        print("\n".join(alertas))
    else:
        print("Nenhum alerta básico identificado.")

    print("\n6. PRIMEIRAS LINHAS")
    print(df.head())

    print("\n7. ÚLTIMAS LINHAS")
    print(df.tail())


# ============================================================
# 11. EXECUÇÃO
# ============================================================

def main():
    print("=" * 80)
    print("EDA — LW-DATASET")
    print("=" * 80)

    df = carregar_dados()

    informacoes_gerais(df)
    analisar_missing(df)
    analisar_duplicados(df)
    estatisticas_descritivas(df)
    analisar_cardinalidade(df)
    identificar_alta_cardialidade(df)
    identificar_datas(df)
    resumo_eda(df)

    # Value Counts fica no final porque pode gerar bastante saída.
    value_counts_todas_colunas(df)

    print("\n" + "=" * 80)
    print("EDA FINALIZADO")
    print("=" * 80)


if __name__ == "__main__":
    main()
