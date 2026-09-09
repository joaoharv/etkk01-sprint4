# Exemplo de Pipeline Completo — Orçado x Realizado por Centro de Custo

Fonte: MySQL Protheus | Destino: ClickHouse Gold

## Visão geral

```
extractor_centro_custo.py
    → MinIO: bronze-orcado-realizado / bronze_centro_custo.parquet
    → MinIO: bronze-orcado-realizado / bronze_orcado.parquet

loader_bronze_centro_custo.py
    → MySQL: bronze_centro_custo
    → MySQL: bronze_orcado

transformer_silver_orcado_realizado.py
    → MinIO: silver-orcado-realizado / silver_centro_custo.parquet
    → MinIO: silver-orcado-realizado / silver_orcado.parquet

loader_silver_orcado_realizado.py
    → MySQL: silver_centro_custo
    → MySQL: silver_orcado

transformer_gold_custo_por_centro.py
    → MinIO: gold-custo-realizado / gold_custo_por_centro.parquet

loader_gold_custo_por_centro.py
    → ClickHouse: gold_custo_por_centro
```

## 1. Extractor — extractor_centro_custo.py

```python
# IMPORTS
from flowrix import read_data, write_data

QUERY_CENTRO_CUSTO = """
    SELECT
        CTT_CUSTO,
        CTT_DESC01,
        CTT_DESC02,
        D_E_L_E_T_
    FROM CTT010
    WHERE D_E_L_E_T_ <> '*'
"""

QUERY_ORCADO = """
    SELECT
        CT2_FILIAL,
        CT2_CONTA,
        CT2_CCUSTO,
        CT2_MES,
        CT2_VALOR,
        D_E_L_E_T_
    FROM CT2010
    WHERE D_E_L_E_T_ <> '*'
"""

BUCKET_BRONZE = 'bronze-orcado-realizado'

# EXTRACTORS
# Extract | centro_custo
df_centro_custo = read_data('protheus', QUERY_CENTRO_CUSTO)
if df_centro_custo.empty:
    raise ValueError("[Extract] centro_custo retornou DataFrame vazio. Verifique a query e a fonte.")
print(f"[Extract] centro_custo: {len(df_centro_custo)} registros")

# Extract | orcado
df_orcado = read_data('protheus', QUERY_ORCADO)
if df_orcado.empty:
    raise ValueError("[Extract] orcado retornou DataFrame vazio. Verifique a query e a fonte.")
print(f"[Extract] orcado: {len(df_orcado)} registros")

# EXPORTS
# Create Bucket | bronze-orcado-realizado
write_data('minio', f'CREATE BUCKET {BUCKET_BRONZE}')

# Export | bronze_centro_custo
write_data(df_centro_custo, bucket=BUCKET_BRONZE, object_name='bronze_centro_custo.parquet')
print(f"[Export] bronze_centro_custo.parquet exportado.")

# Export | bronze_orcado
write_data(df_orcado, bucket=BUCKET_BRONZE, object_name='bronze_orcado.parquet')
print(f"[Export] bronze_orcado.parquet exportado.")
```

O que este script demonstra: constantes nomeadas no topo, validação de DataFrame vazio com
`raise` imediatamente após **cada** `read_data()`, log de volume em cada passo,
**nenhuma transformação** (dados brutos da fonte).

## 2. Loader Bronze — loader_bronze_centro_custo.py

