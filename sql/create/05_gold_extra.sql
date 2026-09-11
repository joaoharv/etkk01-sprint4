-- GOLD (extra): extensoes decididas em DEC3 — sustentam os 5 dashboards do Grafana.
-- Mesma regra: so agregacao diaria da Silver, nenhuma logica de negocio nova.

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_grupo_full (
    data_abertura     date NOT NULL,
    grupo_designado   text NOT NULL,          -- os 17 grupos reais
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, grupo_designado)
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_status (
    data_abertura     date NOT NULL,
    status            text NOT NULL,
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, status)
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_categoria (
    data_abertura     date NOT NULL,
    categoria         text NOT NULL,          -- 'Não informado' quando ausente na origem
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (data_abertura, categoria)
);

CREATE TABLE IF NOT EXISTS gold.incidentes_diario_codigo_fechamento (
    data_abertura      date NOT NULL,
    codigo_fechamento  text NOT NULL,         -- 'Não informado' quando ausente na origem
    total_incidentes   integer NOT NULL,
    PRIMARY KEY (data_abertura, codigo_fechamento)
);

-- kpi_violado e NULL para incidentes fora de KPI; coluna de PK nao aceita NULL.
-- Solucao: UNIQUE INDEX com NULLS NOT DISTINCT (Postgres 15+), preservando a
-- semantica de unicidade da Parte 6 do plano sem trocar o tipo da coluna.
CREATE TABLE IF NOT EXISTS gold.incidentes_diario_kpi (
    data_abertura     date NOT NULL,
    entrou_kpi        boolean NOT NULL,
    kpi_violado       boolean,                -- NULL quando entrou_kpi = false
    total_incidentes  integer NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_gold_incidentes_diario_kpi
    ON gold.incidentes_diario_kpi (data_abertura, entrou_kpi, kpi_violado) NULLS NOT DISTINCT;

CREATE TABLE IF NOT EXISTS gold.incidentes_horario (
    hora              integer NOT NULL,       -- 0..23
    dia_semana        integer NOT NULL,       -- 0=segunda .. 6=domingo
    total_incidentes  integer NOT NULL,
    PRIMARY KEY (hora, dia_semana)
);
