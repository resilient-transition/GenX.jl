# GenX Azure Container Apps - Deployment Verification Guide

This guide provides step-by-step instructions to verify that your GenX Azure Container Apps deployment is working correctly.

## Pre-Deployment Checklist

Before testing, ensure you have completed these steps:

### 1. Check Required Files Exist
```bash
# Navigate to GenX directory
cd /Users/roderick/PycharmProjects/resilient-transition/GenX.jl

# Verify key files exist
ls -la deploy_azure_infrastructure.sh setup_event_grid.sh test_deployment.sh
ls -la .github/workflows/azure-container-apps-parallel.yml
ls -la azure-function/function_app.py
ls -la Dockerfile startup.sh
```

### 2. Check Prerequisites
```bash
# Check Azure CLI
az version

# Check if logged into Azure
az account show

# Check Docker (if testing locally)
docker --version

# Check Julia installation
julia --version
```

## Testing Strategy: 3-Phase Approach

### Phase 1: Infrastructure Validation
### Phase 2: Component Testing  
### Phase 3: End-to-End Testing

---

## Phase 1: Infrastructure Validation

### Step 1.1: Deploy Azure Infrastructure

```bash
# Make script executable
chmod +x deploy_azure_infrastructure.sh

# Run deployment (will create all Azure resources)
./deploy_azure_infrastructure.sh

# Expected output:
# ✅ Resource group created
# ✅ Storage account created  
# ✅ Blob container created
# ✅ Function app created
# ✅ Service principal created
# ✅ Event Grid system topic created
```

**Verification:**
- Check that `github_secrets.txt` file was created
- Verify Azure resources in portal:
  ```bash
  # List created resources
  az resource list --resource-group YOUR_RESOURCE_GROUP --output table
  ```

### Step 1.2: Verify Storage Account

```bash
# List containers in storage account
az storage container list --account-name YOUR_STORAGE_ACCOUNT --output table

# Test upload to container
echo "test file" > test.txt
az storage blob upload \
    --account-name YOUR_STORAGE_ACCOUNT \
    --container-name YOUR_CONTAINER \
    --name "test/test.txt" \
    --file test.txt

# Verify upload
az storage blob list \
    --account-name YOUR_STORAGE_ACCOUNT \
    --container-name YOUR_CONTAINER \
    --prefix "test/" \
    --output table

# Clean up test file
rm test.txt
az storage blob delete \
    --account-name YOUR_STORAGE_ACCOUNT \
    --container-name YOUR_CONTAINER \
    --name "test/test.txt"
```

### Step 1.3: Verify GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add the secrets from `github_secrets.txt`:
   - `AZURE_CREDENTIALS`
   - `AZURE_SUBSCRIPTION_ID`
   - `AZURE_RESOURCE_GROUP`
   - `AZURE_LOCATION`
   - `AZURE_STORAGE_ACCOUNT`
   - `AZURE_STORAGE_KEY`

**Verification:**
- All 6 secrets should be visible in the repository secrets list
- Secrets should not show their values (for security)

---

## Phase 2: Component Testing

### Step 2.1: Test Dockerfile Build

```bash
# Build Docker image locally
docker build -t genx-test .

# Expected output:
# Successfully built [image-id]
# Successfully tagged genx-test:latest

# Check image exists
docker images | grep genx-test

# Optional: Test container startup (will fail without proper env vars, but should start)
docker run --rm genx-test echo "Container starts successfully"
```

### Step 2.2: Test Azure Function Deployment

```bash
# Navigate to function directory
cd azure-function

# Install Azure Functions Core Tools (if needed)
# macOS:
brew tap azure/functions
brew install azure-functions-core-tools@4

# Deploy function
func azure functionapp publish YOUR_FUNCTION_APP_NAME

# Expected output:
# Getting site publishing info...
# [Multiple deployment steps]
# Deployment successful
```

**Verification:**
```bash
# Check function status
az functionapp show \
    --name YOUR_FUNCTION_APP_NAME \
    --resource-group YOUR_RESOURCE_GROUP \
    --query "state" -o tsv
# Should return: Running

# Get function URL
az functionapp show \
    --name YOUR_FUNCTION_APP_NAME \
    --resource-group YOUR_RESOURCE_GROUP \
    --query "defaultHostName" -o tsv
```

