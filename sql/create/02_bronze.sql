-- BRONZE: espelho fiel do LW-DATASET.xlsx.
-- Todas as colunas de negocio como text (DEC5) — nenhuma conversao de tipo aqui,
-- maxima tolerancia a inconsistencia da fonte. Sem PK/FK.
-- Nomes de coluna ja normalizados (snake_case, sem acento) pelo read_source().

CREATE TABLE IF NOT EXISTS bronze.incidentes_raw (
    numero              text,
    prioridade          text,
    produto             text,
    categoria           text,
    subcategoria        text,
    grupo_designado     text,
    item_configuracao   text,
    aberto              text,
    resolvido           text,
    encerrado           text,
    duracao_segundos    text,
    codigo_fechamento   text,
    descricao_resumida  text,
    solucao             text,
    aberto_por          text,
    incidente_pai       text,
    status              text,
    entrou_kpi          text,
    kpi_violado         text,
    carga_timestamp     timestamp without time zone NOT NULL DEFAULT now()
);
