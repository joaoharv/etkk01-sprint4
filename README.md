# sprint4-incidentes-ti

Pipeline de dados de **incidentes de TI** em arquitetura **Medallion**, rodando
inteiramente em **Docker Compose**:

```
data/LW-DATASET.xlsx  →  Apache Airflow (ETL)  →  PostgreSQL [bronze → silver → gold]  →  Grafana
```

- **PostgreSQL 16** — banco único `incidentes_ti`, três schemas (`bronze`, `silver`, `gold`).
- **Apache Airflow 2.9.3** (LocalExecutor) — uma DAG que orquestra o ETL. A lógica fica em `src/`.
- **Grafana 11.1** — 5 dashboards sobre a camada Gold, provisionados automaticamente.

Fonte: `data/LW-DATASET.xlsx` — extração pontual e estática de **122.543 incidentes**
(abertura de 2023-01-02 a 2025-12-31). O pipeline é **full-load idempotente** — não há
ingestão incremental.

---

## Pré-requisitos

- **Docker Engine** + **Docker Compose v2** (`docker compose`, não `docker-compose`)
- ~2 GB de RAM livres para os containers
- (opcional) **GNU Make** para os atalhos `make ...`. No Windows: `choco install make`,
  ou use os comandos `docker compose` equivalentes mostrados abaixo.

---

## Subida do ambiente

```bash
git clone <repositorio>
cd sprint4-incidentes-ti
cp .env.example .env
```

Gere as chaves do Airflow e substitua no `.env` (`AIRFLOW_FERNET_KEY`, `AIRFLOW_SECRET_KEY`):

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_hex(32))"
```

Suba os serviços:

```bash
make up
# equivalente sem make (o compose.yaml da raiz inclui docker/docker-compose.yml
# e carrega o .env automaticamente):
# docker compose up -d --build
```

O primeiro `up` **compila a imagem do Airflow** e baixa as imagens base (~1,5 GB) —
pode levar alguns minutos. O Airflow leva ~40 s a mais para ficar `healthy` depois
que o container sobe.

Confirme que está tudo de pé:

```bash
make ps
# docker compose --env-file .env -f docker/docker-compose.yml ps
```

Os 3 serviços devem aparecer `healthy` / `running`.

| Serviço | URL | Credenciais padrão (desenvolvimento) |
|---|---|---|
| Airflow | http://localhost:8080 | `admin` / `admin` |
| Grafana | http://localhost:3000 | `admin` / `locaweb2024` |
| PostgreSQL | `localhost:5432` | `incidentes` / `incidentes_dev_pwd` (banco `incidentes_ti`) |

> A senha do Grafana **não pode ser `admin`** — o Grafana força a troca no primeiro
> login se for a padrão. O valor vem de `GRAFANA_ADMIN_PASSWORD` no `.env`.

> As credenciais acima são **de desenvolvimento**, documentadas no `.env.example`.
> Não use este `.env` em produção.

---

## Rodar o pipeline (DAG)

A DAG `pipeline_incidentes_ti` nasce **pausada**. Duas formas de executar:

**Pela linha de comando:**

```bash
make dag
# equivalente:
# docker compose --env-file .env -f docker/docker-compose.yml exec airflow-webserver airflow dags unpause pipeline_incidentes_ti
# docker compose --env-file .env -f docker/docker-compose.yml exec airflow-webserver airflow dags trigger pipeline_incidentes_ti
```

**Pela UI:** abra http://localhost:8080, ligue o toggle da DAG `pipeline_incidentes_ti` e clique ▶.

A DAG executa 5 tasks em sequência (~1–2 min):

```
create_schema → extract_bronze → transform_silver → transform_gold → validate_pipeline
```

`validate_pipeline` é o **gate**: se alguma contagem entre camadas não bater, a DAG falha.

Ao final:
- `bronze.incidentes_raw` = 122.543 linhas
- `silver.incidentes_tratados` = 122.543 linhas (0 nulo em `prioridade`, 0 duplicata de `numero`)
- 12 tabelas `gold.*` populadas; `gold.previsoes` vazia (reservada — ver abaixo)

---

## Dashboards (Grafana)

Abra http://localhost:3000 (`admin` / `admin`). O datasource `incidentes_ti` e os 5
dashboards já aparecem provisionados, **sem nenhum clique de configuração**:

| Dashboard | Foco |
|---|---|
| 01 · Visão Executiva | totais do período, taxa de resolução, % KPI violado, evolução diária |
| 02 · Incidentes (Operacional) | volume/dia, por prioridade, Team14 vs Outros, por status |
| 03 · KPIs / SLA | incidentes em KPI, taxa de violação no tempo, código de fechamento |
| 04 · Análise Temporal | por mês, por hora, por dia da semana, comparação ano a ano, tendência |
| 05 · Análises Operacionais | por grupo (17), por categoria, origem, código de fechamento |

Cada dashboard usa o seletor de intervalo global (padrão: 2023–2025). As queries leem
direto das tabelas `gold.*` — nenhuma agregação pesada em tempo de consulta.

---

## Testes

Testes de integração (rodam contra o banco real, **após** uma execução da DAG):

```bash
make test
# equivalente:
# docker compose --env-file .env -f docker/docker-compose.yml exec airflow-webserver \
#   sh -c 'cd /opt/airflow/project && pytest tests -v -p no:cacheprovider'
```

Verificam contagem entre camadas, ausência de nulos/duplicatas na Silver, consistência
Gold × Silver e `gold.previsoes` vazia.

---

## Comandos (`make`)

| Comando | O que faz |
|---|---|
| `make up` | sobe os 3 serviços (build se necessário) |
| `make dag` | despausa e dispara a DAG |
| `make dag-test` | roda a DAG de forma síncrona (debug, sem scheduler) |
| `make test` | roda os testes de integração |
| `make ps` / `make logs` | status / logs dos containers |
| `make shell` | shell no container do Airflow |
| `make db-check` | testa a conexão ao Postgres |
| `make down` | para os serviços (mantém os dados) |
| `make reset` | **apaga os volumes** e sobe do zero |

---

## Estrutura do projeto

```text
Makefile                  atalhos (up / dag / test / ...)
.env.example              variaveis de ambiente (copiar para .env)
docker/
  docker-compose.yml      Postgres + Airflow (init/webserver/scheduler) + Grafana
  airflow/Dockerfile      imagem do Airflow + dependencias do ETL
  postgres/init-airflow-db.sh   cria o banco de metadados do Airflow
