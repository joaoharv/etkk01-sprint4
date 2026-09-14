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
    "duracao_segundos", "duracao_valida", "duracao_dias", "duracao_outlier_flag",
    "aberto_por", "status",
    "entrou_kpi", "kpi_violado", "data_abertura", "ano", "mes", "dia_semana",
]

_TOLERANCIA_DURACAO = 1.05  # duracao_segundos pode passar 5% do intervalo aberto->encerrado
_PERCENTIL_OUTLIER_DURACAO = 0.99  # duracao_outlier_flag: sinalizacao estatistica, nao regra de negocio


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

    # 4b. Duracao nunca pode ser negativa -- protecao de regressao (nao ha
    # nenhum caso na fonte atual; se aparecer, falha alto e claro em vez de
    # seguir em silencio, mesmo padrao de guarda das checagens acima).
    if (df["duracao_segundos"] < 0).any():
        raise ValueError("duracao_segundos negativa encontrada na origem.")

    # 5. duracao_valida: nao pode passar muito do intervalo aberto->encerrado.
    # Validacao ESTRUTURAL (o dado e' internamente coerente?) -- nao e' analise
    # estatistica de outlier. Ver duracao_outlier_flag abaixo (conceito distinto,
    # as duas colunas podem ser True ao mesmo tempo).
    intervalo_seg = (df["encerrado"] - df["aberto"]).dt.total_seconds()
    df["duracao_valida"] = df["duracao_segundos"] <= (intervalo_seg * _TOLERANCIA_DURACAO)

    # 5b. duracao_dias: mesma informacao de duracao_segundos, em dias, sem
    # arredondar. duracao_segundos original permanece intocada -- nenhum valor
    # e' filtrado, clipado ou substituido em nenhum ponto desta funcao.
    df["duracao_dias"] = df["duracao_segundos"] / 86400.0

    # 5c. duracao_outlier_flag: sinalizacao ESTATISTICA (> P99 calculado
    # dinamicamente sobre o lote atual -- nunca um numero fixo hardcoded).
    # Significa apenas "esta no extremo superior da distribuicao observada
    # nesta execucao"; NAO significa erro, NAO e' uma classificacao de negocio
    # e NAO deve remover/alterar nenhuma linha. Conceito ortogonal a
    # duracao_valida (ver 5. acima).
    limite_outlier = df["duracao_segundos"].quantile(_PERCENTIL_OUTLIER_DURACAO)
    df["duracao_outlier_flag"] = df["duracao_segundos"] > limite_outlier

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
        "Silver preparada: %d linhas | duracao_valida=false: %d | "
        "duracao_outlier_flag=true: %d | foi_resolvido=true: %d",
        len(resultado),
        int((~resultado["duracao_valida"]).sum()),
        int(resultado["duracao_outlier_flag"].sum()),
        int(resultado["foi_resolvido"].sum()),
    )
    return resultado
