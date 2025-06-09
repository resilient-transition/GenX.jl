#!/bin/bash

# Test Azure Container Apps Deployment by Uploading a Real GenX Case
# This script uploads one of your existing GenX cases to Azure Blob Storage to test the deployment

set -e

echo "=== GenX Azure Container Apps - Upload Test ==="
echo "This script will upload a real GenX case to test your deployment."
echo ""

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first:"
    echo "   macOS: brew install azure-cli"
    echo "   Then run: az login"
    exit 1
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    echo "❌ Not logged in to Azure. Please run: az login"
    exit 1
fi

# Configuration - you'll need to update these
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-}"
CONTAINER_NAME="${CONTAINER_NAME:-genx-data}"
RESOURCE_GROUP="${RESOURCE_GROUP:-}"

# Prompt for missing configuration
if [ -z "$STORAGE_ACCOUNT" ]; then
    echo "Enter your Azure Storage Account name:"
    read -r STORAGE_ACCOUNT
fi

if [ -z "$RESOURCE_GROUP" ]; then
    echo "Enter your Azure Resource Group name:"
    read -r RESOURCE_GROUP
fi

echo ""
echo "Configuration:"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  Container: $CONTAINER_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo ""

# Verify storage account exists
if ! az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo "❌ Storage account '$STORAGE_ACCOUNT' not found in resource group '$RESOURCE_GROUP'"
    echo "   Please check your configuration or run deploy_azure_infrastructure.sh first"
    exit 1
fi

echo "✅ Storage account verified"

# Available case folders
echo "Available GenX case folders:"
echo "1. KRC-6Years-24Days-NoPlan-Retire-BBB-NoGasAfter2040-Wind10GW (2025-06-05)"
echo "2. KRC-6Years-24Days-NoPlan-Retire-BBB-NoGasAfter2040-Wind1GW (2025-06-05)"
echo "3. KRC-6Years-24Days-NoPlan-Retire-IRA-NoGasAfter2040-Wind10GW (2025-06-05)"
echo "4. KRC-6Years-24Days-NoPlan-Retire-IRA-NoGasAfter2040-Wind1GW (2025-06-05)"
echo ""

# Select a test case (default to option 1)
echo "Which case would you like to upload for testing? [1-4, default: 1]:"
read -r CASE_CHOICE

case $CASE_CHOICE in
    1|"")
        CASE_NAME="KRC-BBB-Wind10GW"
        CASE_PATH="example_systems/1_three_zones"
        ;;
    2)
        CASE_NAME="KRC-BBB-Wind1GW"
        CASE_PATH="cases/2025-06-05/KRC-6Years-24Days-NoPlan-Retire-BBB-NoGasAfter2040-Wind1GW"
        ;;
    3)
        CASE_NAME="KRC-IRA-Wind10GW"
        CASE_PATH="cases/2025-06-05/KRC-6Years-24Days-NoPlan-Retire-IRA-NoGasAfter2040-Wind10GW"
        ;;
    4)
        CASE_NAME="KRC-IRA-Wind1GW"
        CASE_PATH="cases/2025-06-05/KRC-6Years-24Days-NoPlan-Retire-IRA-NoGasAfter2040-Wind1GW"
        ;;
    *)
        echo "Invalid choice. Using default case 1."
        CASE_NAME="KRC-BBB-Wind10GW"
        CASE_PATH="cases/2025-06-05/KRC-6Years-24Days-NoPlan-Retire-BBB-NoGasAfter2040-Wind10GW"
        ;;
esac

echo "Selected case: $CASE_NAME"
echo "Path: $CASE_PATH"

# Verify case exists
if [ ! -d "$CASE_PATH" ]; then
    echo "❌ Case directory not found: $CASE_PATH"
    exit 1
fi

echo ""
echo "=== Checking Case Structure ==="

# Check required directories
REQUIRED_DIRS=("inputs" "settings")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$CASE_PATH/$dir" ]; then
        echo "✅ Found: $dir/"
        # List contents briefly
        echo "   Contents: $(ls "$CASE_PATH/$dir" | tr '\n' ' ')"
    else
        echo "❌ Missing: $dir/"
    fi
done

echo ""
read -p "Continue with upload? [y/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Upload cancelled."
    exit 0
fi

echo "=== Uploading Case to Azure Blob Storage ==="

# Upload inputs directory
echo "Uploading inputs..."
if [ -d "$CASE_PATH/inputs" ]; then
    az storage blob upload-batch \
        --source "$CASE_PATH/inputs" \
        --destination "$CONTAINER_NAME" \
        --destination-path "inputs/$CASE_NAME" \
        --account-name "$STORAGE_ACCOUNT" \
        --overwrite \
        --output table
else
    echo "❌ No inputs directory found"
    exit 1
fi

# Upload settings directory
echo ""
echo "Uploading settings..."
if [ -d "$CASE_PATH/settings" ]; then
    az storage blob upload-batch \
        --source "$CASE_PATH/settings" \
        --destination "$CONTAINER_NAME" \
        --destination-path "inputs/$CASE_NAME/settings" \
        --account-name "$STORAGE_ACCOUNT" \
        --overwrite \
        --output table
else
    echo "❌ No settings directory found"
    exit 1
fi

echo ""
echo "✅ Upload completed!"

echo ""
echo "=== Verifying Upload ==="
echo "Files uploaded to blob storage:"
az storage blob list \
    --container-name "$CONTAINER_NAME" \
    --prefix "inputs/$CASE_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --output table

echo ""
echo "=== Testing Results ==="
echo "✅ Case '$CASE_NAME' uploaded successfully!"
echo ""
echo "🔥 What should happen next:"
echo "   1. If Event Grid is configured, a GitHub Actions workflow should trigger automatically"
echo "   2. Check GitHub Actions tab for new workflow runs"
echo "   3. Monitor the 'Parallel GenX Jobs on Azure Container Apps' workflow"
echo ""
echo "🚀 Manual testing (if automatic trigger doesn't work):"
echo "   1. Go to GitHub Actions → Parallel GenX Jobs on Azure Container Apps"
echo "   2. Click 'Run workflow'"
echo "   3. Enter:"
echo "      - blob_container: $CONTAINER_NAME"
echo "      - case_names: $CASE_NAME"
echo "      - cpu_cores: 2.0"
echo "      - memory_gb: 4.0"
echo "      - max_parallel: 1"
echo "   4. Click 'Run workflow'"
echo ""
echo "📊 Monitor progress:"
echo "   - GitHub Actions: https://github.com/YOUR_USERNAME/YOUR_REPO/actions"
echo "   - Azure Portal: Container Apps in resource group '$RESOURCE_GROUP'"
echo "   - Results will appear in: $CONTAINER_NAME/results/$CASE_NAME_TIMESTAMP/"
echo ""
echo "🎉 Deployment test initiated! Check GitHub Actions for workflow execution."
