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

-- Reservada para o pipeline de ML (forecast de volume D+1/D+7). Vazia nesta entrega.
CREATE TABLE IF NOT EXISTS gold.previsoes (
    data_referencia   date NOT NULL,
    serie             text NOT NULL,          -- ex.: 'total', 'Team14', 'Prioridade_3'
    horizonte         text NOT NULL,          -- 'D+1' ou 'D+7'
    valor_previsto    numeric,
    modelo_utilizado  text,
    gerado_em         timestamp without time zone DEFAULT now(),
    PRIMARY KEY (data_referencia, serie, horizonte)
);
