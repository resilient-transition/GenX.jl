# GenX Event Grid Automation

## Overview
Automated GenX case processing using Azure Event Grid, triggered by blob uploads to the `cases` container.

## Architecture
```
Blob Upload → Event Grid → Azure Function → Container Instance → GenX Processing → Results Upload
```

## How It Works

### 1. Case Upload
Upload GenX case files to the `cases` blob container:
```bash
az storage blob upload-batch \
  --destination cases \
  --source your-case-directory \
  --account-name genxstorage
```

### 2. Automatic Processing
- Event Grid detects blob creation in `cases` container
- Azure Function `process_genx_case` is triggered
- Function creates Container Instance with commit SHA-tagged image
- Container downloads case data, runs GenX optimization, uploads results

### 3. Results Storage
Results are automatically uploaded to the `results` container:
- `{case_name}/results/` - Main optimization results
- `{case_name}/TDR_results/` - Time Domain Reduction results

## Infrastructure Components

| Component | Purpose |
|-----------|---------|
| Storage Account `genxstorage` | Stores case inputs and results |
| Container Registry `genxjlregistry` | Hosts GenX Docker images |
| Function App `genx-function-app` | Orchestrates container creation |
| Event Grid Topic `genx-blob-events` | Triggers processing on uploads |
| Container Instances | Runs GenX optimization |

## Monitoring

### Check Processing Status
```bash
# List active containers
az container list --resource-group genx-rg --output table

# View function logs
az functionapp logs tail --name genx-function-app --resource-group genx-rg

# List results
az storage blob list --container-name results --account-name genxstorage
```

### Download Results
```bash
az storage blob download-batch \
  --destination ./results \
  --source results \
  --pattern "your-case-name/*" \
  --account-name genxstorage
```

## Case Requirements
For automatic detection, case uploads should include:
- `Run.jl`, `Generators_data.csv`, `Load_data.csv`, `Fuels_data.csv`, or `genx_settings.yml`
- Or be in a directory structure containing `/case/` or prefixed with `case_`

## Deployment
Infrastructure is automatically deployed when changes are pushed to the main branch via GitHub Actions workflow.
