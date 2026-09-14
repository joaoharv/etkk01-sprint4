-- SILVER: dados tratados e padronizados. Unica camada com decisao de qualidade.
-- Tipos nativos, PK natural (numero), nulos padronizados, flags e colunas de data
-- derivadas. Ver PLANO_IMPLEMENTACAO_SPRINT4.md Parte 10.
--
-- Desvio consciente em relacao a Parte 6 do plano: incluida a coluna
-- codigo_fechamento — necessaria para a tabela gold.incidentes_diario_codigo_fechamento
-- e para o Dashboard 3 (KPIs/SLA). Segue o mesmo padrao de nulo -> 'Não informado'.
--
-- Desvio consciente (Plano 2.1, Etapa 4): incluida a coluna descricao_resumida —
-- unica fonte de texto do modelo de classificacao de Prioridade (TF-IDF). Passthrough
-- puro: sem default, sem regra de qualidade, sem tratamento de nulo (fillna pertence
-- ao feature engineering do ML, nao a Silver — ver src/ml/features/prioridade_features.py,
-- Etapa 11).

CREATE TABLE IF NOT EXISTS silver.incidentes_tratados (
    numero              text PRIMARY KEY,
    prioridade          text NOT NULL,
    produto             text NOT NULL DEFAULT 'Não informado',
    categoria           text NOT NULL DEFAULT 'Não informado',
    subcategoria        text NOT NULL DEFAULT 'Não informado',
    grupo_designado     text NOT NULL,
    item_configuracao   text,
    descricao_resumida  text,
    codigo_fechamento   text NOT NULL DEFAULT 'Não informado',
    aberto              timestamp without time zone NOT NULL,
    resolvido           timestamp without time zone,
    foi_resolvido       boolean NOT NULL,
    encerrado           timestamp without time zone NOT NULL,
    duracao_segundos    bigint NOT NULL,
    duracao_valida      boolean NOT NULL,
    duracao_dias            double precision NOT NULL,  -- derivada de duracao_segundos, sem arredondar
    duracao_outlier_flag    boolean NOT NULL,            -- estatistico (> P99 dinamico); NAO e' erro nem regra de exclusao
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

-- Migracao idempotente para bancos ja existentes: create_schema roda este
-- arquivo a cada execucao da DAG (dags/pipeline_incidentes_ti.py), e
-- CREATE TABLE IF NOT EXISTS acima e' no-op quando a tabela ja existe.
-- Sem NOT NULL aqui de proposito: a tabela pode ja ter linhas no momento
-- deste ALTER; a task seguinte (transform_silver) faz TRUNCATE + INSERT full
-- load (src/db.py:truncate_insert) e repopula as duas colunas em todas as
-- linhas na MESMA execucao da DAG -- nao ha janela de dado incompleto.
-- ATENCAO: nao usar o caractere de porcentagem neste arquivo (nem em
-- comentario) -- psycopg2/SQLAlchemy o interpretam como placeholder de
-- parametro em exec_driver_sql() (ver sql/create/04_gold_core.sql).
ALTER TABLE silver.incidentes_tratados
    ADD COLUMN IF NOT EXISTS duracao_dias double precision;

ALTER TABLE silver.incidentes_tratados
    ADD COLUMN IF NOT EXISTS duracao_outlier_flag boolean;
