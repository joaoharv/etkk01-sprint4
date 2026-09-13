---
name: pipeline-medallion
description: Arquitetura Medallion (Bronze/Silver/Gold) e criação de scripts ETL da PetroBahia. Aplica-se ao criar, estruturar ou modificar um extractor, transformer, loader ou DAG; ao decidir em qual camada uma transformação pertence; ao nomear buckets, arquivos parquet, tabelas ou colunas; ao finalizar um ETL criado a partir do template; ou quando o usuário pedir um pipeline novo, mesmo que não mencione "Medallion" explicitamente. Contém o pipeline completo de exemplo em references/exemplo_pipeline_completo.md.
---

# Pipeline Medallion — Bronze → Silver → Gold

## Visão geral do fluxo

```
extractor.py → MinIO (bronze-) → [transformer_bronze.py → MinIO (bronze-)] →
loader_bronze.py → MySQL (bronze_) →
transformer_silver.py → MinIO (silver-) → loader_silver.py → MySQL (silver_) →
transformer_gold.py → MinIO (gold-) → loader_gold.py → ClickHouse (gold_)
```

O MinIO é o **data stage transitório**. Nenhum dado fica apenas no MinIO — toda camada tem
destino final em banco. A ordem de promoção é **sempre Bronze → Silver → Gold**.

O `transformer_bronze` entre colchetes é **opcional**. O princípio é que a Bronze guarda o
dado **como a fonte entrega**: formato declarado pela fonte é preservado byte a byte, e o
extractor só escolhe o formato quando a fonte não declara nenhum.

| A fonte devolve | Extractor grava | `transformer_bronze`? |
| --- | --- | --- |
| DataFrame (`read_data` de banco) | `.parquet` | Não |
| Formato declarado: CSV, XML, XLSX, XLS, ODS | bytes, extensão da fonte | Não — `read_data()` lê pela extensão |
| Formato declarado: PDF ou binário | bytes `.pdf` / `.bin` | Sim |
| Sem formato declarado (JSON) + lista plana | `.parquet` | Não |
| Sem formato declarado (JSON) + aninhado | bytes `.json` | Sim |

JSON conta como "sem formato declarado" porque é o transporte padrão de API REST, não uma
escolha deliberada de formato de arquivo — só aí o extractor decide pelo conteúdo.

Materializar lista plana em parquet **não** viola a regra "extractor não transforma": nomes
e valores da fonte são preservados, é a mesma materialização que o `read_data()` faz num
extractor de banco. Achatar estrutura aninhada, sim, é interpretação — e por isso pertence
ao `transformer_bronze`. Independentemente do caminho, o Bronze entregue à Silver cumpre o
mesmo contrato: a Silver não precisa saber qual caminho o produziu.

## Responsabilidades por script

| Script | Responsabilidade | Lê de | Escreve em |
| --- | --- | --- | --- |
| `extractor_*.py` | Extrair dados brutos da fonte | Fonte (Protheus, API, etc.) | MinIO `bronze-` |
| `transformer_bronze_*.py` | Estruturar dados não tabulares | MinIO `bronze-` | MinIO `bronze-` |
| `loader_bronze_*.py` | Carga na Bronze | MinIO `bronze-` | MySQL `bronze_` |
| `transformer_silver_*.py` | Limpeza e padronização | MinIO `bronze-` ou MySQL `bronze_` | MinIO `silver-` |
| `loader_silver_*.py` | Carga na Silver | MinIO `silver-` | MySQL `silver_` |
| `transformer_gold_*.py` | Regras de negócio e agregações | MySQL `silver_` | MinIO `gold-` |
| `loader_gold_*.py` | Carga na Gold | MinIO `gold-` | ClickHouse `gold_` |

## Regras críticas por camada

- **[CRÍTICO] Extractor: nenhuma transformação.** Preserve os dados exatamente como vêm da
  fonte. Renomear, filtrar ou converter no Extractor corrompe a Bronze como cópia auditável,
  dificultando auditoria, debug e reprocessamento.
- **[CRÍTICO] Silver: deduplicação obrigatória** com `subset` explícito. A Silver é a camada
  de canonicalização; duplicatas multiplicam todos os joins da Gold. Nunca
  `drop_duplicates()` sem `subset`.
- **[CRÍTICO] Gold lendo de Bronze diretamente:** tolerado como exceção com alerta
  obrigatório. Explique os riscos (duplicatas, despadronização), recomende criar a Silver e
  ofereça ajuda. Se o usuário recusar, siga sem bloquear.
- **[CRÍTICO] Loader transformando dados:** o Loader apenas lê do MinIO e carrega no banco.
  Qualquer transformação no Loader viola a separação de responsabilidades.

## Ordem de operações do Loader

1. `read_data` — lê do bucket MinIO correspondente
2. **validar `df.empty`** — OBRIGATÓRIO, antes de qualquer escrita (ver checklist abaixo)
3. `write_data` — CREATE TABLE
4. `write_data` — DELETE ou TRUNCATE (para recarga completa)
5. `write_data` — INSERT do DataFrame no banco

