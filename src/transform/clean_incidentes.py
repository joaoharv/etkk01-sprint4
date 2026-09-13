"""Transform Silver: limpeza e padronizacao dos incidentes.

Unica camada onde ha decisao de qualidade de dado. Funcao pura (sem banco).
Ver PLANO_IMPLEMENTACAO_SPRINT4.md Parte 10.
"""

from __future__ import annotations

import pandas as pd

from config.logging import get_logger

log = get_logger(__name__)

_NAO_INFORMADO = "Não informado"
_COLS_NAO_INFORMADO = ["produto", "categoria", "subcategoria", "codigo_fechamento"]
_COLS_DATA = ["aberto", "resolvido", "encerrado"]

# Colunas da silver.incidentes_tratados, na ordem do schema.
COLUNAS_SILVER = [
    "numero", "prioridade", "produto", "categoria", "subcategoria",
    "grupo_designado", "item_configuracao", "descricao_resumida", "codigo_fechamento",
    "aberto", "resolvido", "foi_resolvido", "encerrado",
    "duracao_segundos", "duracao_valida", "aberto_por", "status",
    "entrou_kpi", "kpi_violado", "data_abertura", "ano", "mes", "dia_semana",
]

_TOLERANCIA_DURACAO = 1.05  # duracao_segundos pode passar 5% do intervalo aberto->encerrado


def _sim_nao(serie: pd.Series) -> pd.Series:
    """'SIM'/'NAO' (case-insensitive) -> boolean nullable; qualquer outro -> <NA>."""
    return (
        serie.astype("string").str.strip().str.upper()
        .map({"SIM": True, "NAO": False})
        .astype("boolean")
    )


def clean(df_bronze: pd.DataFrame) -> pd.DataFrame:
    """Recebe o DataFrame da Bronze e devolve o DataFrame pronto para a Silver."""
    df = df_bronze.copy()

    # 1. Nulos de dimensao -> 'Não informado' (nunca descarta linha)
    for col in _COLS_NAO_INFORMADO:
        df[col] = df[col].fillna(_NAO_INFORMADO).replace("", _NAO_INFORMADO)

    # 2. Datas -> timestamp nativo
    for col in _COLS_DATA:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    obrigatorias_nat = df["aberto"].isna().sum() + df["encerrado"].isna().sum()
    if obrigatorias_nat:
        raise ValueError(
            f"{obrigatorias_nat} registro(s) com 'aberto' ou 'encerrado' invalido/nulo "
            "apos parse — nao deveria ocorrer nesta fonte."
        )

    # 3. Flag de resolucao (resolvido continua nulo quando ausente)
    df["foi_resolvido"] = df["resolvido"].notna()

    # 4. Duracao -> inteiro
    duracao = pd.to_numeric(df["duracao_segundos"], errors="coerce")
    if duracao.isna().any():
        raise ValueError("duracao_segundos com valor nao numerico na origem.")
    df["duracao_segundos"] = duracao.astype("int64")

    # 5. duracao_valida: nao pode passar muito do intervalo aberto->encerrado
    intervalo_seg = (df["encerrado"] - df["aberto"]).dt.total_seconds()
    df["duracao_valida"] = df["duracao_segundos"] <= (intervalo_seg * _TOLERANCIA_DURACAO)

    # 6. KPI: SIM/NAO -> boolean
    df["entrou_kpi"] = _sim_nao(df["entrou_kpi"])
    if df["entrou_kpi"].isna().any():
        raise ValueError("entrou_kpi com valor fora de {SIM, NAO} na origem.")
    df["entrou_kpi"] = df["entrou_kpi"].astype(bool)
    df["kpi_violado"] = _sim_nao(df["kpi_violado"])  # nullable: <NA> quando fora de KPI

    # 7. Colunas de data derivadas (dia_semana: 0=segunda)
    df["data_abertura"] = df["aberto"].dt.date
    df["ano"] = df["aberto"].dt.year.astype("int64")
    df["mes"] = df["aberto"].dt.month.astype("int64")
    df["dia_semana"] = df["aberto"].dt.dayofweek.astype("int64")

    # 8. Deduplicacao por chave natural (mantem a 1a ocorrencia)
    antes = len(df)
    df = df.drop_duplicates(subset=["numero"], keep="first")
    descartadas = antes - len(df)
    if descartadas:
        log.warning("Deduplicacao por 'numero': %d linha(s) descartada(s)", descartadas)

    # 9. Prioridades raras sao preservadas — nenhum filtro por prioridade aqui.

    resultado = df[COLUNAS_SILVER].reset_index(drop=True)
    log.info(
        "Silver preparada: %d linhas | duracao_valida=false: %d | foi_resolvido=true: %d",
        len(resultado),
        int((~resultado["duracao_valida"]).sum()),
        int(resultado["foi_resolvido"].sum()),
    )
    return resultado