### Step 2.3: Configure Function Environment Variables

In Azure Portal:
1. Navigate to your Function App
2. Go to **Configuration** → **Application settings**
3. Add these settings:
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `GITHUB_REPO`: `your-username/your-repo-name`
   - `GITHUB_WORKFLOW_ID`: `azure-container-apps-parallel.yml`

### Step 2.4: Set Up Event Grid

```bash
# Return to main directory
cd ..

# Run Event Grid setup
./setup_event_grid.sh YOUR_RESOURCE_GROUP YOUR_STORAGE_ACCOUNT YOUR_FUNCTION_APP

# Expected output:
# ✅ Function endpoint retrieved
# ✅ Event Grid subscription created
# ✅ Event Grid subscription is active
```

**Verification:**
```bash
# Check Event Grid subscription
az eventgrid event-subscription list \
    --source-resource-id "/subscriptions/YOUR_SUBSCRIPTION/resourceGroups/YOUR_RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/YOUR_STORAGE_ACCOUNT" \
    --output table
```

---

## Phase 3: End-to-End Testing

### Step 3.1: Manual Workflow Testing

1. **Go to GitHub Actions**:
   - Navigate to your repository → **Actions** tab
   - Should see "Parallel GenX Jobs on Azure Container Apps" workflow

2. **Trigger Manual Run**:
   - Click workflow → **Run workflow**
   - Fill in test parameters:
     ```
     blob_container: YOUR_CONTAINER_NAME
     case_names: test_case
     cpu_cores: 0.5
     memory_gb: 1.0
     max_parallel: 1
     ```
   - Click **Run workflow**

