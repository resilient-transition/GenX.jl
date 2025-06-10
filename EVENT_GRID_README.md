# GenX Azure Event Grid Automation

This system automatically processes GenX optimization cases when they are uploaded to Azure Blob Storage using Azure Event Grid triggers.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Blob Storage  │    │   Event Grid     │    │   Azure Function   │
│                 │    │                  │    │                     │
│  📁 cases/      │───▶│  🎯 Blob Created │───▶│  🔍 Process Event   │
│  📁 results/    │    │     Events       │    │  🐳 Create Container│
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Azure Container Instance                             │
│                                                                         │
│  1. 📥 Download case data from blob storage                            │
│  2. 🏃 Run GenX optimization                                           │
│  3. 📤 Upload results back to blob storage                            │
│  4. 🧹 Auto-cleanup on completion                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Azure Function (`azure-function/`)
- **Event Grid Trigger**: Responds to blob creation events
- **Container Orchestration**: Creates Azure Container Instances for processing
- **HTTP Status Endpoint**: Monitor active processing jobs

### 2. Enhanced Container (`Dockerfile.eventgrid`)
- **Dynamic Case Loading**: Downloads cases from blob storage
- **GenX Processing**: Runs optimization with uploaded case data
- **Result Upload**: Automatically uploads results back to blob storage
- **Python Integration**: Includes Azure SDK for blob operations

### 3. Management Scripts (`scripts/`)
- **`setup_event_grid.sh`**: Initial Azure infrastructure setup
- **`monitor_deployment.sh`**: Monitor and manage the system
- **`run_genx_case.py`**: Enhanced GenX runner with blob integration

## Setup Instructions

### Prerequisites

1. **Azure CLI** installed and logged in
2. **Azure Functions Core Tools** for function deployment
3. **Docker** for local testing
4. **Azure Subscription** with appropriate permissions

### Step 1: Initial Setup

Run the setup script to create all required Azure resources:

```bash
./scripts/setup_event_grid.sh
```

This creates:
- Resource Group (`genx-rg`)
- Storage Account (`genxstorage`) with containers (`cases`, `results`)
- Function App (`genx-eventgrid-function`)
- Event Grid subscription for blob events
- Required permissions and managed identities

### Step 2: Deploy Function Code

```bash
cd azure-function
func azure functionapp publish genx-eventgrid-function
```

### Step 3: Build and Deploy Container

The container is automatically built and deployed via GitHub Actions when you push changes. Alternatively, build manually:

```bash
# Build the Event Grid container
docker build -f Dockerfile.eventgrid -t genx-eventgrid .

# Tag and push to ACR (after logging in)
az acr login --name genxjlregistry
docker tag genx-eventgrid genxjlregistry.azurecr.io/genx-eventgrid:latest
docker push genxjlregistry.azurecr.io/genx-eventgrid:latest
```

## Usage

### Upload a Case for Processing

1. **Prepare your GenX case** with the standard file structure:
   ```
   my_case/
   ├── genx_settings.yml
   ├── Load_data.csv
   ├── Generators_data.csv
   ├── Fuels_data.csv
   └── ... (other GenX input files)
   ```

2. **Upload to blob storage**:
   ```bash
   # Using Azure CLI
   az storage blob upload-batch \
     --destination "cases/my_case" \
     --source "./my_case" \
     --account-name genxstorage
   
   # Using the utility script
   python3 scripts/azure_blob_utils.py upload \
     --account-name genxstorage \
     --container cases \
     --local-path "./my_case" \
     --blob-prefix "my_case"
   ```

3. **Monitor processing**:
   ```bash
   # Check system status
   ./scripts/monitor_deployment.sh status
   
   # Stream function logs
   ./scripts/monitor_deployment.sh logs
   
   # List active containers
   ./scripts/monitor_deployment.sh containers
   ```

