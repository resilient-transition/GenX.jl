# 🚀 GenX.jl Azure Deployment Guide

This guide provides comprehensive instructions for deploying the GenX.jl Azure cloud infrastructure for automated power system optimization.

## 📋 Overview

The GenX Azure infrastructure provides:
- **Automated Processing**: Event Grid triggers for blob uploads
- **Container Orchestration**: Azure Container Instances for scalable computation
- **Storage Integration**: Blob storage for input/output management
- **Monitoring**: Real-time status tracking and logging
- **CI/CD Pipeline**: Automated builds and deployments

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Blob Storage  │────│   Event Grid     │────│   Azure Function   │
│   (Cases/Data)  │    │   (Triggers)     │    │   (Orchestrator)    │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
                                                           ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Results       │◄───│   Monitoring     │    │   Container Inst.   │
│   Storage       │    │   (App Insights) │    │   (GenX Processing) │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## 🛠️ Prerequisites

### Required Tools
- **Azure CLI** (`az --version >= 2.0`)
- **Docker** (for local testing)
- **Python 3.8+** (for deployment scripts)
- **Git** (for source code)

### Required Azure Services
- **Azure Subscription** with Contributor access
- **Resource Group** creation permissions
- **Service Principal** (for CI/CD authentication)

## 📦 Deployment Steps

### 1. Clone and Setup Repository

```bash
# Clone the repository
git clone <your-genx-repo-url>
cd GenX.jl

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Azure Environment

```bash
# Login to Azure
az login

# Set subscription (replace with your subscription ID)
az account set --subscription "your-subscription-id"

# Create resource group
az group create --name genx-rg --location eastus
```

### 3. Deploy Infrastructure

#### Option A: Automated Deployment (Recommended)

```bash
# Use the comprehensive deployment script
./scripts/deploy_complete_workflow.sh
```

#### Option B: Manual Deployment

```bash
# 1. Deploy ARM template
az deployment group create \
  --resource-group genx-rg \
  --template-file infrastructure/arm-template.json \
  --parameters @infrastructure/parameters.json

# 2. Build and push container image
docker build -t genx-jl:latest .
az acr build --registry genxjlregistry --image genx-jl:latest .

# 3. Deploy Azure Function
cd azure-function
func azure functionapp publish genx-function-app
```

### 4. Configure Environment Variables

Set the following environment variables in your Azure Function:

```bash
# Storage Configuration
AZURE_STORAGE_ACCOUNT=genxstorage
AZURE_STORAGE_KEY=<your-storage-key>

# Container Registry
AZURE_REGISTRY_NAME=genxjlregistry
AZURE_REGISTRY_USERNAME=<registry-username>
AZURE_REGISTRY_PASSWORD=<registry-password>

# Azure Configuration
AZURE_SUBSCRIPTION_ID=<your-subscription-id>
AZURE_RESOURCE_GROUP=genx-rg
AZURE_LOCATION=eastus
```

### 5. Setup Event Grid Subscription

```bash
# Create Event Grid subscription
az eventgrid event-subscription create \
  --name genx-blob-subscription \
  --source-resource-id "/subscriptions/<subscription-id>/resourceGroups/genx-rg/providers/Microsoft.Storage/storageAccounts/genxstorage" \
  --endpoint "/subscriptions/<subscription-id>/resourceGroups/genx-rg/providers/Microsoft.Web/sites/genx-function-app/functions/blob_trigger" \
  --endpoint-type azurefunction \
  --subject-begins-with "/blobServices/default/containers/cases/"
```

## 🧪 Testing the Deployment

### 1. Validate Infrastructure

```bash
# Run validation script
python tests/test_deployment_validation.py
```

### 2. Test Case Upload

```bash
# Upload a test case
python scripts/azure_blob_utils.py upload \
  --account-name genxstorage \
  --account-key <storage-key> \
  --container cases \
  --local-path example_systems/1_three_zones \
  --blob-prefix test-case-1
```

### 3. Monitor Processing

```bash
# Check container status
az container list --resource-group genx-rg --output table

