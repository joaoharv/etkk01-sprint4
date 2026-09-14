"""Thresholds dos alertas analiticos de volume (Plano 2.1, Etapa 15).

Duas regras, duas fontes de dados DELIBERADAMENTE distintas:

- ``volume_acima_do_normal`` (Alertas 1 e 2 do plano, D+1 e D+7 comparados
  contra o MESMO baseline): media + 2*stddev do volume diario historico,
  calculado SO sobre o regime vigente (``data_abertura >= DATA_CORTE_REGIME``,
  a mesma constante que ``volume_features.py`` ja usa como feature do
  modelo -- nunca duplicada aqui). O historico anterior a essa data pertence
  a um regime operacional distinto (volume ~6,6x menor -- ver auditoria da
  Etapa 15) e misturaria duas populacoes num unico threshold, produzindo um
  numero estatisticamente incoerente (validado e aprovado antes desta
  implementacao).
- ``erro_d7_acima_do_esperado`` (Alerta 3): 2x o MAE da PROPRIA avaliacao OOS
  que ``predict_volume.py`` ja calcula a cada execucao -- nao recalcula nada,
  so envolve o numero que o pipeline ja produz.

Cada execucao INSERE uma linha nova em ``gold.alertas_thresholds`` (nunca
UPDATE/TRUNCATE) -- historico completo para auditoria/reproducao. O Grafana
Alerting sempre le a linha mais recente de cada regra.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from config.logging import get_logger
from src.db import get_engine
from src.ml.features.volume_features import DATA_CORTE_REGIME

log = get_logger(__name__)

REGRA_VOLUME = "volume_acima_do_normal"
REGRA_ERRO_D7 = "erro_d7_acima_do_esperado"

_SQL_ESTATISTICAS_REGIME_ATUAL = """
    WITH regime AS (
        SELECT volume_total
        FROM gold.ml_volume_diario
        WHERE data_abertura >= :data_corte
    ), stats AS (
        SELECT avg(volume_total) AS media, stddev(volume_total) AS desvio, count(*) AS qtd_dias
        FROM regime
    )
    SELECT
        stats.media AS media,
        stats.desvio AS desvio,
        (stats.media + 2 * stats.desvio) AS threshold,
        (SELECT percentile_cont(0.90) WITHIN GROUP (ORDER BY volume_total) FROM regime) AS p90,
        (SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY volume_total) FROM regime) AS p95,
        (SELECT percentile_cont(0.99) WITHIN GROUP (ORDER BY volume_total) FROM regime) AS p99,
        stats.qtd_dias AS qtd_dias,
        (SELECT count(*) FROM regime WHERE volume_total > stats.media + 2 * stats.desvio) AS qtd_dias_acima
    FROM stats
"""

_INSERT_THRESHOLD = text(
    "INSERT INTO gold.alertas_thresholds "
    "(regra, threshold, media, desvio, p90, p95, p99, qtd_dias_historico, "
    " qtd_dias_acima_historico, pct_dias_acima_historico, regime_data_corte, detalhe) "
    "VALUES (:regra, :threshold, :media, :desvio, :p90, :p95, :p99, :qtd_dias_historico, "
    " :qtd_dias_acima_historico, :pct_dias_acima_historico, :regime_data_corte, :detalhe)"
)


def calcular_threshold_volume(engine: Engine | None = None) -> dict:
    """Media + 2*stddev do volume diario, restrito ao regime vigente.

    Formula validada e aprovada apos auditoria (Etapa 15): calcular sobre o
    historico COMPLETO (2025-01-01 em diante) misturaria o regime antigo
    (media=115,6) com o regime vigente (media=765,6), inflando o desvio
    padrao e produzindo um threshold sem relacao com o volume atual.
    """
    engine = engine or get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text(_SQL_ESTATISTICAS_REGIME_ATUAL), {"data_corte": DATA_CORTE_REGIME}
        ).mappings().one()

    qtd_dias = int(row["qtd_dias"])
    qtd_dias_acima = int(row["qtd_dias_acima"])
    pct_dias_acima = round(100.0 * qtd_dias_acima / qtd_dias, 2) if qtd_dias else None

    resultado = {
        "regra": REGRA_VOLUME,
        "threshold": round(float(row["threshold"]), 1),
        "media": round(float(row["media"]), 1),
        "desvio": round(float(row["desvio"]), 1),
        "p90": round(float(row["p90"]), 1),
        "p95": round(float(row["p95"]), 1),
        "p99": round(float(row["p99"]), 1),
        "qtd_dias_historico": qtd_dias,
        "qtd_dias_acima_historico": qtd_dias_acima,
        "pct_dias_acima_historico": pct_dias_acima,
        "regime_data_corte": DATA_CORTE_REGIME,
        "detalhe": (
            "Baseline restrito ao regime vigente (data_abertura >= "
            f"{DATA_CORTE_REGIME}). O historico anterior representa um "
            "regime operacional distinto e nao entra neste calculo."
        ),
    }
    log.info("Threshold '%s' calculado: %s", REGRA_VOLUME, resultado)
    return resultado


def calcular_threshold_erro_d7(metricas_oos_d7: dict) -> dict:
    """2x o MAE da avaliacao OOS que ``predict_volume.py`` ja produziu --
    nunca recalcula a metrica, so deriva o threshold dela."""
    mae = float(metricas_oos_d7["MAE"])
    n = int(metricas_oos_d7["n"])
    resultado = {
        "regra": REGRA_ERRO_D7,
        "threshold": round(2 * mae, 1),
        "media": None,
        "desvio": None,
        "p90": None,
        "p95": None,
        "p99": None,
        "qtd_dias_historico": n,
        "qtd_dias_acima_historico": None,
        "pct_dias_acima_historico": None,
        "regime_data_corte": None,
        "detalhe": f"2 x MAE da avaliacao OOS (D+7) desta mesma execucao (MAE={mae}, n={n}).",
    }
    log.info("Threshold '%s' calculado: %s", REGRA_ERRO_D7, resultado)
    return resultado


def registrar_thresholds(thresholds: list[dict], engine: Engine | None = None) -> None:
    """INSERT append-only -- nunca apaga/atualiza uma linha anterior."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        for t in thresholds:
            conn.execute(_INSERT_THRESHOLD, t)


def calcular_e_registrar_thresholds_volume(metricas_oos_d7: dict) -> dict:
    """Orquestra as duas regras de volume (chamado pela DAG a cada execucao)."""
    threshold_volume = calcular_threshold_volume()
    threshold_erro_d7 = calcular_threshold_erro_d7(metricas_oos_d7)
    registrar_thresholds([threshold_volume, threshold_erro_d7])
    return {REGRA_VOLUME: threshold_volume["threshold"], REGRA_ERRO_D7: threshold_erro_d7["threshold"]}
