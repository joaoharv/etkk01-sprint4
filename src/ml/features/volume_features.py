"""Feature engineering do modelo de volume D+7 (notebook 01, Plano 2.1 - Etapa 6).

A serie base (``volume_total``) NAO reaproveita ``gold.incidentes_diario_total``: essa
tabela e' de uso operacional/BI (Dashboards 1-5) e inclui todas as prioridades. O
notebook treinou e validou o modelo sobre outra populacao -- incidentes com
``data_abertura >= 2025-01-01``, excluindo as classes raras de prioridade
(``1 - Critica``, ``5 - Muito Baixa``, Secao 03 do notebook). Reproduzir essa
populacao exatamente e' condicao para o modelo em producao reproduzir o MAE
reportado no notebook (criterio de aceite da Etapa 8). Ver a divergencia registrada
e aprovada antes desta implementacao.

D+1 NAO usa nada deste modulo -- e' persistencia pura (``volume_total(t)``), sem
parametro treinado (Secao 16 do notebook: nenhum modelo bateu a persistencia em
D+1). So D+7 usa lags + ``periodo_pos_set_2025``.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine

from config.logging import get_logger
from src.db import get_engine

log = get_logger(__name__)

# Populacao replicada do notebook (Secoes 03/05): 2025 em diante, sem as 2 classes
# raras de prioridade (1 registro + 333 registros no dataset inteiro).
DATA_INICIO_MODELAGEM = "2025-01-01"
CLASSES_PRIORIDADE_EXCLUIDAS = ("1 - Crítica", "5 - Muito Baixa")

# Lags do notebook (Secao 11.1) -- LAGS_ALL = [1, 2, 3, 7, 14, 21, 28]. NAO e' um
# range continuo de 1 a 28: propositalmente pula 4,5,6,8..13,15..20,22..27.
LAGS = (1, 2, 3, 7, 14, 21, 28)

# Quebra de regime (Secao 08 do notebook) -- mesma constante, mesmo nome de coluna.
DATA_CORTE_REGIME = "2025-09-01"

LAG_COLS = [f"lag_{k}" for k in LAGS]

# Conjunto de features do modelo D+7 vencedor (Secao 16 do notebook): lags completos
# (E02) + periodo_pos_set_2025 (E08, sob a Estrategia II). Rolling/calendario/
# operacionais foram testados e descartados -- nao entram aqui.
# NUNCA adicionar nenhuma coluna derivada de duracao_segundos (duracao_dias,
# duracao_outlier_flag, etc.): a serie base e' contagem diaria de incidentes
# (carregar_volume_diario), nao granularidade por incidente, e um agregado de
# duracao por dia so fica completo depois que os incidentes daquele dia
# fecham -- risco de leakage temporal indireto (ver auditoria de outliers de
# duracao, docs/PLANO_TRATAMENTO_OUTLIERS_DURACAO.md).
FEATURES_D7 = LAG_COLS + ["periodo_pos_set_2025"]


def carregar_volume_diario(engine: Engine | None = None) -> pd.Series:
    """Serie diaria de ``volume_total``, na populacao EXATA do notebook 01.

    Fonte: ``silver.incidentes_tratados`` -- NUNCA ``gold.incidentes_diario_total``
    (populacao de BI, inclui todas as prioridades e todo o historico 2023-2025).
    """
    engine = engine or get_engine()
    exclusoes = ", ".join(f"'{p}'" for p in CLASSES_PRIORIDADE_EXCLUIDAS)
    sql = f"""
        SELECT data_abertura, COUNT(*) AS volume_total
        FROM silver.incidentes_tratados
        WHERE data_abertura >= '{DATA_INICIO_MODELAGEM}'
          AND prioridade NOT IN ({exclusoes})
        GROUP BY data_abertura
        ORDER BY data_abertura
    """
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    serie = df.set_index(pd.to_datetime(df["data_abertura"]))["volume_total"]
    serie.index.name = "data_abertura"
    serie = serie.asfreq("D")  # garante grade diaria continua, mesmo padrao do notebook

    if serie.isna().any():
        dias_vazios = serie[serie.isna()].index.tolist()
        raise ValueError(
            f"Serie de volume tem {len(dias_vazios)} dia(s) sem nenhum incidente "
            f"apos o filtro de populacao: {dias_vazios[:5]}... "
            "Isso mudaria a semantica de asfreq('D') do notebook -- parar e revisar."
        )

    log.info(
        "Serie de volume carregada: %d dias (%s a %s), soma=%d",
        len(serie), serie.index.min().date(), serie.index.max().date(), int(serie.sum()),
    )
    return serie


def build_features_volume(volume_diario: pd.Series) -> pd.DataFrame:
    """Matriz de features do modelo D+7 (lags + periodo_pos_set_2025).

    Recebe a serie de ``carregar_volume_diario()`` e descarta as linhas de warmup
    (primeiros 28 dias, onde ``lag_28`` ainda nao existe) -- mesmo criterio do
    notebook (Secao 11.6), mesmo comprimento de corte (rolling_28 exige a mesma
    janela de 28 dias que lag_28).
    """
    df = pd.DataFrame(index=volume_diario.index)
    for k in LAGS:
        df[f"lag_{k}"] = volume_diario.shift(k)
    df["periodo_pos_set_2025"] = (df.index >= pd.Timestamp(DATA_CORTE_REGIME)).astype(int)

    antes = len(df)
    df = df.dropna(subset=LAG_COLS)
    log.info(
        "Features de volume: %d linhas antes do corte de warmup -> %d depois "
        "(descartadas %d linha(s) sem lag_28 no inicio da serie)",
        antes, len(df), antes - len(df),
    )
    return df[FEATURES_D7]


def construir_targets(volume_diario: pd.Series) -> pd.DataFrame:
    """``target_d1(t) = volume_total(t+1)``; ``target_d7(t) = volume_total(t+7)``.

    Mesma convencao do notebook (Secao 09): shift negativo: NaN no fim da serie
    (dias em que o valor futuro ainda nao existe na base).
    """
    return pd.DataFrame(
        {
            "target_d1": volume_diario.shift(-1),
            "target_d7": volume_diario.shift(-7),
        },
        index=volume_diario.index,
    )
