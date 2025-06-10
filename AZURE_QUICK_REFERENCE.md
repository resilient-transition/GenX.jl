# 🚀 GenX Azure - Quick Reference

> **Essential commands and information for GenX Azure cloud infrastructure**

📚 **Full Documentation**: See [`AZURE_README.md`](./AZURE_README.md) for complete deployment and operational guide

## 📦 **Deployment**
```bash
# One-command deployment
./scripts/deploy_complete_workflow.sh

# Validate deployment
python scripts/validate_deployment.py --resource-group genx-rg --storage-account <name> --registry <name> --function-app <name>
```

## 🔄 **Case Processing**
```bash
# Upload optimization case
python scripts/azure_blob_utils.py upload \
  --account-name <storage-account> \
  --account-key <key> \
  --container cases \
  --local-path ./your-case \
  --blob-prefix case-name

# Download results
python scripts/azure_blob_utils.py download \
  --account-name <storage-account> \
  --account-key <key> \
  --container results \
  --blob-prefix case-name \
  --local-path ./results
```

## 📊 **Monitoring**
```bash
# System status
python scripts/production_monitor.py --resource-group genx-rg monitor

# List active containers
python scripts/production_monitor.py --resource-group genx-rg list

# Container logs
python scripts/production_monitor.py --resource-group genx-rg logs <container-name>

# Cleanup old containers
python scripts/production_monitor.py --resource-group genx-rg cleanup --max-age-hours 24
```

## 🔧 **Azure CLI Commands**
```bash
# Check container status
az container list --resource-group genx-rg --output table

# Function app logs
az functionapp logs tail --name genx-function-app --resource-group genx-rg

# Storage containers
az storage container list --account-name <storage-account>

# Event Grid subscriptions
az eventgrid event-subscription list --source-resource-id <storage-resource-id>
```

## 🌐 **Key URLs**
- **Azure Portal**: https://portal.azure.com
- **Function Status**: https://genx-function-app.azurewebsites.net/api/status
- **Storage Explorer**: Portal → Storage Accounts → genxstorage
- **Application Insights**: Portal → genx-app-insights

## 📁 **Important Files**
- `COMPLETE_AZURE_DOCUMENTATION.md` - Full documentation
- `azure-function/function_app.py` - Core processing logic
- `scripts/deploy_complete_workflow.sh` - Deployment script
- `scripts/production_monitor.py` - Management tools
- `tests/` - Test suite (4/4 passing)

## 🆘 **Quick Troubleshooting**
```bash
# Container creation fails
az vm list-usage --location eastus  # Check quotas
az acr credential show --name genxjlregistry  # Verify registry

# Function timeouts
# Increase timeout in azure-function/host.json: "functionTimeout": "00:30:00"

# Storage access issues
az storage account keys list --account-name genxstorage  # Get keys
az role assignment list --assignee <function-identity>  # Check permissions
```

## 📋 **Environment Variables** (Function App)
```
AZURE_STORAGE_ACCOUNT=genxstorage
AZURE_STORAGE_KEY=<storage-key>
AZURE_REGISTRY_NAME=genxjlregistry
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=genx-rg
AZURE_LOCATION=eastus
```

## 🎯 **Architecture Summary**
```
Blob Upload → Event Grid → Azure Function → Container Instance → GenX Optimization → Results Storage
```

---
**Complete Documentation**: [`AZURE_README.md`](./AZURE_README.md) | **Status**: ✅ Production Ready | **Tests**: 4/4 Passing