```python
# IMPORTS
from flowrix import read_data, write_data

BUCKET_BRONZE = 'bronze-orcado-realizado'

# EXTRACTORS
# Extract | bronze_centro_custo
df_centro_custo = read_data(bucket=BUCKET_BRONZE, object_name='bronze_centro_custo.parquet')
if df_centro_custo.empty:
    raise ValueError(
        "[Extract] bronze_centro_custo.parquet vazio — DELETE e INSERT não executados. "
        "Verifique se o extractor rodou com sucesso."
    )
print(f"[Extract] bronze_centro_custo: {len(df_centro_custo)} registros")

# Extract | bronze_orcado
df_orcado = read_data(bucket=BUCKET_BRONZE, object_name='bronze_orcado.parquet')
if df_orcado.empty:
    raise ValueError(
        "[Extract] bronze_orcado.parquet vazio — DELETE e INSERT não executados. "
        "Verifique se o extractor rodou com sucesso."
    )
print(f"[Extract] bronze_orcado: {len(df_orcado)} registros")

# CREATE TABLE
write_data('mysql', """
    CREATE TABLE IF NOT EXISTS bronze_centro_custo (
        CTT_CUSTO   VARCHAR(15),
        CTT_DESC01  VARCHAR(40),
        CTT_DESC02  VARCHAR(40),
        D_E_L_E_T_  CHAR(1),
        data_carga  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

write_data('mysql', """
    CREATE TABLE IF NOT EXISTS bronze_orcado (
        CT2_FILIAL  VARCHAR(8),
        CT2_CONTA   VARCHAR(20),
        CT2_CCUSTO  VARCHAR(15),
        CT2_MES     CHAR(2),
        CT2_VALOR   DECIMAL(18, 6),
        D_E_L_E_T_  CHAR(1),
        data_carga  DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")

# CLEAN TABLE
# Seguro: os DataFrames já foram validados como não-vazios acima.
write_data('mysql', 'DELETE FROM bronze_centro_custo')
write_data('mysql', 'DELETE FROM bronze_orcado')

# LOAD TABLE
write_data('mysql', df_centro_custo, table='bronze_centro_custo')
print(f"[Load] bronze_centro_custo: {len(df_centro_custo)} registros carregados.")

write_data('mysql', df_orcado, table='bronze_orcado')
print(f"[Load] bronze_orcado: {len(df_orcado)} registros carregados.")
```

A ordem é inegociável: **read → validar → CREATE → DELETE → INSERT**. Se a validação viesse
depois do DELETE, um parquet vazio apagaria a tabela sem carregar nada e o Airflow marcaria
sucesso — ghost run destrutivo e silencioso.

## 3. Transformer Silver — transformer_silver_orcado_realizado.py

```python
# IMPORTS
from flowrix import read_data, write_data

BUCKET_BRONZE = 'bronze-orcado-realizado'
BUCKET_SILVER = 'silver-orcado-realizado'

COLUNAS_CENTRO_CUSTO = {
    'CTT_CUSTO':  'codigo_centro_custo',
    'CTT_DESC01': 'descricao_centro_custo',
    'CTT_DESC02': 'descricao_complementar_centro_custo',
}

COLUNAS_ORCADO = {
    'CT2_FILIAL': 'codigo_filial',
    'CT2_CONTA':  'codigo_conta',
    'CT2_CCUSTO': 'codigo_centro_custo',
    'CT2_MES':    'mes_referencia',
    'CT2_VALOR':  'valor_orcado',
}

CHAVE_CENTRO_CUSTO = ['codigo_centro_custo']
CHAVE_ORCADO       = ['codigo_filial', 'codigo_conta', 'codigo_centro_custo', 'mes_referencia']

# EXTRACTORS
# Extract | bronze_centro_custo
df_centro_custo = read_data(bucket=BUCKET_BRONZE, object_name='bronze_centro_custo.parquet')
if df_centro_custo.empty:
    raise ValueError("[Extract] bronze_centro_custo.parquet vazio. Verifique o loader bronze.")
print(f"[Extract] bronze_centro_custo: {len(df_centro_custo)} registros")

# Extract | bronze_orcado
df_orcado = read_data(bucket=BUCKET_BRONZE, object_name='bronze_orcado.parquet')
if df_orcado.empty:
    raise ValueError("[Extract] bronze_orcado.parquet vazio. Verifique o loader bronze.")
print(f"[Extract] bronze_orcado: {len(df_orcado)} registros")

# TRANSFORMERS

# Transform | Rename | centro_custo
df_centro_custo = df_centro_custo.rename(columns=COLUNAS_CENTRO_CUSTO)

# Transform | Rename | orcado
df_orcado = df_orcado.rename(columns=COLUNAS_ORCADO)

# Transform | Data Cleaning | centro_custo
df_centro_custo['codigo_centro_custo']                 = df_centro_custo['codigo_centro_custo'].str.strip()
df_centro_custo['descricao_centro_custo']              = df_centro_custo['descricao_centro_custo'].str.strip()
df_centro_custo['descricao_complementar_centro_custo'] = df_centro_custo['descricao_complementar_centro_custo'].str.strip()

# Transform | Data Cleaning | orcado
df_orcado['codigo_centro_custo'] = df_orcado['codigo_centro_custo'].str.strip()
df_orcado['codigo_filial']       = df_orcado['codigo_filial'].str.strip()
df_orcado['valor_orcado']        = df_orcado['valor_orcado'].astype(float)
df_orcado['mes_referencia']      = df_orcado['mes_referencia'].astype(str).str.zfill(2)

# Transform | Drop Duplicates | centro_custo
linhas_antes = len(df_centro_custo)
df_centro_custo = df_centro_custo.drop_duplicates(subset=CHAVE_CENTRO_CUSTO, keep='last')
print(f"[Dedup] centro_custo: {linhas_antes} → {len(df_centro_custo)} registros")

# Transform | Drop Duplicates | orcado
linhas_antes = len(df_orcado)
df_orcado = df_orcado.drop_duplicates(subset=CHAVE_ORCADO, keep='last')
print(f"[Dedup] orcado: {linhas_antes} → {len(df_orcado)} registros")

# Transform | Null Validation | centro_custo
nulos = df_centro_custo[CHAVE_CENTRO_CUSTO].isnull().sum()
if nulos.any():
    raise ValueError(f"Nulos em chave primária de centro_custo:\n{nulos[nulos > 0]}")

# Transform | Null Validation | orcado
nulos = df_orcado[CHAVE_ORCADO].isnull().sum()
if nulos.any():
    raise ValueError(f"Nulos em chave primária de orcado:\n{nulos[nulos > 0]}")

# EXPORTS
# Create Bucket | silver-orcado-realizado
write_data('minio', f'CREATE BUCKET {BUCKET_SILVER}')

# Export | silver_centro_custo
write_data(df_centro_custo, bucket=BUCKET_SILVER, object_name='silver_centro_custo.parquet')
print(f"[Export] silver_centro_custo.parquet: {len(df_centro_custo)} registros")

# Export | silver_orcado
write_data(df_orcado, bucket=BUCKET_SILVER, object_name='silver_orcado.parquet')
print(f"[Export] silver_orcado.parquet: {len(df_orcado)} registros")
```