dags/
  pipeline_incidentes_ti.py     DAG (so orquestra; chama src/)
src/
  db.py                   engine, run_sql_file, truncate_insert, read_table
  extract/read_source.py  le o Excel -> DataFrame (sem transformar)
  transform/clean_incidentes.py   regras de qualidade da Silver
  transform/aggregate_gold.py     agregacoes diarias da Gold
  load/load_{bronze,silver,gold}.py   full load por camada
  validation/checks.py    checagens entre camadas (gate da DAG)
config/logging.py         logger compartilhado
sql/
  create/01_schemas.sql .. 05_gold_extra.sql   DDL idempotente
  drop/drop_all.sql       reset total (manual)
grafana/
  provisioning/           datasource + provider de dashboards
  dashboards/*.json       os 5 dashboards
tests/                    pytest de integracao
data/LW-DATASET.xlsx      fonte
notebooks/eda.py          EDA das sprints 1/2 (fora do pipeline)
```

---

## Troubleshooting

| Sintoma | Causa / solução |
|---|---|
| `Error: Database is uninitialized and superuser password is not specified` (postgres unhealthy) | você rodou `docker compose -f docker/docker-compose.yml up` (o `.env` não é lido de `docker/`). Rode da **raiz**: `docker compose up -d` (usa o `compose.yaml` da raiz) ou `make up`. |
| DAG não dispara / "DagNotFound" logo após subir | o scheduler ainda não serializou a DAG. Aguarde ~30 s, ou rode `docker compose ... exec airflow-scheduler airflow dags reserialize`. |
| `airflow dags trigger` não faz nada | a DAG nasce pausada. `make dag` despausa antes; na UI, ligue o toggle. |
| Grafana "No data" nos painéis | rode a DAG primeiro (`make dag`); confira que o intervalo do dashboard cobre 2023–2025. |
| `make` não existe (Windows) | `choco install make` ou use os comandos `docker compose` equivalentes desta página. |
| Portas 5432 / 8080 / 3000 ocupadas | ajuste `POSTGRES_PORT_HOST` / `AIRFLOW_PORT_HOST` / `GRAFANA_PORT_HOST` no `.env`. |

---

## Notas

- **`notebooks/eda.py`** é a análise exploratória das sprints 1/2. Roda isolado
  (`python notebooks/eda.py`), **não faz parte do pipeline** de produção.
- **`gold.previsoes`** existe mas fica **vazia** nesta entrega. É a estrutura reservada
  para o modelo de ML de volume de incidentes (previsão D+1 / D+7) — fora do escopo
  da Sprint 4.
- Documentos de planejamento (análise do estado, plano de implementação, prompts) estão
  em `docs/` — são material de trabalho, não parte do runtime.

---

## Status da implementação

| Etapa | Descrição | Status |
|---|---|---|
| 1 | Base transversal (`logging`, `db`, `Makefile`) | ✅ |
| 2 | Schemas e tabelas SQL | ✅ |
| 3 | ETL Extract | ✅ |
| 4 | ETL Bronze | ✅ |
| 5 | ETL Silver | ✅ |
| 6 | ETL Gold (12 tabelas) | ✅ |
| 7 | Validação entre camadas | ✅ |
| 8 | DAG do Airflow | ✅ |
| 9 | Grafana — datasource | ✅ |
| 10 | Grafana — 5 dashboards | ✅ |
| 11 | Testes de integração (pytest) | ✅ |
| 12 | Documentação | ✅ |
| 13 | Teste de ponta a ponta | ✅ |
