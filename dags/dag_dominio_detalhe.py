# =============================================================================
# dag_dominio_detalhe.py
#

# TEMPLATE — DAG Airflow para pipeline Medallion completo
#
# Orquestra as tasks do pipeline: extractor → loader Bronze →
# transformer Silver → loader Silver → transformer Gold → loader Gold.
#
# Compatível com o Airflow 2 de produção (VM + venv airflow-env).
# Baseado na estrutura dos DAGs em produção (ex.: etl_custo_anp_medio_por_regiao),
# com correções: retries com backoff, execution_timeout, destinatários de
# alerta via variável de ambiente (nunca e-mail pessoal hardcoded), sem
# código morto, dag_id idêntico ao nome do arquivo.
#
# Renomeie para: dag_{dominio}_{especificadores}.py
# Exemplos: dag_venda_protheus.py | dag_cadastro_filial.py
# REGRA: dag_id deve ser idêntico ao nome do arquivo (sem .py) — na hora do
# incidente, encontra-se o arquivo a partir do que aparece na UI do Airflow.
#
# IMPORTANTE: este arquivo orquestra scripts — não acessa dados diretamente.
# Nenhum import de pandas, flowrix, requests, dotenv ou conectores aqui.
# O .env é carregado pelo Flowrix dentro de cada script; load_dotenv() no DAG
# é inútil e roda a cada ciclo de parse do scheduler.
#
# MIGRAÇÃO AIRFLOW 3 (quando o container_airflow 3.0.6 entrar em produção):
#   1. BashOperator: airflow.operators.bash → airflow.providers.standard.operators.bash
#   2. schedule_interval= → schedule=
#   3. send_email_smtp (removido no 3.x) → SmtpNotifier do provider smtp
#      (exige conexão smtp_default configurada no cluster)
#   4. context['execution_date'] (removido) → context['logical_date']
#      (o fallback no callback abaixo já cobre as duas versões)
#   5. ETL_BASE_DIR passa a /opt/airflow/dags/{repo} (bind mount do container)
#      e a ativação do venv do host deixa de existir no bash_command
# =============================================================================

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.email import send_email_smtp

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

# Timezone de Brasília — o cron do schedule passa a valer em horário local,
# não em UTC. Sem isso, "0 6 * * *" roda às 03h da manhã.
TIMEZONE_LOCAL = pendulum.timezone("America/Sao_Paulo")

# Layout de produção (VM): scripts em /home/orchestrator/Petrobahia_GitLab/dags/{repo}
# e Python do venv do orquestrador. Ambos parametrizados por variável de
# ambiente para funcionar também em homologação/DR sem editar o DAG.
ETL_BASE_DIR  = os.getenv(
    'ETL_BASE_DIR',
    '/home/orchestrator/Petrobahia_GitLab/dags/etl_dominio_detalhe',
)
VENV_ACTIVATE = os.getenv('ETL_VENV_ACTIVATE', '/home/orchestrator/airflow-env/bin/activate')

# Destinatários de alerta — SEMPRE via variável de ambiente ou lista de
# distribuição. E-mail pessoal hardcoded morre silenciosamente quando a
# pessoa sai da empresa; alerta que ninguém lê é igual a não ter alerta.
ALERT_EMAILS = [
    email.strip()
    for email in os.getenv('ALERT_EMAILS', 'suporte.dados@petrobahia.com.br').split(',')
]

# Host externo do Airflow para os links de log nos e-mails de alerta
# (o log_url gerado internamente aponta para localhost).
AIRFLOW_HOST_EXTERNO = os.getenv('AIRFLOW_HOST_EXTERNO', '10.1.1.134')


def comando_etl(script_relativo):
    """Monta o bash_command padrão: ativa o venv e executa o script pelo
    caminho absoluto. Um único lugar para mudar quando o deploy mudar
    (ex.: migração para o container, onde o venv deixa de existir)."""
    return f'source {VENV_ACTIVATE} && python3 {ETL_BASE_DIR}/{script_relativo}'


def notificar_falha(context):
    """Callback executado automaticamente quando qualquer task falhar.

    Envia e-mail de alerta com link direto para o log da task.
    Referenciado em default_args['on_failure_callback'] — não chamar diretamente.
    """
    task_instance = context['task_instance']
    dag_id        = context['dag'].dag_id
    task_id       = task_instance.task_id
    # logical_date existe no Airflow >= 2.2 e é o nome que sobrevive no 3.x;
    # execution_date é o fallback para versões antigas.
    data_execucao = context.get('logical_date') or context.get('execution_date')
    log_url       = task_instance.log_url.replace('localhost', AIRFLOW_HOST_EXTERNO)

    send_email_smtp(
        to=ALERT_EMAILS,
        subject=f'[Airflow FALHA] {dag_id} | {task_id}',
        html_content=(
            f"<h3>Falha em task do Airflow</h3>"
            f"<p><b>DAG:</b> {dag_id}</p>"
            f"<p><b>Task:</b> {task_id}</p>"
            f"<p><b>Execução:</b> {data_execucao}</p>"
            f"<p><b>Host:</b> {task_instance.hostname}</p>"
            f"<p><b>Log:</b> <a href='{log_url}'>Ver log completo</a></p>"
        ),
    )


