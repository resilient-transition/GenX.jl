# GenX Azure Container Apps - Complete Documentation

This comprehensive guide covers everything you need to know about deploying and using the GenX Azure Container Apps parallel processing system. This document combines all aspects: quick start, technical architecture, user guide, and troubleshooting.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start Deployment](#quick-start-deployment)
3. [Technical Architecture](#technical-architecture)
4. [Complete User Guide](#complete-user-guide)
5. [Monitoring and Troubleshooting](#monitoring-and-troubleshooting)
6. [Cost Optimization](#cost-optimization)
7. [Best Practices](#best-practices)

---

# Overview

## What is GenX Azure Container Apps?

GenX Azure Container Apps provides a scalable, cloud-native solution for running multiple GenX optimization cases in parallel. The system automatically scales based on demand, provides cost-effective pay-per-use pricing, and requires no infrastructure management.

### Key Features
- **Automatic triggering** when case files are uploaded to Azure Blob Storage
- **Manual execution** through GitHub Actions interface  
- **Parallel processing** of multiple cases with configurable resources
- **Cost-effective** pay-per-use model with automatic scaling
- **No infrastructure management** required

### System Architecture
```
Azure Blob Storage → Event Grid → Azure Function → GitHub Actions → Azure Container Apps
       ↑                                                                        ↓
   File Upload                                                            Results Upload
```

### Parallel Execution Flow
```
Input: "case1,case2,case3,case4,case5"
       ↓
┌─────────────────────────────────────┐
│     GitHub Actions Matrix           │
│  ┌─────┬─────┬─────┬─────┬─────┐   │
│  │Job 1│Job 2│Job 3│Job 4│Job 5│   │  (max_parallel=5)
│  │case1│case2│case3│case4│case5│   │
│  └─────┴─────┴─────┴─────┴─────┘   │
└─────────────────────────────────────┘
       ↓ (parallel execution)
┌─────────────────────────────────────┐
│       Azure Container Apps          │
│  ┌─────┬─────┬─────┬─────┬─────┐   │
│  │ACA 1│ACA 2│ACA 3│ACA 4│ACA 5│   │  (separate containers)
│  │GenX │GenX │GenX │GenX │GenX │   │
│  └─────┴─────┴─────┴─────┴─────┘   │
└─────────────────────────────────────┘
       ↓ (results uploaded)
┌─────────────────────────────────────┐
│        Azure Blob Storage           │
│  results/case1_20250609_143022/     │
│  results/case2_20250609_143025/     │
│  results/case3_20250609_143028/     │
│  results/case4_20250609_143031/     │
│  results/case5_20250609_143034/     │
└─────────────────────────────────────┘
```

---

# Quick Start Deployment

## 🚀 Deployment Checklist

### Prerequisites
- [ ] Azure subscription with sufficient credits/quotas
- [ ] Azure CLI installed locally (`brew install azure-cli` on macOS)
- [ ] GitHub repository with push access
- [ ] GitHub Personal Access Token with `workflow` permissions

### 1. Deploy Azure Infrastructure
```bash
# Make deployment script executable
chmod +x deploy_azure_infrastructure.sh

# Run deployment (will prompt for confirmation)
./deploy_azure_infrastructure.sh

# This creates:
# ✅ Resource Group
# ✅ Storage Account  
# ✅ Blob Container
# ✅ Azure Function App
# ✅ Service Principal for GitHub
# ✅ Event Grid System Topic
```

### 2. Configure GitHub Repository
```bash
# Copy secrets from generated file
cat github_secrets.txt

# Add these secrets to GitHub repository:
# Settings → Secrets and variables → Actions → Repository secrets
```

**Required GitHub Secrets:**
- `AZURE_CREDENTIALS`
- `AZURE_SUBSCRIPTION_ID` 
- `AZURE_RESOURCE_GROUP`
- `AZURE_LOCATION`
- `AZURE_STORAGE_ACCOUNT`
- `AZURE_STORAGE_KEY`

### 3. Deploy Azure Function
```bash
# Navigate to function directory
cd azure-function

# Install Azure Functions Core Tools (if needed)
# macOS: brew tap azure/functions && brew install azure-functions-core-tools@4

# Deploy function
func azure functionapp publish YOUR_FUNCTION_APP_NAME

# Configure function environment variables in Azure Portal:
# Function App → Configuration → Application settings
# GITHUB_TOKEN=your_github_token
# GITHUB_REPO=username/repository_name  
# GITHUB_WORKFLOW_ID=azure-container-apps-parallel.yml
```

### 4. Set Up Event Grid Subscription
```bash
# Make setup script executable
chmod +x setup_event_grid.sh

# Run Event Grid setup
./setup_event_grid.sh YOUR_RESOURCE_GROUP YOUR_STORAGE_ACCOUNT YOUR_FUNCTION_APP
```

### 5. Test the System
```bash
# Make test script executable
chmod +x test_deployment.sh

# Run test with minimal case
./test_deployment.sh YOUR_STORAGE_ACCOUNT YOUR_CONTAINER_NAME test_case

# This will:
# ✅ Create minimal GenX test case
# ✅ Upload to blob storage
# ✅ Trigger automatic workflow (if Event Grid configured)
# ✅ Provide manual testing instructions
```

---

# Technical Architecture

## Resource Management

### Per-Job Resources
- **CPU**: 0.25 to 2.0 cores per job
- **Memory**: 0.5 to 4.0 GB per job
- **Storage**: Temporary disk for downloads/processing
- **Timeout**: 2 hours per job (configurable)

### Total Resource Usage
If you run 5 parallel jobs with 2 cores and 4GB each:
- **Total**: 10 CPU cores, 20GB RAM
- **Cost**: Pay only for actual usage time
- **Scaling**: Automatic scale-to-zero when jobs complete

## Advantages over GitHub Actions

| Feature | GitHub Actions | Azure Container Apps |
|---------|----------------|---------------------|
| **Max Runtime** | 6 hours | Unlimited |
| **CPU Cores** | 2 cores | Up to 2 cores per job |
| **Memory** | 7GB | Up to 4GB per job |
| **Parallel Jobs** | 20 (org limit) | Hundreds |
| **Cost** | Free tier limited | Pay-per-use |
| **GPU Support** | No | Yes (preview) |
| **Network** | GitHub's | Azure's high-speed |
| **Storage** | Temporary | Persistent options |

## Usage Examples

### Example 1: Run 3 cases in parallel
```
# Manual trigger in GitHub Actions:
case_names: "kentucky,texas,california"
max_parallel: 3
cpu_cores: 1.0
memory_gb: 2.0
```
**Result**: 3 Container App jobs run simultaneously, each with 1 CPU core and 2GB RAM.

### Example 2: Run 10 cases with resource limits
```
case_names: "case1,case2,case3,case4,case5,case6,case7,case8,case9,case10"
max_parallel: 5
cpu_cores: 2.0
memory_gb: 4.0
```
**Result**: 5 jobs run first, then 5 more jobs start as the first batch completes. Each job gets 2 CPU cores and 4GB RAM.

### Example 3: Large batch processing
```
case_names: "region1,region2,region3,region4,region5,region6,region7,region8,region9,region10,region11,region12"
max_parallel: 6
cpu_cores: 1.5
memory_gb: 3.0
```
**Result**: Runs 6 jobs at a time in 2 waves (6 + 6), with moderate resource allocation.

---

# Complete User Guide

## Prerequisites

Before using the system, ensure you have:

1. **Azure Storage Account** with the following containers:
   - `genx-data` (or your preferred container name)
2. **Access credentials** for the storage account
3. **GitHub repository access** (for manual triggering)

## File Upload Instructions

### Required File Structure

Your GenX case files must be organized in the following structure in Azure Blob Storage:

```
your-container/
├── inputs/
│   ├── case1/
│   │   ├── settings/
│   │   │   ├── genx_settings.yml
│   │   │   └── [other settings files]
│   │   ├── system/
│   │   │   ├── Generators_data.csv
│   │   │   ├── Load_data.csv
│   │   │   └── [other system files]
│   │   └── resources/
│   │       └── [resource files]
│   ├── case2/
│   │   └── [same structure as case1]
│   └── case3/
│       └── [same structure as case1]
└── results/
    └── [results will appear here automatically]
```

### Upload Methods

#### Method 1: Azure Portal (Web Interface)
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Storage Account
3. Click "Containers" → select your container (e.g., `genx-data`)
4. Click "Upload" 
5. Create folder structure: `inputs/your_case_name/`
6. Upload your GenX case files maintaining the required structure

#### Method 2: Azure Storage Explorer (Desktop App)
1. Download and install [Azure Storage Explorer](https://azure.microsoft.com/en-us/features/storage-explorer/)
2. Connect to your storage account
3. Navigate to your container
4. Create folder structure and drag-and-drop files

#### Method 3: Azure CLI (Command Line)
```bash
# Install Azure CLI (if not already installed)
# macOS: brew install azure-cli
# Windows: Download from Microsoft

# Login to Azure
az login

# Upload a case folder
az storage blob upload-batch \
    --source ./local_case_folder \
    --destination your-container \
    --destination-path "inputs/case_name" \
    --account-name your-storage-account \
    --account-key your-storage-key
```

#### Method 4: Python Script
```python
from azure.storage.blob import BlobServiceClient
import os

# Connection string from Azure Portal
connection_string = "DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
container_name = "genx-data"
case_name = "kentucky"

# Create client
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# Upload files
def upload_folder(local_folder, blob_prefix):
    for root, dirs, files in os.walk(local_folder):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_folder)
            blob_path = f"{blob_prefix}/{relative_path}".replace("\\", "/")
            
            blob_client = blob_service_client.get_blob_client(
                container=container_name, 
                blob=blob_path
            )
            
            with open(local_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            print(f"Uploaded: {blob_path}")

# Upload your case
upload_folder("./my_local_case", f"inputs/{case_name}")
```

### File Upload Triggers

When you upload files to the `inputs/` folder, the system will:
1. **Detect the upload** via Event Grid
2. **Extract the case name** from the path (e.g., `inputs/kentucky/` → case name: `kentucky`)
3. **Trigger the Azure Function** (if automatic triggering is set up)
4. **Start a GitHub Actions workflow** that creates a Container App job
5. **Run GenX** in an isolated container
6. **Upload results** to the `results/` folder

## Manual Job Execution

You can manually trigger GenX jobs without uploading files:

### Steps:
1. Go to your GitHub repository
2. Click the **"Actions"** tab
3. Select **"Parallel GenX Jobs on Azure Container Apps"** workflow
4. Click **"Run workflow"** (top right)
5. Fill in the form:
   - **blob_container**: `genx-data` (your container name)
   - **case_names**: `kentucky,texas,california` (comma-separated)
   - **cpu_cores**: `1.0` (optional, default: 1.0)
   - **memory_gb**: `2.0` (optional, default: 2.0)
   - **max_parallel**: `3` (optional, default: 5)
6. Click **"Run workflow"**

### Example Configurations:

**Small test run:**
```
blob_container: genx-data
case_names: test_case
cpu_cores: 0.5
memory_gb: 1.0
max_parallel: 1
```

**Medium parallel run:**
```
blob_container: genx-data
case_names: kentucky,texas,california,florida,ohio
cpu_cores: 1.0
memory_gb: 2.0
max_parallel: 3
```

**Large batch processing:**
```
blob_container: genx-data
case_names: region1,region2,region3,region4,region5,region6,region7,region8
cpu_cores: 2.0
memory_gb: 4.0
max_parallel: 4
```

## Automatic Triggering Setup

To enable automatic job triggering when files are uploaded:

### Step 1: Deploy Azure Function
```bash
# From the azure-function/ directory
az functionapp create \
    --resource-group your-resource-group \
    --consumption-plan-location eastus \
    --runtime python \
    --runtime-version 3.9 \
    --functions-version 4 \
    --name genx-trigger-function \
    --storage-account your-storage-account

# Deploy function code
func azure functionapp publish genx-trigger-function
```

### Step 2: Create Event Grid Subscription
```bash
# Get function endpoint
FUNCTION_URL=$(az functionapp show \
    --resource-group your-resource-group \
    --name genx-trigger-function \
    --query "defaultHostName" -o tsv)

# Create Event Grid subscription
az eventgrid event-subscription create \
    --name genx-blob-trigger \
    --source-resource-id "/subscriptions/your-subscription/resourceGroups/your-resource-group/providers/Microsoft.Storage/storageAccounts/your-storage-account" \
    --endpoint "https://$FUNCTION_URL/api/BlobTriggerGenX" \
    --endpoint-type webhook \
    --included-event-types Microsoft.Storage.BlobCreated
```

### Step 3: Configure Function Environment Variables
In Azure Portal → Function App → Configuration:
```
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=username/repository_name
GITHUB_WORKFLOW_ID=azure-container-apps-parallel.yml
```

---

# Monitoring and Troubleshooting

## Monitoring Progress

### GitHub Actions Interface
1. **Go to Actions tab** in your GitHub repository
2. **Click on the running workflow** to see overall progress
3. **View individual job status** in the matrix visualization
4. **Check real-time logs** for each case

### Azure Portal Monitoring
1. **Navigate to Azure Portal** → Container Apps
2. **Find your Container App Environment** (e.g., `genx-env-12345`)
3. **View active jobs** and their execution status
4. **Access real-time logs** and resource utilization

### Azure CLI Monitoring
```bash
# List running container apps
az containerapp list --resource-group your-resource-group

# Get job status
az containerapp job execution list \
    --job-name genx-kentucky-12345 \
    --resource-group your-resource-group

# View logs
az containerapp logs show \
    --name genx-kentucky-12345 \
    --resource-group your-resource-group \
    --follow
```

### Progress Indicators

**Status meanings:**
- ✅ **Running**: Container is executing GenX
- ✅ **Succeeded**: Job completed successfully, results uploaded
- ❌ **Failed**: Job encountered an error (check logs)
- ⏸️ **Pending**: Job waiting for resources
- ⏹️ **Cancelled**: Job was manually stopped

## Downloading Results

Results are automatically uploaded to Azure Blob Storage under the `results/` folder with timestamped directories.

### Result Structure
```
your-container/
└── results/
    ├── kentucky_20250609_143022/
    │   ├── execution_summary.txt
    │   ├── results/
    │   │   ├── capacity.csv
    │   │   ├── emissions.csv
    │   │   ├── costs.csv
    │   │   └── [other GenX outputs]
    │   ├── Project.toml
    │   └── Manifest.toml
    ├── texas_20250609_143025/
    └── california_20250609_143028/
```

### Download Methods

#### Method 1: Azure Portal
1. Navigate to Storage Account → Containers → your-container
2. Browse to `results/case_name_timestamp/`
3. Select files and click "Download"

#### Method 2: Azure Storage Explorer
1. Open Azure Storage Explorer
2. Navigate to your container → results
3. Right-click folder → "Download"

#### Method 3: Azure CLI
```bash
# Download all results for a specific case
az storage blob download-batch \
    --source your-container \
    --destination ./local_results \
    --pattern "results/kentucky_*/*" \
    --account-name your-storage-account \
    --account-key your-storage-key

# Download latest results
az storage blob download-batch \
    --source your-container \
    --destination ./latest_results \
    --pattern "results/*" \
    --account-name your-storage-account \
    --account-key your-storage-key
```

#### Method 4: Python Script
```python
from azure.storage.blob import BlobServiceClient
import os

connection_string = "your-connection-string"
container_name = "genx-data"

blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

# List all result folders
def list_results():
    blobs = container_client.list_blobs(name_starts_with="results/")
    folders = set()
    for blob in blobs:
        parts = blob.name.split('/')
        if len(parts) >= 2:
            folders.add(parts[1])
    return sorted(folders)

# Download specific result folder
def download_results(result_folder, local_path):
    blobs = container_client.list_blobs(name_starts_with=f"results/{result_folder}/")
    for blob in blobs:
        blob_client = container_client.get_blob_client(blob.name)
        
        # Create local directory structure
        local_file_path = os.path.join(local_path, blob.name)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        # Download file
        with open(local_file_path, "wb") as download_file:
            download_file.write(blob_client.download_blob().readall())
        print(f"Downloaded: {blob.name}")

# Usage
results = list_results()
print("Available results:", results)

# Download latest result
if results:
    latest = results[-1]
    download_results(latest, f"./downloaded_results/{latest}")
```

## Common Issues

### 1. No Results Uploaded
**Symptoms:** Job shows as succeeded but no results in blob storage
**Solutions:**
- Check container app logs for upload errors
- Verify Azure Storage account key is correct
- Ensure GenX actually produced output files

### 2. Job Fails Immediately
**Symptoms:** Container app job fails within seconds
**Solutions:**
- Check GitHub Actions logs for Docker build errors
- Verify case files exist in correct blob storage location
- Check for missing required GenX input files

### 3. Long Queue Times
**Symptoms:** Jobs stay in "Pending" status for extended periods
**Solutions:**
- Reduce `max_parallel` setting
- Check Azure subscription quotas
- Consider using smaller resource allocations

### 4. Automatic Triggering Not Working
**Symptoms:** File uploads don't trigger jobs
**Solutions:**
- Verify Event Grid subscription is active
- Check Azure Function logs for errors
- Ensure GitHub token has correct permissions

### Getting Help

#### Check Logs
1. **GitHub Actions logs:** Actions tab → Workflow run → Job details
2. **Container App logs:** Azure Portal → Container Apps → Logs
3. **Azure Function logs:** Azure Portal → Function App → Monitor

#### Resource Limits
- **Maximum parallel jobs:** Limited by Azure subscription quotas
- **Job timeout:** 2 hours (configurable in workflow)
- **Memory per job:** 0.5-4.0 GB
- **CPU per job:** 0.25-2.0 cores

---

# Cost Optimization

## Typical Costs (East US)

- **Small job** (1 core, 2GB, 30 min): ~$0.10
- **Medium job** (2 cores, 4GB, 60 min): ~$0.40
- **Large job** (2 cores, 4GB, 120 min): ~$0.80

## Strategies

1. **Right-size resources**: Start with 1 core, 2GB, scale up if needed
2. **Batch processing**: Group smaller cases together
3. **Time-based runs**: Use cheaper regions/times
4. **Auto-cleanup**: Workflow deletes completed jobs (optional)

## Performance Comparison

### Serial Execution (Original)
```
Total time = Case1 (60min) + Case2 (60min) + Case3 (60min) = 180 minutes
Total cost = 3 × $0.40 = $1.20
```

### Parallel Execution (New)
```
Total time = max(Case1, Case2, Case3) = 60 minutes
Total cost = 3 × $0.40 = $1.20 (same cost, 3x faster!)
```

## Tips
- Start with smaller resource allocations
- Use `max_parallel` to control concurrent usage
- Monitor costs in Azure Cost Management
- Consider scheduled runs during off-peak hours

---

# Best Practices

## File Organization
- Use descriptive case names (e.g., `kentucky_2030_high_renewables`)
- Keep case sizes reasonable (<1GB input data)
- Test with small cases first

## Resource Management
- Start with smaller resource allocations and scale up
- Use `max_parallel` to control costs
- Monitor Azure quotas and billing

## Batch Processing
- Group related cases for parallel execution
- Consider regional Azure deployments for large datasets
- Use Azure's spot instances for cost savings (if available)

## Success Indicators

Your system is working correctly when:
- [ ] Test case uploads trigger GitHub Actions workflows
- [ ] Container App jobs complete successfully  
- [ ] Results appear in blob storage with timestamps
- [ ] GitHub Actions shows green checkmarks
- [ ] Function app logs show successful triggers

## Next Steps

1. **Test with 2-3 small cases** first
2. **Monitor resource usage** and adjust
3. **Scale up** to larger batches
4. **Set up Event Grid** for automatic triggering
5. **Consider GPU instances** for very large models

---

# Support and Documentation

## Additional Resources

- **[Azure Container Apps Documentation](https://docs.microsoft.com/en-us/azure/container-apps/)**
- **[GenX.jl Documentation](https://genxproject.github.io/GenX.jl/dev/)**
- **GitHub repository issues** for bug reports and feature requests

## Support Channels

- For GenX-specific issues: Check GenX.jl documentation
- For Azure issues: Azure support portal
- For workflow issues: GitHub repository issues

---

**Ready to scale up!** This system provides a scalable, cost-effective way to run GenX optimization models in parallel using Azure's cloud infrastructure. Start with small test cases and gradually scale up to larger production workloads! 🚀
