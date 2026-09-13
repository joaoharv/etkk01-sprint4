# Model Registry

Artefatos treinados dos modelos de ML (Plano 2.1), consumidos por `src/ml/model_registry.py`.
Não é um serviço (sem MLflow) — é um diretório versionado por pastas, validado em código.

## Estrutura esperada

```
models/
├── volume_d7/
│   ├── current.json      -- {"version": "v1"} aponta a versao vigente
│   └── v1/
│       ├── model.pkl      -- joblib.dump() do modelo treinado (Ridge, notebook 01)
│       └── metadata.json
└── prioridade/
    ├── current.json
    └── v1/
        ├── model.pkl       -- pipeline sklearn completo (TF-IDF + OneHot + LinearSVC, notebook 02)
        └── metadata.json
```

Cada família de modelo (`volume_d7`, `prioridade`) é independente. Promover uma versão nova
é editar `current.json` manualmente — não existe promoção automática nesta sprint.

## `metadata.json` — campos obrigatórios

```json
{
  "modelo": "ridge_d7",
  "versao": "v1",
  "tipo": "regressao | classificacao",
  "target": "volume_total(t+7)",
  "features": ["lag_1", "lag_2", "...", "periodo_pos_set_2025"],
  "hiperparametros": {"alpha": 0.01},
  "periodo_treino": {"inicio": "2025-01-01", "fim": "2025-10-31"},
  "metricas_val": {"MAE": 91.2, "RMSE": 118.4},
  "metricas_test": {"MAE": 95.8, "RMSE": 122.1},
  "sklearn_version": "1.9.1",
  "python_version": "3.11.9",
  "treinado_em": "2026-01-10T14:00:00"
}
```

Todos os campos acima são obrigatórios — `model_registry.load_model()` recusa carregar um
artefato cujo `metadata.json` esteja incompleto (ver Plano 2.1, seção "Model Registry").

## Cadeia de validação (`src/ml/model_registry.py::load_model`)

```
current.json existe?          -> senão: FileNotFoundError
versão apontada existe?        -> senão: FileNotFoundError
model.pkl existe?              -> senão: FileNotFoundError
metadata.json existe e é JSON válido?  -> senão: FileNotFoundError / ValueError
metadata tem todos os campos obrigatórios?  -> senão: ValueError explícito
joblib.load(model.pkl) não lança exceção?   -> incompatibilidade de versão apareceria aqui
```

A comparação `features do metadata == features produzidas pelo feature engineering` é feita
por `validar_features()`, chamada pelos scripts `predict_*.py` (não pelo registry em si — o
registry não sabe quais colunas o chamador produziu). Nunca faz subset silencioso: falta ou
sobra de coluna é erro.

## Versionamento de artefatos no git

`*.pkl` **não é versionado** (binário, gerado por `src/ml/train_*.py`, específico da versão
de `scikit-learn`/`numpy` do container — ver `.gitignore`). `current.json` e `metadata.json`
são versionados normalmente: são o registro auditável de qual modelo está vigente e com que
métricas, sem custo de repositório.

## Treinamento

Todo treino roda **dentro do container Airflow** (`docker compose exec airflow-webserver ...`
ou `make shell`), nunca no host — garante que a versão de `scikit-learn`/`numpy` que serializa
o `.pkl` é a mesma que vai desserializá-lo na inferência.

Nesta etapa (Plano 2.1, Etapa 3) nenhum modelo foi treinado ainda — este diretório documenta
o contrato, mas `volume_d7/` e `prioridade/` só passam a existir de fato na Etapa 7/11.