# Argumentos padrão herdados por todas as tasks do DAG.
# Sobrescreva por task apenas quando a regra realmente difere.
default_args = {
    'owner': 'dados',                     # time responsável — nunca o genérico 'airflow'
    'depends_on_past': False,             # não trava por falha de execução anterior
    'retries': 2,                         # falha transiente (rede, lock) não mata o run
    'retry_delay': timedelta(minutes=5),
    'retry_exponential_backoff': True,    # 1ª retry: 5m | 2ª retry: 10m
    'max_retry_delay': timedelta(minutes=30),
    'email_on_failure': False,            # o alerta é o callback custom abaixo
    'email_on_retry': False,
    'on_failure_callback': notificar_falha,
    # Mata task travada e libera o worker. Calibre por task quando o tempo
    # real observado justificar (regra prática: tempo observado × 2).
    'execution_timeout': timedelta(hours=2),
}

# =============================================================================
# DAG
# =============================================================================

with DAG(
    # REGRA: dag_id == nome do arquivo sem .py
    dag_id='dag_dominio_detalhe',
    default_args=default_args,
    description='Pipeline Medallion — domínio detalhe: Bronze → Silver → Gold',
    # Seg–sex às 06h (horário de Brasília, via start_date tz-aware).
    # Use None para disparo manual (pipelines sob demanda).
    schedule_interval='0 6 * * 1-5',
    start_date=pendulum.datetime(2024, 1, 1, tz=TIMEZONE_LOCAL),
    catchup=False,        # não reprocessa execuções passadas ao ativar a DAG
    max_active_runs=1,    # impede dois runs disputando DELETE/INSERT nas mesmas tabelas
    tags=['dominio', 'medallion'],
) as dag:

    # -------------------------------------------------------------------------
    # BRONZE — Extração e carga
    # -------------------------------------------------------------------------

    extrair = BashOperator(
        task_id='extractor_dominio_detalhe',
        bash_command=comando_etl('extractors/extractor_dominio_detalhe.py'),
    )

    # Se o extractor gravar dado não-tabular (ex.: bytes crus de API externa),
    # descomente o transformer Bronze — par do extractor_dominio_api_externa.py:
    # transformar_bronze = BashOperator(
    #     task_id='transformer_bronze_dominio_api',
    #     bash_command=comando_etl('transformers/transformer_bronze_dominio_api.py'),
    # )

    carregar_bronze = BashOperator(
        task_id='loader_bronze_dominio_detalhe',
        bash_command=comando_etl('loaders/loader_bronze_dominio_detalhe.py'),
    )

    # -------------------------------------------------------------------------
    # SILVER — Transformação e carga
    # -------------------------------------------------------------------------

    transformar_silver = BashOperator(
        task_id='transformer_silver_dominio_detalhe',
        bash_command=comando_etl('transformers/transformer_silver_dominio_detalhe.py'),
    )

    carregar_silver = BashOperator(
        task_id='loader_silver_dominio_detalhe',
        bash_command=comando_etl('loaders/loader_silver_dominio_detalhe.py'),
    )

    # -------------------------------------------------------------------------
    # GOLD — Transformação e carga
    # -------------------------------------------------------------------------

    transformar_gold = BashOperator(
        task_id='transformer_gold_dominio_detalhe',
        bash_command=comando_etl('transformers/transformer_gold_dominio_detalhe.py'),
    )

    carregar_gold = BashOperator(
        task_id='loader_gold_dominio_detalhe',
        bash_command=comando_etl('loaders/loader_gold_dominio_detalhe.py'),
    )

    # -------------------------------------------------------------------------
    # DEPENDÊNCIAS
    # Sequência obrigatória Bronze → Silver → Gold.
    # Nunca paralelize tasks do mesmo domínio — cada task depende do estado
    # produzido pela anterior. Paralelismo entre DAGs de domínios diferentes
    # é seguro e controlado pelo Airflow naturalmente.
    # task_id sempre igual ao nome do script (sem .py): rastreabilidade direta
    # da UI do Airflow para o arquivo no repositório.
    # -------------------------------------------------------------------------

    extrair >> carregar_bronze >> transformar_silver >> carregar_silver >> transformar_gold >> carregar_gold
