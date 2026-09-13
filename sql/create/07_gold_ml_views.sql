-- GOLD (ML): view auxiliar para o Dashboard 06 (Plano 2.1, Etapa 10).
--
-- gold.incidentes_diario_total (Dashboards 1-5) inclui TODAS as prioridades e
-- todo o historico 2023-2025 -- e' a populacao certa para BI, mas ERRADA para
-- comparar contra a previsao do modelo de volume. O modelo (notebook 01,
-- replicado em src/ml/features/volume_features.py, Etapa 6) foi treinado e
-- avaliado sobre uma populacao diferente: incidentes com data_abertura >=
-- 2025-01-01, excluindo as classes raras de prioridade (1 - Critica,
-- 5 - Muito Baixa). Comparar gold.previsoes contra gold.incidentes_diario_total
-- viesaria o erro exibido no Dashboard (divergencia concentrada em 143 dos
-- 365 dias de 2025 -- ver achado da Etapa 6).
--
-- Esta view replica, em SQL, EXATAMENTE a mesma query que
-- carregar_volume_diario() roda em Python -- nunca a logica pode divergir
-- entre as duas (ha teste garantindo isso, tests/test_gold_ml_views.py).
-- View (nao tabela materializada): sempre em sincronia com a Silver, sem
-- nenhum passo de ETL/loader adicional.
--
-- ATENCAO: nunca usar o caractere de porcentagem em nenhum script deste
-- diretorio -- psycopg2/SQLAlchemy o interpretam como inicio de placeholder
-- de parametro em exec_driver_sql(), inclusive dentro de comentario SQL
-- (ver sql/create/04_gold_core.sql, achado da Etapa 5).
CREATE OR REPLACE VIEW gold.ml_volume_diario AS
SELECT
    data_abertura,
    COUNT(*) AS volume_total
FROM silver.incidentes_tratados
WHERE data_abertura >= '2025-01-01'
  AND prioridade NOT IN ('1 - Crítica', '5 - Muito Baixa')
GROUP BY data_abertura;
