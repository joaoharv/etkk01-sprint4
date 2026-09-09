---
name: revisao-etl
description: Fluxo de revisão de código ETL da PetroBahia, classificação de severidade e catálogo de situações perigosas em pandas/ETL. Aplica-se sempre que o usuário pedir para revisar, auditar, corrigir, avaliar qualidade ou "dar uma olhada" em um script ETL (extractor, transformer, loader) ou DAG, ou antes de analisar código de pipeline existente para modificá-lo.
---

# Revisão de Código ETL

## Fluxo de revisão (na ordem)

1. Identifique a camada pelo nome do bucket, arquivo ou script
2. Verifique a estrutura de seções (`# IMPORTS`, `# EXTRACTORS`, `# TRANSFORMERS`, `# EXPORTS` / `# CREATE TABLE` / `# CLEAN TABLE` / `# LOAD TABLE`)
3. Verifique a corretude do uso do Flowrix (imports, nomes de fonte, parâmetros)
4. Verifique se fontes externas têm `declare_source()` obrigatório
5. Verifique se há conectores nativos sendo usados diretamente
6. Verifique `load_dotenv`: permitido **apenas** em extractors externos (`declare_source` presente, `read_data` ausente). Em qualquer outro contexto é legado — o Flowrix carrega `.env` automaticamente.
7. Avalie aderência à camada Medallion (Extractor não transforma, Loader não transforma, Silver deduplica, promoção Bronze → Silver → Gold)
8. Verifique nomenclatura de scripts, buckets, arquivos, tabelas e colunas
9. Avalie qualidade e simplicidade do código Python
10. Liste os problemas **numerados e classificados por severidade**
11. Explique cada problema com justificativa técnica
12. Pergunte: "Deseja que eu aplique todas as correções ou prefere revisar uma por uma?"

## CI vs revisão humana

Antes de revisar manualmente, rode `python scripts/check_etl_standards.py` — as
regras que o CI já bloqueia estão listadas no CLAUDE.md (seção CI/CD). Ao listar
os problemas, marque quais o CI pega automaticamente e concentre a revisão humana
no que ele **não** cobre: transformação em extractor/loader, ordem das operações
no loader (validar ANTES do DELETE), qualidade semântica dos nomes de colunas,
logs de volume e promoção de camadas.

## Classificação de severidade

- **[CRÍTICO]** — viola arquitetura, emite linhagem incorreta, usa conexão nativa direta, viola nomenclatura obrigatória (inclui abreviatura proibida e fora de snake_case em Silver/Gold — CLAUDE.md regra 6)
- **[IMPORTANTE]** — viola estrutura de seções, join sem parâmetros explícitos
- **[SUGESTÃO]** — melhoria de legibilidade, simplificação, boas práticas

## Situações mais perigosas em ETL

### [CRÍTICO] DataFrame vazio processado silenciosamente (ghost run)
Pipeline executa sem erro e carrega zero registros sem aviso. `read_data()` pode retornar
vazio se a query não trouxer resultados, o arquivo no MinIO estiver vazio, ou um filtro
eliminou tudo.
```python
df = read_data('protheus', query)
if df.empty:
    raise ValueError("Extração retornou DataFrame vazio. Verifique a query ou a fonte.")
```

### [CRÍTICO] DELETE/TRUNCATE antes da validação de vazio (loader destrutivo)
A variante mais danosa do ghost run: o loader limpa a tabela de destino e só então
descobriria que não tem nada para inserir. A tabela de produção é apagada, o Airflow
marca sucesso, dashboards zeram silenciosamente.
```python
# Perigoso — DELETE antes de validar:
df = read_data(bucket=BUCKET, object_name=ARQUIVO)
write_data('mysql', DELETE_SQL)          # tabela apagada mesmo com df vazio
write_data('mysql', df, table=TABELA)

# Correto — ordem: read → validar → CREATE → DELETE → INSERT:
df = read_data(bucket=BUCKET, object_name=ARQUIVO)
if df.empty:
    raise ValueError("[Extract] Parquet vazio — DELETE e INSERT não executados.")
write_data('mysql', DELETE_SQL)
write_data('mysql', df, table=TABELA)
```

### [IMPORTANTE] Join sem parâmetros explícitos
Join implícito depende de comportamento padrão — impossível de entender sem executar.
```python
# Perigoso:
df_resultado = df_venda.merge(df_filial)

# Correto:
df_resultado = df_venda.merge(df_filial, how='left', on='codigo_filial')
print(f"Linhas antes: {len(df_venda)} | Após merge: {len(df_resultado)}")
```

### [CRÍTICO] Chained assignment
Comportamento imprevisível no pandas — bug silencioso.
```python
# Perigoso:
df[df['status'] == 'ativo']['valor'] = 0

# Correto:
df.loc[df['status'] == 'ativo', 'valor'] = 0
```

