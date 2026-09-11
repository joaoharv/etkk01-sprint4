-- SILVER: dados tratados e padronizados. Unica camada com decisao de qualidade.
-- Tipos nativos, PK natural (numero), nulos padronizados, flags e colunas de data
-- derivadas. Ver PLANO_IMPLEMENTACAO_SPRINT4.md Parte 10.
--
-- Desvio consciente em relacao a Parte 6 do plano: incluida a coluna
-- codigo_fechamento — necessaria para a tabela gold.incidentes_diario_codigo_fechamento
-- e para o Dashboard 3 (KPIs/SLA). Segue o mesmo padrao de nulo -> 'Não informado'.

CREATE TABLE IF NOT EXISTS silver.incidentes_tratados (
    numero              text PRIMARY KEY,
    prioridade          text NOT NULL,
    produto             text NOT NULL DEFAULT 'Não informado',
    categoria           text NOT NULL DEFAULT 'Não informado',
    subcategoria        text NOT NULL DEFAULT 'Não informado',
    grupo_designado     text NOT NULL,
    item_configuracao   text,
    codigo_fechamento   text NOT NULL DEFAULT 'Não informado',
    aberto              timestamp without time zone NOT NULL,
    resolvido           timestamp without time zone,
    foi_resolvido       boolean NOT NULL,
    encerrado           timestamp without time zone NOT NULL,
    duracao_segundos    bigint NOT NULL,
    duracao_valida      boolean NOT NULL,
    aberto_por          text NOT NULL,
    status              text NOT NULL,
    entrou_kpi          boolean NOT NULL,
    kpi_violado         boolean,
    data_abertura       date NOT NULL,
    ano                 integer NOT NULL,
    mes                 integer NOT NULL,
    dia_semana          integer NOT NULL   -- convencao fixa: 0=segunda (pandas.dt.dayofweek)
);

CREATE INDEX IF NOT EXISTS ix_silver_incidentes_data_abertura
    ON silver.incidentes_tratados (data_abertura);

CREATE INDEX IF NOT EXISTS ix_silver_incidentes_prioridade
    ON silver.incidentes_tratados (prioridade);