A validação no passo 2 é o que impede o ghost run destrutivo: DELETE com
DataFrame vazio apaga a tabela de destino sem inserir nada, e o Airflow
marca a task como sucesso.

## Estrutura obrigatória de seções

Todo script segue seções nomeadas com comentários. Ausência ou ordem incorreta é **[IMPORTANTE]**.

**Extractor**
```python
# IMPORTS

# EXTRACTORS
# Extract | table_a
# Extract | table_b

# EXPORTS
# Create Bucket | bronze-pipeline-name
# Export | table_a
# Export | table_b
```

**Transformer**
```python
# IMPORTS

# EXTRACTORS
# Extract | table_a

# TRANSFORMERS
# Transform | Data Cleaning
# Transform | Rename
# Transform | Drop Duplicates
# Transform | Merge
# (demais transformações conforme necessidade)

# EXPORTS
# Create Bucket | silver-pipeline-name
# Export | table_c
```

**Loader**
```python
# IMPORTS

# EXTRACTORS
# Extract | table_c

# CREATE TABLE

# CLEAN TABLE

# LOAD TABLE
```

## Nomenclatura obrigatória

Qualquer violação é **[CRÍTICO]**. Sempre snake_case, sem abreviaturas.

| Elemento | Padrão | Exemplo |
| --- | --- | --- |
| Script extractor | `extractor_{domínio}_{especificadores}` | `extractor_custo_resumo.py` |
| Script transformer / loader | `{funcao}_{camada}_{domínio}_{especificadores}` | `transformer_silver_custo_detalhe.py` |
| Bucket MinIO | `{camada}-{domínio}-{especificador}` | `bronze-orcado-realizado` |
| Arquivo parquet | `{camada}_{tabela}.parquet` | `bronze_centro_custo.parquet` |
| Tabela MySQL Bronze/Silver | `{camada}_{domínio}_{especificador}` | `silver_centro_custo` |
| Tabela ClickHouse Gold | `gold_{domínio}_{especificador}` | `gold_custo_por_centro` |

**Tabelas:** `{camada}_{domínio}_{especificador_1}_{especificador_2}...` — primeiro segmento
após o prefixo é o domínio de negócio; especificadores do mais geral ao mais específico.
Válidos: `silver_venda_anp`, `gold_margem_por_filial`. Inválidos: `silver_vnd_anp`
(abreviatura), `gold_CMV` (fora de snake_case), `tabela_vendas` (sem prefixo).

**Colunas Silver e Gold:** `{conceito}_{especificador_1}...` — primeiro segmento é o conceito
semântico (`valor_`, `codigo_`, `data_`, `nome_`, `percentual_`, `flag_`...). Proibido usar o
domínio da tabela como prefixo das colunas. Válidos: `codigo_filial`, `valor_venda`,
`data_referencia`. Inválidos: `cod_filial` (abreviatura), `NomeCliente` (fora de snake_case),
`venda_valor` (domínio antes do conceito).

A lista completa de abreviaturas proibidas é a do CLAUDE.md, regra 6.

**DAGs:** arquivo `dag_{domínio}_{especificadores}.py`, e **dag_id idêntico ao nome
do arquivo** (sem `.py`) — ver a seção "DAG de orquestração" abaixo.

## Validações obrigatórias — checklist por tipo de script

**Extractor e Transformer (após todo `read_data`):**
```python
df = read_data(...)                       # leitura da fonte
if df.empty:                              # OBRIGATÓRIO — nunca omitir
    raise ValueError(
        "[Extract] nome_tabela retornou DataFrame vazio. "
        "Verifique a query, os filtros e a disponibilidade da fonte."
    )
print(f"[Extract] nome_tabela: {len(df)} registros")
```

**Leitura em bytes (`raw=True` ou `.pdf`) — mesma regra, guarda diferente:**
```python
conteudo = read_data(bucket=BUCKET, object_name=ARQUIVO, raw=True)
if not conteudo:                          # OBRIGATÓRIO — bytes vazios
    raise ValueError(
        "[Extract] arquivo bruto vazio. Verifique se o extractor executou."
    )
print(f"[Extract] {len(conteudo)} bytes lidos")
```

**Transformer Silver (dedup — com subset explícito):**
```python
CHAVE_PRIMARIA = ['codigo_filial', 'numero_pedido']  # constante no topo
linhas_antes = len(df)
df = df.drop_duplicates(subset=CHAVE_PRIMARIA, keep='last')
print(f"[Dedup] {linhas_antes} → {len(df)} registros")
```

**Loader (validação ANTES do DELETE/TRUNCATE):**
```python
df = read_data(bucket=BUCKET, object_name=ARQUIVO)
if df.empty:                              # OBRIGATÓRIO antes do DELETE
    raise ValueError(
        "[Extract] Parquet vazio — DELETE e INSERT não executados. "
        "Verifique o transformer correspondente."
    )
write_data('mysql', CREATE_TABLE_SQL)     # CREATE TABLE primeiro
write_data('mysql', DELETE_SQL)           # DELETE só depois da validação
write_data('mysql', df, table=TABELA)     # INSERT
```