4. **Download results**:
   ```bash
   # List results
   ./scripts/monitor_deployment.sh results
   
   # Download specific case results
   python3 scripts/azure_blob_utils.py download \
     --account-name genxstorage \
     --container results \
     --blob-prefix "my_case/results" \
     --local-path "./my_case_results"
   ```

### Test the System

Run a quick test with a sample case:

```bash
./scripts/monitor_deployment.sh test
```

This uploads a minimal test case and triggers the full processing pipeline.

## Monitoring and Management

### Check System Status
```bash
./scripts/monitor_deployment.sh status
```

### Monitor Processing Logs
```bash
./scripts/monitor_deployment.sh logs
```

### List Active Jobs
```bash
./scripts/monitor_deployment.sh containers
```

### Clean Up Completed Jobs
```bash
./scripts/monitor_deployment.sh clean
```

### Function App Endpoints

- **Status Endpoint**: `https://genx-eventgrid-function.azurewebsites.net/api/status`
- **Azure Portal**: Monitor function executions and logs

## Configuration

### Environment Variables

The system uses these environment variables (automatically configured by setup script):

| Variable | Description |
|----------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `AZURE_RESOURCE_GROUP` | Resource group name |
| `AZURE_STORAGE_ACCOUNT` | Storage account name |
| `AZURE_STORAGE_KEY` | Storage account access key |
| `AZURE_LOCATION` | Azure region |
| `AZURE_REGISTRY_NAME` | Container registry name |

### Container Configuration

Containers are created with these specifications:
- **Memory**: 8GB
- **CPU**: 4 cores
- **Timeout**: 1 hour
- **Restart Policy**: Never (one-time execution)

### Blob Storage Structure

```
Storage Account: genxstorage
├── cases/          # Input cases
│   ├── case1/
│   │   ├── genx_settings.yml
│   │   ├── Load_data.csv
│   │   └── ...
│   └── case2/
│       └── ...
└── results/        # Output results
    ├── case1/
    │   ├── results/
    │   │   ├── capacity.csv
    │   │   ├── power.csv
    │   │   └── ...
    │   └── _summary.json
    └── case2/
        └── ...
```

## Troubleshooting

### Common Issues

1. **Function not triggering**:
   - Check Event Grid subscription is active
   - Verify blob is uploaded to `cases/` container
   - Check function app logs for errors

2. **Container creation fails**:
   - Verify ACR credentials are correct
   - Check resource quotas in Azure subscription
   - Ensure managed identity has required permissions

3. **GenX processing errors**:
   - Check container logs in Azure Portal
   - Verify case data format and completeness
   - Monitor container resource usage

### Debugging Commands

```bash
# Check Event Grid subscription
az eventgrid event-subscription list --source-resource-id /subscriptions/{sub-id}/resourceGroups/genx-rg/providers/Microsoft.Storage/storageAccounts/genxstorage

# View function app logs
az functionapp log tail --name genx-eventgrid-function --resource-group genx-rg

# List container instances
az container list --resource-group genx-rg --output table

# Get container logs
az container logs --name {container-name} --resource-group genx-rg
```

## Cost Optimization

- Containers are automatically deleted after completion
- Use `monitor_deployment.sh clean` to remove completed containers
- Function App uses consumption plan (pay-per-execution)
- Storage costs scale with data volume

## Security

- Managed identities for secure Azure service authentication
- Storage account keys stored as Function App settings
- Container Registry with admin credentials
- Network isolation available through VNet integration (optional)

## GitHub Actions Integration

The system includes automated CI/CD through GitHub Actions:
- Builds and tests containers on code changes
- Deploys to ACR automatically
- Updates Function App when function code changes

## Next Steps

1. **Custom Case Validation**: Add validation logic for uploaded cases
2. **Notification System**: Send emails/webhooks when processing completes
3. **Advanced Monitoring**: Set up Application Insights for detailed monitoring
4. **Multi-Region**: Deploy across multiple Azure regions for redundancy
5. **Resource Scaling**: Implement auto-scaling based on queue depth
