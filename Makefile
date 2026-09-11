# Atalhos do projeto sprint4-incidentes-ti.
# Requer GNU Make. No Windows: instale via `choco install make` ou use o Git Bash
# com make, ou rode os comandos equivalentes listados no README.

# compose.yaml (raiz) inclui docker/docker-compose.yml e carrega o .env sozinho.
COMPOSE = docker compose
DAG     = pipeline_incidentes_ti

.DEFAULT_GOAL := help
.PHONY: help up down reset dag logs ps shell db-check test

help:  ## Lista os alvos disponiveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up:  ## Sobe Postgres + Airflow + Grafana (build se necessario)
	$(COMPOSE) up -d --build
	@echo "Airflow: http://localhost:8080   Grafana: http://localhost:3000"

down:  ## Para os servicos (mantem os volumes/dados)
	$(COMPOSE) down

reset:  ## Derruba tudo INCLUSIVE os volumes e sobe de novo do zero
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build

dag:  ## Despausa e dispara a DAG do pipeline (execucao via scheduler)
	$(COMPOSE) exec airflow-webserver airflow dags unpause $(DAG)
	$(COMPOSE) exec airflow-webserver airflow dags trigger $(DAG)

dag-test:  ## Roda a DAG inteira de forma sincrona (sem scheduler), util para debug
	$(COMPOSE) exec airflow-webserver airflow dags test $(DAG)

ps:  ## Status dos containers
	$(COMPOSE) ps

logs:  ## Segue os logs de todos os servicos
	$(COMPOSE) logs -f

shell:  ## Abre um shell no container do Airflow (com src/ montado)
	$(COMPOSE) exec airflow-webserver bash

db-check:  ## Testa a conexao ao Postgres a partir do container
	$(COMPOSE) exec airflow-webserver python -c "from src.db import get_engine; get_engine().connect().close(); print('conexao OK')"

test:  ## Roda os testes de integracao dentro do container
	$(COMPOSE) exec airflow-webserver sh -c 'cd /opt/airflow/project && pytest tests -v --tb=short -p no:cacheprovider'
