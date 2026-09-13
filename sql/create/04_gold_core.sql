-- GOLD (core): tabelas do Plano Tecnico original (Parte 5). Apenas agregacoes
-- diarias da Silver — nenhuma regra de negocio nova. Consumidas pelo Grafana.

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_total (
    data_abertura     date PRIMARY KEY,
    total_incidentes  integer NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_prioridade (
    data_abertura     date NOT NULL,
    prioridade        text NOT NULL,
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, prioridade)
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_grupo (
    data_abertura     date NOT NULL,
    grupo_categoria   text NOT NULL,          -- 'Team14' ou 'Outros'
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, grupo_categoria)
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_aberto_por (
    data_abertura     date NOT NULL,
    aberto_por        text NOT NULL,          -- 'Monitoramento' ou 'Manual'
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, aberto_por)
);

CREATE TABLE IF NOT EXISTS gold.kpi_resumo (
    data_abertura           date PRIMARY KEY,
    duracao_media_segundos  numeric,          -- media apenas de duracao_valida = true
    taxa_resolucao          numeric,          -- fracao 0..1
    taxa_kpi_violado        numeric           -- fracao 0..1, sobre os que entraram em KPI
);

-- Reservada para o pipeline de ML (forecast de volume D+1/D+7).
--
-- Contrato do Plano 2.1: data_alvo e' SEMPRE derivada de data_referencia + horizonte
-- via coluna GERADA (GENERATED ALWAYS AS ... STORED) -- nunca calculada em Python --
-- para eliminar a logica "+1 dia / +7 dias" duplicada em cada query do Grafana.
-- PK permanece (data_referencia, serie, horizonte); data_alvo NAO entra na PK (e'
-- totalmente derivada dessas 3 colunas). Tabela representa a previsao VIGENTE por
-- chave -- UPSERT, nunca TRUNCATE (ver src/load/load_previsoes.py, Etapa 8).
--
-- ATENCAO: nao usar o caractere de porcentagem em nenhum script deste diretorio --
-- psycopg2/SQLAlchemy o interpretam como inicio de placeholder de parametro em
-- exec_driver_sql(), inclusive dentro de comentario SQL. Escrever por extenso.
CREATE TABLE IF NOT EXISTS gold.previsoes (
    data_referencia   date NOT NULL,
    serie             text NOT NULL,          -- nesta sprint, so 'total'
    horizonte         text NOT NULL CHECK (horizonte IN ('D+1', 'D+7')),
    valor_previsto    numeric CHECK (valor_previsto >= 0),
    modelo_utilizado  text NOT NULL,          -- 'persistencia' | 'ridge_d7'
    versao_modelo     text NOT NULL,
    gerado_em         timestamp without time zone DEFAULT now(),
    data_alvo         date GENERATED ALWAYS AS (
                           data_referencia
                           + (CASE horizonte WHEN 'D+1' THEN 1 WHEN 'D+7' THEN 7 END)
                       ) STORED,
    PRIMARY KEY (data_referencia, serie, horizonte)
);

CREATE INDEX IF NOT EXISTS ix_gold_previsoes_data_alvo ON gold.previsoes (data_alvo);
