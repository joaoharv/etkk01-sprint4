# sprint4-incidentes-ti

Pipeline de dados de incidentes de TI (arquitetura Medallion) rodando inteiramente
em Docker Compose: **PostgreSQL** (bronze/silver/gold) + **Apache Airflow**
(orquestracao ETL) + **Grafana** (dashboards).

Fonte: `data/LW-DATASET.xlsx` — extracao pontual com 122.543 incidentes.

## Status da implementacao

| Fase | Descricao | Status |
|---|---|---|
| 1 | Estrutura de diretorios e configuracao base | concluida |
| 2 | Infraestrutura Docker (Postgres + Airflow + Grafana) | concluida |
| 3 | Schemas e tabelas SQL | pendente |
| 4 | ETL Bronze | pendente |
| 5 | ETL Silver | pendente |
| 6 | ETL Gold | pendente |
| 7 | DAG do Airflow | pendente |
| 8 | Provisionamento do Grafana | pendente |
| 9 | Testes (pytest) | pendente |
| 10 | Documentacao completa | pendente |
| 11 | Teste de ponta a ponta | pendente |

## Pre-requisitos

- Docker Engine + Docker Compose v2
- ~2 GB de RAM livres para os containers

## Subida rapida

```bash
cp .env.example .env
# gere e substitua AIRFLOW_FERNET_KEY e AIRFLOW_SECRET_KEY no .env
docker compose --env-file .env -f docker/docker-compose.yml up -d
```

| Servico | URL | Credenciais padrao (dev) |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Grafana | http://localhost:3000 | admin / admin |
| PostgreSQL | localhost:5432 | incidentes / incidentes_dev_pwd |

> A secao completa de execucao (disparo da DAG, validacoes, prints dos dashboards)
> sera preenchida na Fase 10.

## Estrutura do projeto

```text
docker/    infraestrutura (compose + Dockerfile do Airflow + init do Postgres)
dags/      DAG do Airflow (apenas orquestracao)
src/       logica de ETL (extract / transform / load / validation)
sql/       scripts de criacao e remocao de schemas e tabelas
grafana/   provisionamento de datasource e dashboards
config/    configuracao compartilhada (logging)
tests/     testes de integracao (pytest)
data/      arquivo de origem (LW-DATASET.xlsx)
```