### [IMPORTANTE] Iteração com for sobre linhas de DataFrame
Lento e raramente necessário — use operações vetorizadas.
```python
# Lento e perigoso:
for index, row in df.iterrows():
    df.at[index, 'valor_com_imposto'] = row['valor'] * 1.12

# Correto:
df['valor_com_imposto'] = df['valor'] * 1.12
```

### [CRÍTICO] Nulos em colunas-chave antes da carga
Carrega dados inválidos ou falha com erro genérico no banco.
```python
COLUNAS_OBRIGATORIAS = ['codigo_centro_custo', 'descricao_centro_custo']
nulos = df[COLUNAS_OBRIGATORIAS].isnull().sum()
if nulos.any():
    raise ValueError(f"Nulos em colunas obrigatórias:\n{nulos[nulos > 0]}")
```

### [CRÍTICO] Duplicatas não tratadas na Silver
Duplicatas na Silver multiplicam todos os joins feitos na Gold. Nunca use
`drop_duplicates()` sem `subset` — isso compara todas as colunas e pode manter
duplicatas em colunas-chave.
```python
CHAVE_PRIMARIA = ['codigo_centro_custo']
linhas_antes = len(df)
df = df.drop_duplicates(subset=CHAVE_PRIMARIA, keep='last')
print(f"Dedup: {linhas_antes} → {len(df)} registros")
```

### [CRÍTICO] Carregar na camada errada
Bronze → Gold diretamente pula a Silver e corrompe a linhagem. A ordem de promoção é
sempre Bronze → Silver → Gold; qualquer desvio deve ser documentado e justificado
explicitamente (alertar riscos, recomendar Silver, seguir sem bloquear se recusado).

### [CRÍTICO] Transformação no Extractor
A Bronze deve ser cópia auditável da fonte. Renomear colunas, filtrar registros ou
converter tipos no Extractor dificulta auditoria, debug e reprocessamento. Mover para o
Transformer correspondente.

### [CRÍTICO] Conectores nativos diretamente
`mysql.connector`, `sqlalchemy` ou `boto3` em vez do Flowrix: a linhagem é quebrada, o
Marquez não registra o acesso, o dado fica invisível para o catálogo. Substituir pelo
Flowrix.

## Tratamento de erros

```python
# Perigoso — nunca engolir exceções:
try:
    df = read_data('mysql', query)
except Exception:
    pass

# Correto:
try:
    df = read_data('mysql', query)
except Exception as e:
    print(f"Erro ao extrair dados do MySQL: {e}")
    raise

# pass em except exige justificativa em comentário:
try:
    write_data('mysql', 'DROP TABLE IF EXISTS tmp_cache')
except Exception:
    pass  # Tabela pode não existir — ignorar é intencional
```

## Simplicidade — o que apontar como [SUGESTÃO]

- Classes/OO em pipelines (devem ser scripts lineares procedurais)
- Nomes genéricos (`df2`, `tmp`, `data`, `x`) fora de escopo mínimo e óbvio
- Magic numbers/strings sem constante nomeada no topo
- Funções que fazem mais de uma coisa ou cujo nome não descreve completamente o que fazem
- Mais de 3 níveis de indentação — reorganizar com filtros vetorizados
- Ausência de log de volume antes/depois de transformações relevantes

## Referência rápida

| Situação | Ação |
| --- | --- |
| Nome de script fora do padrão | [CRÍTICO] — `extractor_{dom}_{det}` ou `{funcao}_{camada}_{dom}_{det}` |
| DataFrame vazio após extração | `raise ValueError` com mensagem descritiva |
| Join sem `how` e `on` | Sempre especifique ambos |
| Coluna nula em chave primária | Valide antes da carga com `raise ValueError` |
| Duplicatas na Silver | `drop_duplicates(subset=[chave])` obrigatório |
| Conector nativo (sqlalchemy, boto3) | Substitua pelo Flowrix |
| `load_dotenv` no script | Legado se há `read_data` — Flowrix já carrega `.env`. Permitido em extractors externos (`declare_source` presente, sem `read_data`) |
| Transformação no Extractor | Mova para o Transformer correspondente |
| Carga Bronze → Gold direto | [CRÍTICO] — crie a Silver |
| pandas/flowrix/requests/dotenv em DAG | [CRÍTICO] — DAG orquestra; lógica de dados vai para script versionado |
| dag_id ≠ nome do arquivo | [IMPORTANTE] — convenção: dag_id == stem do arquivo |
| E-mail pessoal hardcoded em DAG | [IMPORTANTE] — use ALERT_EMAILS (env var) |
| Arquivo placeholder (dominio_detalhe/dominio_api) em repo real | [CRÍTICO] — apagar na finalização do ETL |
| Erro interno do Flowrix | Consulte a skill `flowrix` (seção Troubleshooting) |
