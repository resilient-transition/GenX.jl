# Azure Blob Storage Deployment Guide for GenX

This guide explains how to set up automated GenX model runs triggered by Azure Blob Storage uploads.

## Overview

The deployment consists of:
1. **Azure Blob Storage** - Stores input data and results
2. **Azure Event Grid** - Detects new file uploads
3. **GitHub Actions** - Runs the GenX model when triggered
4. **Automated Results** - Returns processed results to blob storage

## Setup Instructions

### 1. Prerequisites

- Azure subscription with storage account
- GitHub repository with GenX.jl code
- GitHub Personal Access Token with `repo` scope

### 2. Azure Storage Setup

1. Create or use existing Azure Storage Account
2. Create a container for GenX data (e.g., `genx-data`)
3. Note your storage account name and access key

### 3. GitHub Repository Secrets

Add the following secrets to your GitHub repository (Settings → Secrets and variables → Actions):

```
AZURE_STORAGE_ACCOUNT=your_storage_account_name
AZURE_STORAGE_KEY=your_storage_account_key
```

### 4. Directory Structure

Organize your blob storage with this structure:
```
container-name/
├── inputs/
│   ├── case1/
│   │   ├── settings/
│   │   ├── system/
│   │   └── *.csv files
│   └── case2/
└── results/
    ├── case1_20241209_143022/
    └── case2_20241209_150315/
```

## Usage

### Method 1: Manual Trigger

1. Go to GitHub Actions → "Azure Blob Storage GenX Pipeline"
2. Click "Run workflow"
3. Specify:
   - Container name
   - Input folder path
   - Case name

### Method 2: API Trigger

Use the included utility script:
```bash
python scripts/azure_blob_utils.py trigger \
  --account-name your_storage_account \
  --account-key your_key \
  --container genx-data \
  --blob-prefix inputs/case1 \
  --case-name case1 \
  --github-token your_token \
  --repo-owner your_username \
  --repo-name your_repo
```

### Method 3: Automatic Trigger (Event Grid)

For automatic triggering when files are uploaded, you'll need to set up Azure Event Grid:

1. In Azure Portal, go to your Storage Account
2. Navigate to Events → Event Subscriptions
3. Create new subscription with:
   - **Name**: `genx-blob-trigger`
   - **Event Types**: `Blob Created`
   - **Endpoint Type**: `Web Hook`
   - **Endpoint**: `https://api.github.com/repos/YOUR_USERNAME/YOUR_REPO/dispatches`
   - **Additional Headers**:
     - `Authorization`: `token YOUR_GITHUB_TOKEN`
     - `X-GitHub-Event`: `repository_dispatch`
     - `Content-Type`: `application/json`

## Utility Scripts

### Upload Data
```bash
python scripts/azure_blob_utils.py upload \
  --account-name your_storage_account \
  --account-key your_key \
  --container genx-data \
  --local-path ./local_case_folder \
  --blob-prefix inputs/case1
```

### Download Results
```bash
python scripts/azure_blob_utils.py download \
  --account-name your_storage_account \
  --account-key your_key \
  --container genx-data \
  --blob-prefix results/case1_20241209_143022 \
  --local-path ./downloaded_results
```

### List Files
```bash
python scripts/azure_blob_utils.py list \
  --account-name your_storage_account \
  --account-key your_key \
  --container genx-data \
  --blob-prefix results/
```

## Workflow Features

- **Julia 1.9** environment (recommended for GenX)
- **Dependency caching** for faster runs
- **Results timestamping** to avoid overwrites
- **Error handling** and detailed logging
- **Run summaries** in GitHub Actions
- **Cleanup** of temporary files

## Example: Complete Workflow

1. **Prepare your GenX case locally**:
   ```bash
   # Organize your case files
   mkdir -p my_case/settings
   mkdir -p my_case/system
   # Copy your CSV files, settings, etc.
   ```

2. **Upload to Azure Blob Storage**:
   ```bash
   python scripts/azure_blob_utils.py upload \
     --account-name mystorageaccount \
     --account-key "your_key_here" \
     --container genx-data \
     --local-path ./my_case \
     --blob-prefix inputs/my_case
   ```

3. **Trigger the GitHub workflow**:
   ```bash
   python scripts/azure_blob_utils.py trigger \
     --account-name mystorageaccount \
     --account-key "your_key_here" \
     --container genx-data \
     --blob-prefix inputs/my_case \
     --case-name my_case \
     --github-token "your_github_token" \
     --repo-owner your_username \
     --repo-name GenX.jl
   ```

4. **Monitor the run** in GitHub Actions

5. **Download results**:
   ```bash
   # First, list available results
   python scripts/azure_blob_utils.py list \
     --account-name mystorageaccount \
     --account-key "your_key_here" \
     --container genx-data \
     --blob-prefix results/
   
   # Download specific results
   python scripts/azure_blob_utils.py download \
     --account-name mystorageaccount \
     --account-key "your_key_here" \
     --container genx-data \
     --blob-prefix results/my_case_20241209_143022 \
     --local-path ./my_case_results
   ```

## Troubleshooting

### Common Issues

1. **Workflow not triggering**
   - Check GitHub Actions tab for any failed runs
   - Verify secrets are correctly set
   - Ensure blob container and paths exist

2. **Authentication errors**
   - Verify Azure storage account credentials
   - Check GitHub token permissions
   - Ensure secrets are correctly named

3. **GenX model errors**
   - Check input file format and completeness
   - Review workflow logs for Julia errors
   - Ensure all required CSV files are present

4. **Upload/Download failures**
   - Verify blob container exists
   - Check network connectivity
   - Ensure sufficient storage permissions

### Installing Dependencies for Local Testing

```bash
# Install Python dependencies
pip install azure-storage-blob requests pandas loguru upath

# Make the script executable
chmod +x scripts/azure_blob_utils.py
```

## Security Considerations

- Store sensitive credentials in GitHub Secrets
- Use Azure service principals with minimal permissions when possible
- Regularly rotate access keys and tokens
- Monitor access logs for unauthorized usage

## Support

For issues with this deployment:
1. Check the troubleshooting section above
2. Review GitHub Actions logs
3. Create an issue in the repository

