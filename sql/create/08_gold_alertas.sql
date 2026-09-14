-- gold.alertas_thresholds (Plano 2.1, Etapa 15)
--
-- Registro append-only dos thresholds usados pelos alertas analiticos do
-- Grafana Alerting. Nunca sobrescreve/apaga linha antiga -- cada execucao do
-- pipeline de volume insere uma linha nova por regra, preservando o
-- historico completo para auditoria e reproducao (o Grafana sempre le a
-- linha mais recente por "regra").
--
-- O historico anterior a 2025-09-01 representa um regime operacional
-- distinto (volume ~6,6x menor) e NAO e' usado para calcular o baseline de
-- anomalia do regime vigente -- ver src/ml/alertas_threshold.py.

CREATE TABLE IF NOT EXISTS gold.alertas_thresholds (
    id bigserial PRIMARY KEY,
    calculado_em timestamp NOT NULL DEFAULT now(),
    regra text NOT NULL,
    threshold numeric NOT NULL,
    media numeric,
    desvio numeric,
    p90 numeric,
    p95 numeric,
    p99 numeric,
    qtd_dias_historico integer,
    qtd_dias_acima_historico integer,
    pct_dias_acima_historico numeric,
    regime_data_corte date,
    detalhe text
);

CREATE INDEX IF NOT EXISTS ix_gold_alertas_thresholds_regra_calculado_em
    ON gold.alertas_thresholds (regra, calculado_em DESC);