# View function logs
az functionapp logs tail --name genx-function-app --resource-group genx-rg
```

## 📊 Monitoring and Management

### Application Insights

Access monitoring data through:
- **Azure Portal** → Application Insights → genx-app-insights
- **Live Metrics**: Real-time performance data
- **Logs**: Query execution logs with KQL
- **Alerts**: Automated notifications for failures

### Container Management

```bash
# List active containers
curl -X GET "https://genx-function-app.azurewebsites.net/api/status?code=<function-key>"

# Stop a specific container
az container stop --name <container-name> --resource-group genx-rg

# View container logs
az container logs --name <container-name> --resource-group genx-rg
```

### Storage Management

```bash
# List cases in storage
python scripts/azure_blob_utils.py list \
  --account-name genxstorage \
  --account-key <storage-key> \
  --container cases

# Download results
python scripts/azure_blob_utils.py download \
  --account-name genxstorage \
  --account-key <storage-key> \
  --container results \
  --blob-prefix case-name \
  --local-path ./downloaded-results
```

## 🔧 Configuration Options

### Function App Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `FUNCTION_TIMEOUT` | Maximum execution time | 00:10:00 |
| `CONTAINER_MEMORY_GB` | Memory allocation | 8.0 |
| `CONTAINER_CPU` | CPU allocation | 4.0 |
| `GENX_PRECOMPILE` | Julia precompilation | false |

### Container Instance Settings

Modify in `azure-function/function_app.py`:

```python
# Resource requirements
ResourceRequirements(
    requests=ResourceRequests(
        memory_in_gb=16.0,  # Increase for larger cases
        cpu=8.0             # Increase for faster processing
    )
)
```

## 🚨 Troubleshooting

### Common Issues

1. **Container Creation Failures**
   ```bash
   # Check quota limits
   az vm list-usage --location eastus
   
   # Check registry credentials
   az acr credential show --name genxjlregistry
   ```

2. **Function Timeout Issues**
   ```bash
   # Increase timeout in host.json
   "functionTimeout": "00:30:00"
   
   # Use async processing for large cases
   ```

3. **Storage Access Issues**
   ```bash
   # Verify storage key
   az storage account keys list --account-name genxstorage
   
   # Test connectivity
   az storage container list --account-name genxstorage
   ```

### Debug Logs

```bash
# Function app logs
az functionapp logs tail --name genx-function-app --resource-group genx-rg

# Container logs
az container logs --name <container-name> --resource-group genx-rg --follow

# Event Grid delivery attempts
az eventgrid event-subscription show \
  --name genx-blob-subscription \
  --source-resource-id <storage-resource-id>
```

## 🔐 Security Considerations

### Access Control
- Use **Managed Identity** for inter-service authentication
- Implement **RBAC** for resource access
- Configure **Network Security Groups** for container isolation

### Secrets Management
- Store sensitive data in **Azure Key Vault**
- Use **Function App Settings** for configuration
- Rotate **storage keys** regularly

### Monitoring
- Enable **Azure Security Center** recommendations
- Configure **Log Analytics** for security events
- Set up **alerts** for unusual activity

## 📈 Scaling and Optimization

### Performance Tuning
- **Container Resources**: Scale based on case complexity
- **Parallel Processing**: Run multiple containers simultaneously
- **Storage Tiers**: Use appropriate storage classes for data lifecycle

### Cost Optimization
- **Automatic Cleanup**: Remove completed containers
- **Storage Lifecycle**: Archive old results
- **Reserved Instances**: For predictable workloads

## 🆘 Support

### Documentation
- **Azure Functions**: [Microsoft Docs](https://docs.microsoft.com/azure/azure-functions/)
- **Container Instances**: [Microsoft Docs](https://docs.microsoft.com/azure/container-instances/)
- **Event Grid**: [Microsoft Docs](https://docs.microsoft.com/azure/event-grid/)

### Community Support
- **GenX.jl Issues**: [GitHub Repository](https://github.com/GenXProject/GenX)
- **Azure Forums**: [Microsoft Q&A](https://docs.microsoft.com/answers/)

---

## 📝 Deployment Checklist

- [ ] Azure CLI installed and configured
- [ ] Resource group created
- [ ] ARM template deployed successfully
- [ ] Container registry configured
- [ ] Function app deployed
- [ ] Event Grid subscription created
- [ ] Environment variables configured
- [ ] Test case processed successfully
- [ ] Monitoring configured
- [ ] Documentation reviewed

**🎉 Your GenX Azure infrastructure is ready for production use!**
