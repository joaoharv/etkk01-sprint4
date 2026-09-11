"""Transform Gold: agregacoes diarias da Silver.

Somente groupby / count / mean — nenhuma regra de negocio nova. Cada funcao
devolve um DataFrame pronto para a respectiva tabela gold.*.
"""

from __future__ import annotations

import pandas as pd

from config.logging import get_logger

log = get_logger(__name__)

_PREVISOES_COLS = [
    "data_referencia", "serie", "horizonte",
    "valor_previsto", "modelo_utilizado", "gerado_em",
]


def _por_dia(df: pd.DataFrame, dimensao: str | None = None) -> pd.DataFrame:
    chaves = ["data_abertura"] + ([dimensao] if dimensao else [])
    return (
        df.groupby(chaves, dropna=False)
        .size()
        .reset_index(name="total_incidentes")
    )


def _kpi_resumo(df: pd.DataFrame) -> pd.DataFrame:
    dias = pd.DataFrame({"data_abertura": sorted(df["data_abertura"].unique())})

    duracao = (
        df.loc[df["duracao_valida"]]
        .groupby("data_abertura")["duracao_segundos"].mean()
        .rename("duracao_media_segundos").reset_index()
    )
    resolucao = (
        df.groupby("data_abertura")["foi_resolvido"].mean()
        .rename("taxa_resolucao").reset_index()
    )
    violado = (
        df.loc[df["entrou_kpi"]]
        .assign(_v=lambda x: x["kpi_violado"].astype("float64"))
        .groupby("data_abertura")["_v"].mean()
        .rename("taxa_kpi_violado").reset_index()
    )

    return (
        dias.merge(duracao, on="data_abertura", how="left")
        .merge(resolucao, on="data_abertura", how="left")
        .merge(violado, on="data_abertura", how="left")
    )


def build_gold(df_silver: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Recebe a Silver e devolve {nome_tabela_gold: DataFrame}."""
    df = df_silver.copy()
    df["data_abertura"] = pd.to_datetime(df["data_abertura"]).dt.date
    df["kpi_violado"] = df["kpi_violado"].astype("boolean")
    df["hora"] = pd.to_datetime(df["aberto"]).dt.hour
    df["grupo_categoria"] = df["grupo_designado"].where(
        df["grupo_designado"] == "Team14", "Outros"
    )

    tabelas: dict[str, pd.DataFrame] = {
        "incidentes_diario_total": _por_dia(df),
        "incidentes_diario_prioridade": _por_dia(df, "prioridade"),
        "incidentes_diario_grupo": _por_dia(df, "grupo_categoria"),
        "incidentes_diario_grupo_full": _por_dia(df, "grupo_designado"),
        "incidentes_diario_aberto_por": _por_dia(df, "aberto_por"),
        "incidentes_diario_status": _por_dia(df, "status"),
        "incidentes_diario_categoria": _por_dia(df, "categoria"),
        "incidentes_diario_codigo_fechamento": _por_dia(df, "codigo_fechamento"),
        "incidentes_diario_kpi": (
            df.groupby(["data_abertura", "entrou_kpi", "kpi_violado"], dropna=False)
            .size().reset_index(name="total_incidentes")
            .assign(kpi_violado=lambda x: x["kpi_violado"].astype("boolean"))
        ),
        "kpi_resumo": _kpi_resumo(df),
        "incidentes_horario": (
            df.groupby(["hora", "dia_semana"])
            .size().reset_index(name="total_incidentes")
        ),
        "previsoes": pd.DataFrame(columns=_PREVISOES_COLS),
    }

    total_gold = int(tabelas["incidentes_diario_total"]["total_incidentes"].sum())
    log.info(
        "Gold construida: %d tabelas | soma incidentes_diario_total = %d",
        len(tabelas), total_gold,
    )
    return tabelas