3. **Expected Behavior**:
   - Workflow should start immediately
   - Should fail at job execution (because test_case doesn't exist yet)
   - This confirms GitHub Actions integration works

### Step 3.2: Upload Test Case and Test Automatic Triggering

```bash
# Create and upload test case
./test_deployment.sh YOUR_STORAGE_ACCOUNT YOUR_CONTAINER_NAME test_case

# Expected output:
# ✅ Test case files created
# ✅ Test case uploaded to: inputs/test_case/
# [File listing in blob storage]
# 🎉 Test setup completed!
```

**Verification Steps:**

1. **Check File Upload**:
   ```bash
   # Verify files were uploaded
   az storage blob list \
       --account-name YOUR_STORAGE_ACCOUNT \
       --container-name YOUR_CONTAINER \
       --prefix "inputs/test_case" \
       --output table
   ```

2. **Check Function Trigger** (within 2-3 minutes):
   ```bash
   # Check function logs for trigger
   az functionapp log tail \
       --name YOUR_FUNCTION_APP \
       --resource-group YOUR_RESOURCE_GROUP
   
   # Look for log entries showing blob creation event
   ```

3. **Check GitHub Actions** (within 5 minutes):
   - Go to Actions tab in GitHub
   - Should see new workflow run triggered automatically
   - Workflow should process `test_case`

### Step 3.3: Complete End-to-End Test

Now run a complete test with the uploaded test case:

1. **Manual Trigger with Real Test Case**:
   - GitHub Actions → Run workflow
   - Parameters:
     ```
     blob_container: YOUR_CONTAINER_NAME
     case_names: test_case
     cpu_cores: 1.0
     memory_gb: 2.0
     max_parallel: 1
     ```

2. **Monitor Execution**:
   - Watch GitHub Actions progress
   - Check Azure Portal → Container Apps for job execution
   - Monitor for ~10-15 minutes (test case should be fast)

3. **Verify Results**:
   ```bash
   # Check for results in blob storage
   az storage blob list \
       --account-name YOUR_STORAGE_ACCOUNT \
       --container-name YOUR_CONTAINER \
       --prefix "results/" \
       --output table
   
   # Should see: results/test_case_YYYYMMDD_HHMMSS/
   ```

4. **Download and Inspect Results**:
   ```bash
   # Download results folder
   az storage blob download-batch \
       --source YOUR_CONTAINER \
       --destination ./test_results \
       --pattern "results/test_case_*/*" \
       --account-name YOUR_STORAGE_ACCOUNT
   
   # Check downloaded files
   find ./test_results -type f -name "*.txt" -o -name "*.csv" | head -10
   ```

---

## Success Indicators

### ✅ Your deployment is working if:

1. **Infrastructure**: All Azure resources created successfully
2. **GitHub Integration**: Workflows can be triggered manually
3. **Automatic Triggering**: File uploads trigger workflows within 5 minutes
4. **Job Execution**: Container Apps jobs complete successfully
5. **Results**: Output files appear in blob storage with timestamps
6. **Monitoring**: Can view logs in both GitHub Actions and Azure Portal

### ⚠️ Common Issues and Troubleshooting

#### Issue: Manual workflow fails immediately
**Solution**: Check GitHub secrets are set correctly
```bash
# Verify secrets in GitHub repository settings
# Re-run deploy_azure_infrastructure.sh if needed
```

#### Issue: Automatic triggering doesn't work
**Solution**: Check Event Grid and Function configuration
```bash
# Check Event Grid subscription
az eventgrid event-subscription show --name genx-blob-trigger --source-resource-id "YOUR_STORAGE_RESOURCE_ID"

# Check function logs
az functionapp log tail --name YOUR_FUNCTION_APP --resource-group YOUR_RESOURCE_GROUP
```

#### Issue: Container jobs fail
**Solution**: Check container logs and resources
```bash
# List recent container executions
az containerapp job execution list --job-name YOUR_JOB_NAME --resource-group YOUR_RESOURCE_GROUP

# Get job logs
az containerapp logs show --name YOUR_JOB_NAME --resource-group YOUR_RESOURCE_GROUP
```

#### Issue: No results uploaded
**Solution**: Check storage credentials and GenX output
- Verify `AZURE_STORAGE_KEY` is correct
- Check if GenX actually produced output files
- Review container logs for upload errors

---

## Advanced Testing

### Test Multiple Cases in Parallel

1. **Create Multiple Test Cases**:
   ```bash
   ./test_deployment.sh YOUR_STORAGE_ACCOUNT YOUR_CONTAINER case1
   ./test_deployment.sh YOUR_STORAGE_ACCOUNT YOUR_CONTAINER case2
   ./test_deployment.sh YOUR_STORAGE_ACCOUNT YOUR_CONTAINER case3
   ```

2. **Trigger Parallel Execution**:
   - GitHub Actions → Run workflow
   - `case_names`: `case1,case2,case3`
   - `max_parallel`: `3`

3. **Monitor Parallel Jobs**:
   - Should see 3 container jobs running simultaneously
   - All should complete and upload results

### Performance Testing

1. **Resource Scaling Test**:
   - Try different CPU/memory combinations
   - Monitor execution times and costs

2. **Load Testing**:
   - Upload 5-10 cases simultaneously
   - Verify automatic triggering handles multiple events

### Cost Monitoring

```bash
# Check current Azure costs
az consumption usage list --output table

# Monitor resource usage
az monitor metrics list --resource YOUR_CONTAINER_APP_ID --metric "CPU" --output table
```

---

## Final Verification Checklist

- [ ] Infrastructure deployed successfully
- [ ] GitHub secrets configured
- [ ] Docker image builds locally
- [ ] Azure Function deployed and configured
- [ ] Event Grid subscription active
- [ ] Manual workflow execution works
- [ ] Automatic triggering works (file upload → workflow)
- [ ] Test case completes successfully
- [ ] Results uploaded to blob storage
- [ ] Can download and inspect results
- [ ] Parallel execution works with multiple cases
- [ ] Monitoring works in both GitHub and Azure
- [ ] Cost tracking is visible in Azure Portal

## 🎉 Success!

If all items in the checklist pass, your GenX Azure Container Apps deployment is fully functional and ready for production use!

**Next Steps:**
1. Upload your real GenX cases to the `inputs/` folder
2. Scale up to larger parallel workloads
3. Set up cost alerts in Azure
4. Consider automation for regular batch processing
