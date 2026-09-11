-- Reset total do ambiente de dados. Uso manual (nunca chamado pela DAG).
-- CASCADE remove tabelas, indices e o schema previsoes junto.
DROP SCHEMA IF EXISTS gold CASCADE;
DROP SCHEMA IF EXISTS silver CASCADE;
DROP SCHEMA IF EXISTS bronze CASCADE;