## 4. Loader Silver — loader_silver_orcado_realizado.py

```python
# IMPORTS
from flowrix import read_data, write_data

BUCKET_SILVER = 'silver-orcado-realizado'

# EXTRACTORS
# Extract | silver_centro_custo
df_centro_custo = read_data(bucket=BUCKET_SILVER, object_name='silver_centro_custo.parquet')
if df_centro_custo.empty:
    raise ValueError(
        "[Extract] silver_centro_custo.parquet vazio — DELETE e INSERT não executados. "
        "Verifique o transformer silver."
    )
print(f"[Extract] silver_centro_custo: {len(df_centro_custo)} registros")

# Extract | silver_orcado
df_orcado = read_data(bucket=BUCKET_SILVER, object_name='silver_orcado.parquet')
if df_orcado.empty:
    raise ValueError(
        "[Extract] silver_orcado.parquet vazio — DELETE e INSERT não executados. "
        "Verifique o transformer silver."
    )
print(f"[Extract] silver_orcado: {len(df_orcado)} registros")

# CREATE TABLE
write_data('mysql', """
    CREATE TABLE IF NOT EXISTS silver_centro_custo (
        codigo_centro_custo                  VARCHAR(15)  NOT NULL,
        descricao_centro_custo               VARCHAR(40),
        descricao_complementar_centro_custo  VARCHAR(40),
        data_carga                           DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (codigo_centro_custo)
    )
""")

write_data('mysql', """
    CREATE TABLE IF NOT EXISTS silver_orcado (
        codigo_filial        VARCHAR(8)   NOT NULL,
        codigo_conta         VARCHAR(20)  NOT NULL,
        codigo_centro_custo  VARCHAR(15)  NOT NULL,
        mes_referencia       CHAR(2)      NOT NULL,
        valor_orcado         DECIMAL(18,2),
        data_carga           DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (codigo_filial, codigo_conta, codigo_centro_custo, mes_referencia)
    )
""")

# CLEAN TABLE
# Seguro: os DataFrames já foram validados como não-vazios acima.
write_data('mysql', 'DELETE FROM silver_centro_custo')
write_data('mysql', 'DELETE FROM silver_orcado')

# LOAD TABLE
write_data('mysql', df_centro_custo, table='silver_centro_custo')
print(f"[Load] silver_centro_custo: {len(df_centro_custo)} registros carregados.")

write_data('mysql', df_orcado, table='silver_orcado')
print(f"[Load] silver_orcado: {len(df_orcado)} registros carregados.")
```

## 5. Transformer Gold — transformer_gold_custo_por_centro.py

