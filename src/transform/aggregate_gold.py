"""Transform Gold: agregacoes diarias da Silver.

Somente groupby / count / mean — nenhuma regra de negocio nova. Cada funcao
devolve um DataFrame pronto para a respectiva tabela gold.*.
"""

from __future__ import annotations

import pandas as pd

from config.logging import get_logger

log = get_logger(__name__)


def _por_dia(df: pd.DataFrame, dimensao: str | None = None) -> pd.DataFrame:
    chaves = ["data_abertura"] + ([dimensao] if dimensao else [])
    return (
        df.groupby(chaves, dropna=False)
        .size()
        .reset_index(name="total_incidentes")
    )


def _kpi_resumo(df: pd.DataFrame) -> pd.DataFrame:
    dias = pd.DataFrame({"data_abertura": sorted(df["data_abertura"].unique())})

    # duracao_media_segundos: KPI OFICIAL. Formula inalterada -- nao mexer.
    # Qualquer metrica robusta/analitica entra como coluna ADICIONAL abaixo,
    # nunca em substituicao a esta.
    duracao = (
        df.loc[df["duracao_valida"]]
        .groupby("data_abertura")["duracao_segundos"].mean()
        .rename("duracao_media_segundos").reset_index()
    )

    # Metricas analiticas/robustas -- mesma populacao do KPI oficial acima
    # (duracao_valida=True), para permitir comparacao direta dia a dia.
    # duracao_mediana_segundos: nao e' afetada pela cauda extrema.
    duracao_valida_df = df.loc[df["duracao_valida"]]
    duracao_mediana = (
        duracao_valida_df
        .groupby("data_abertura")["duracao_segundos"].median()
        .rename("duracao_mediana_segundos").reset_index()
    )
    # duracao_media_aparada_p99_segundos: media convencional (mesma unidade e
    # leitura do KPI oficial), mas excluindo o 1% superior da distribuicao
    # (mesmo P99 dinamico usado em duracao_outlier_flag na Silver) -- mostra
    # quanto da media oficial e' puxado pela cauda, sem apagar a cauda em si
    # (ela continua intocada em duracao_segundos e no KPI oficial acima).
    limite_p99 = df["duracao_segundos"].quantile(0.99)
    duracao_aparada = (
        duracao_valida_df.loc[duracao_valida_df["duracao_segundos"] <= limite_p99]
        .groupby("data_abertura")["duracao_segundos"].mean()
        .rename("duracao_media_aparada_p99_segundos").reset_index()
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
        .merge(duracao_mediana, on="data_abertura", how="left")
        .merge(duracao_aparada, on="data_abertura", how="left")
        .merge(resolucao, on="data_abertura", how="left")
        .merge(violado, on="data_abertura", how="left")
    )


def build_gold(df_silver: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Recebe a Silver e devolve {nome_tabela_gold: DataFrame}.

    NAO inclui ``previsoes`` nem ``previsoes_prioridade`` -- essas tabelas sao
    propriedade exclusiva do pipeline de ML (src/ml/predict_volume.py,
    src/load/load_previsoes.py), que faz UPSERT e nunca TRUNCATE. Incluir um
    stub vazio aqui fazia load_gold() truncar gold.previsoes a cada execucao
    do ETL principal, apagando as previsoes reais (bug encontrado e corrigido
    na Etapa 8 -- ver relatorio)."""
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
    }

    total_gold = int(tabelas["incidentes_diario_total"]["total_incidentes"].sum())
    log.info(
        "Gold construida: %d tabelas | soma incidentes_diario_total = %d",
        len(tabelas), total_gold,
    )
    return tabelas