> **Por que a validação é obrigatória no loader:** executar DELETE com DataFrame
> vazio apaga toda a tabela de destino sem inserir nada. O Airflow marca a task
> como sucesso. O dado some silenciosamente até alguém perceber no relatório.

## DAG de orquestração

O DAG **orquestra** — nunca acessa dados. Proibido no arquivo da DAG (o CI bloqueia):
`pandas`, `flowrix`, `requests`, `dotenv` e conectores nativos. Lógica de dados ou de
rede pertence a um script versionado chamado via `BashOperator`.

Convenções (o template `dags/dag_dominio_detalhe.py` demonstra todas):
- **`dag_id` idêntico ao nome do arquivo** (sem `.py`) — na hora do incidente,
  encontra-se o arquivo a partir da UI do Airflow. O CI aponta divergência.
- **`task_id` idêntico ao nome do script** (sem `.py`) — rastreabilidade direta.
- `start_date` timezone-aware com `pendulum.timezone("America/Sao_Paulo")` — sem
  isso o cron roda em UTC.
- `default_args` com `retries` + backoff, `execution_timeout` e `owner` do time
  (nunca o genérico `'airflow'`).
- `catchup=False` e `max_active_runs=1` — dois runs simultâneos do mesmo domínio
  disputam DELETE/INSERT nas mesmas tabelas.
- Alerta de falha com o endereço da área **somado** aos destinatários —
  `ALERT_EMAILS` acrescenta, nunca substitui (o CI aponta as duas violações:
  e-mail pessoal hardcoded e endereço da área só como fallback):

  ```python
  DESTINATARIO_GARANTIDO = 'suporte.dados@petrobahia.com.br'

  ALERT_EMAILS = sorted({
      *(email.strip() for email in os.getenv('ALERT_EMAILS', '').split(',') if email.strip()),
      DESTINATARIO_GARANTIDO,
  })
  ```

  Com o endereço da área no fallback do `getenv`, definir `ALERT_EMAILS` com um
  endereço pessoal tira a área do alerta sem erro e sem aviso — e, como a
  variável é global ao ambiente, o ajuste feito para um pipeline muda o
  destinatário de todos.
- Encadeamento sequencial Bronze → Silver → Gold; nunca paralelize tasks do
  mesmo domínio.
- Compatível com o Airflow 2 de produção; os deltas da futura migração para o
  Airflow 3 estão documentados no cabeçalho do template.

## Templates canônicos

Scripts de referência na **raiz deste repositório**:
- `extractors/extractor_dominio_detalhe.py` — fonte interna (Protheus/MySQL)
- `extractors/extractor_dominio_api_externa.py` — API REST com `declare_source`; preserva o formato declarado pela fonte e decide entre parquet e bytes quando não há formato declarado
- `transformers/transformer_bronze_dominio_api.py` — bytes crus → parse + parquet; **opcional**, só quando o Bronze ficou em formato que o `read_data()` não abre direto (JSON aninhado, PDF)
- `transformers/transformer_silver_dominio_detalhe.py` — limpeza + padronização + dedup
- `transformers/transformer_gold_dominio_detalhe.py` — regras de negócio + agregações
- `loaders/loader_bronze_dominio_detalhe.py` — carga full → MySQL bronze_ (DDL espelha a fonte)
- `loaders/loader_silver_dominio_detalhe.py` — carga full → MySQL silver_
- `loaders/loader_gold_dominio_detalhe.py` — full + variante incremental → ClickHouse gold_
- `dags/dag_dominio_detalhe.py` — DAG Airflow do pipeline completo

Parta sempre do template correspondente — nunca de um script de produção existente.

## Finalização do ETL (obrigatório antes do merge final)

Ao concluir um ETL criado a partir do template:

1. **Apague os placeholders não utilizados** — todo arquivo `*dominio_detalhe*` /
   `*dominio_api*` restante (scripts e DAG). O CI bloqueia placeholders em
   repositório que já tem scripts reais.
2. **Substitua o README** — preencha o `README_TEMPLATE.md` com os dados do
   projeto e renomeie: `git mv README_TEMPLATE.md README.md`. O CI aponta
   README de template remanescente.
3. **Adapte os testes** — renomeie `tests/test_transformer_silver_dominio_detalhe.py`
   para o seu domínio e ajuste as fixtures do `conftest.py` (o helper
   `constantes_do_script` já encontra o transformer real via glob). Mantenha
   `tests/test_check_etl_standards.py` — é o self-test do verificador, agnóstico
   ao domínio.

## Exemplo completo

Ao criar um pipeline novo ou um script de qualquer camada, leia
`references/exemplo_pipeline_completo.md` — pipeline real Orçado x Realizado por Centro de
Custo, do Protheus ao ClickHouse, com os 6 scripts canônicos. Use-o como gabarito de
estrutura, nomenclatura e validações.