```python
# IMPORTS
from flowrix import read_data, write_data

BUCKET_GOLD = 'gold-custo-realizado'

QUERY_ORCADO_CONSOLIDADO = """
    SELECT
        o.codigo_filial,
        o.codigo_centro_custo,
        c.descricao_centro_custo,
        o.mes_referencia,
        SUM(o.valor_orcado) AS valor_orcado_total
    FROM silver_orcado o
    LEFT JOIN silver_centro_custo c
        ON o.codigo_centro_custo = c.codigo_centro_custo
    GROUP BY
        o.codigo_filial,
        o.codigo_centro_custo,
        c.descricao_centro_custo,
        o.mes_referencia
"""

# EXTRACTORS
# Extract | silver_orcado consolidado por centro de custo
df_custo_por_centro = read_data('mysql', QUERY_ORCADO_CONSOLIDADO)
if df_custo_por_centro.empty:
    raise ValueError("Query Gold retornou vazia. Verifique se as tabelas Silver foram carregadas.")
print(f"[Extract] custo_por_centro: {len(df_custo_por_centro)} registros")

# TRANSFORMERS

# Transform | Null Validation
# descricao_centro_custo pode ser nulo em caso de join sem correspondência — logar apenas
centros_sem_descricao = df_custo_por_centro['descricao_centro_custo'].isnull().sum()
if centros_sem_descricao > 0:
    print(f"[Warning] {centros_sem_descricao} centros sem descrição após join com silver_centro_custo.")

# Transform | Data Cleaning
df_custo_por_centro['descricao_centro_custo'] = df_custo_por_centro['descricao_centro_custo'].fillna('SEM DESCRIÇÃO')
df_custo_por_centro['valor_orcado_total']     = df_custo_por_centro['valor_orcado_total'].round(2)

# EXPORTS
# Create Bucket | gold-custo-realizado
write_data('minio', f'CREATE BUCKET {BUCKET_GOLD}')

# Export | gold_custo_por_centro
write_data(df_custo_por_centro, bucket=BUCKET_GOLD, object_name='gold_custo_por_centro.parquet')
print(f"[Export] gold_custo_por_centro.parquet: {len(df_custo_por_centro)} registros")
```

## 6. Loader Gold — loader_gold_custo_por_centro.py

```python
# IMPORTS
from flowrix import read_data, write_data

BUCKET_GOLD = 'gold-custo-realizado'

# EXTRACTORS
# Extract | gold_custo_por_centro
df_custo_por_centro = read_data(bucket=BUCKET_GOLD, object_name='gold_custo_por_centro.parquet')
if df_custo_por_centro.empty:
    raise ValueError(
        "[Extract] gold_custo_por_centro.parquet vazio — TRUNCATE e INSERT não executados. "
        "Verifique o transformer gold."
    )
print(f"[Extract] gold_custo_por_centro: {len(df_custo_por_centro)} registros")

# CREATE TABLE
write_data('clickhouse', """
    CREATE TABLE IF NOT EXISTS gold_custo_por_centro (
        codigo_filial          String,
        codigo_centro_custo    String,
        descricao_centro_custo String,
        mes_referencia         String,
        valor_orcado_total     Float64
    )
    ENGINE = MergeTree()
    ORDER BY (codigo_filial, codigo_centro_custo, mes_referencia)
""")

# CLEAN TABLE
# Seguro: o DataFrame já foi validado como não-vazio acima.
write_data('clickhouse', 'TRUNCATE TABLE gold_custo_por_centro')

# LOAD TABLE
write_data('clickhouse', df_custo_por_centro, table='gold_custo_por_centro')
print(f"[Load] gold_custo_por_centro: {len(df_custo_por_centro)} registros carregados.")
```

## O que este pipeline demonstra

| Princípio | Onde aparece |
| --- | --- |
| Seções nomeadas obrigatórias | Todos os scripts |
| Constantes no topo | Queries e nomes de bucket como constantes nomeadas |
| Validação de DataFrame vazio | Todos os scripts, imediatamente após **todo** read_data |
| Validação ANTES do DELETE/TRUNCATE | Loaders Bronze, Silver e Gold (read → validar → CREATE → limpar → INSERT) |
| Validação de nulos antes da carga | Transformer Silver |
| Deduplicação com subset explícito | Transformer Silver |
| Log de volume em cada etapa | Todos os scripts |
| Join com how e on explícitos | Transformer Gold (na query SQL) |
| snake_case sem abreviaturas | Todas as colunas Silver e Gold |
| Nenhum conector nativo | Apenas read_data e write_data do Flowrix |
| Nenhuma transformação no Extractor | Extractor apenas extrai e exporta bruto |
| Promoção correta Bronze → Silver → Gold | Ordem do pipeline |
| Scripts lineares, sem `if __name__ == "__main__"` | Execução é sempre `python script.py` via BashOperator |
