-- GOLD (ML): saida do modelo de classificacao de Prioridade (Plano 2.1, Etapa 5).
--
-- Grao = 1 linha por incidente (numero), NAO por dia -- diferente de gold.previsoes,
-- que e' por (data_referencia, serie, horizonte). Ver Plano 2.1, "Auditoria de
-- granularidade". Representa a previsao VIGENTE por incidente -- UPSERT, nunca
-- TRUNCATE (ver src/load/load_previsoes.py, Etapa 8).
--
-- prioridade_real existe para auditoria/matriz de confusao (a fonte e' estatica, o
-- valor real ja e' conhecido) -- NUNCA e' usada como feature do modelo (ver
-- src/ml/features/prioridade_features.py, Etapa 11).
--
-- score_vencedor vem de LinearSVC.decision_function() -- NAO e' probabilidade.
CREATE TABLE IF NOT EXISTS gold.previsoes_prioridade (
    numero               text PRIMARY KEY,
    data_abertura        date NOT NULL,
    prioridade_real      text,
    prioridade_prevista  text NOT NULL CHECK (prioridade_prevista IN ('2 - Alta', '3 - Média', '4 - Baixa')),
    score_vencedor       numeric,
    modelo_utilizado     text NOT NULL,
    versao_modelo        text NOT NULL,
    gerado_em            timestamp without time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_gold_previsoes_prioridade_data ON gold.previsoes_prioridade (data_abertura);
