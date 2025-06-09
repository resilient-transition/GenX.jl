#!/bin/bash

# Quick Azure Infrastructure Check
# This script verifies that your Azure Container Apps infrastructure is properly deployed

set -e

echo "=== Azure Infrastructure Health Check ==="
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI not installed"
    exit 1
fi

# Check login
if ! az account show &> /dev/null; then
    echo "❌ Not logged in to Azure"
    echo "Run: az login"
    exit 1
fi

SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)
echo "✅ Azure CLI logged in"
echo "   Subscription: $SUBSCRIPTION_ID"

# Get user input for resource names
echo ""
echo "Enter your resource information (from deploy_azure_infrastructure.sh output):"
read -p "Resource Group name: " RESOURCE_GROUP
read -p "Storage Account name: " STORAGE_ACCOUNT
read -p "Function App name (optional): " FUNCTION_APP

echo ""
echo "=== Checking Resources ==="

# Check Resource Group
if az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    echo "✅ Resource Group: $RESOURCE_GROUP"
else
    echo "❌ Resource Group not found: $RESOURCE_GROUP"
    exit 1
fi

# Check Storage Account
if az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    echo "✅ Storage Account: $STORAGE_ACCOUNT"
    
    # Check container
    if az storage container show --name "genx-data" --account-name "$STORAGE_ACCOUNT" &> /dev/null; then
        echo "✅ Blob Container: genx-data"
    else
        echo "❌ Blob Container 'genx-data' not found"
    fi
else
    echo "❌ Storage Account not found: $STORAGE_ACCOUNT"
    exit 1
fi

# Check Function App (if provided)
if [ -n "$FUNCTION_APP" ]; then
    if az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        echo "✅ Function App: $FUNCTION_APP"
        
        # Check function status
        STATE=$(az functionapp show --name "$FUNCTION_APP" --resource-group "$RESOURCE_GROUP" --query "state" -o tsv)
        echo "   State: $STATE"
    else
        echo "❌ Function App not found: $FUNCTION_APP"
    fi
fi

# Check GitHub Actions workflow file
if [ -f ".github/workflows/azure-container-apps-parallel.yml" ]; then
    echo "✅ GitHub Actions workflow file exists"
else
    echo "❌ GitHub Actions workflow file missing"
    echo "   Expected: .github/workflows/azure-container-apps-parallel.yml"
fi

# Check if GitHub secrets file exists (from deployment)
if [ -f "github_secrets.txt" ]; then
    echo "✅ GitHub secrets template exists"
    echo ""
    echo "📋 GitHub Secrets Status:"
    echo "   Please verify these secrets are configured in your GitHub repository:"
    echo "   Settings → Secrets and variables → Actions → Repository secrets"
    echo ""
    grep "^[A-Z_]*=" github_secrets.txt | cut -d'=' -f1 | while read secret; do
        echo "   - $secret"
    done
else
    echo "⚠️  GitHub secrets template not found"
    echo "   Run deploy_azure_infrastructure.sh to generate secrets"
fi

echo ""
echo "=== Next Steps ==="
echo ""
if [ -f "github_secrets.txt" ]; then
    echo "1. ✅ Ensure GitHub secrets are configured (see github_secrets.txt)"
else
    echo "1. ❌ Run: ./deploy_azure_infrastructure.sh"
fi

if [ -n "$FUNCTION_APP" ]; then
    echo "2. ✅ Deploy Azure Function: cd azure-function && func azure functionapp publish $FUNCTION_APP"
    echo "3. ✅ Set up Event Grid: ./setup_event_grid.sh $RESOURCE_GROUP $STORAGE_ACCOUNT $FUNCTION_APP"
else
    echo "2. ❌ Create Function App (see deploy_azure_infrastructure.sh)"
fi

echo "4. 🧪 Test upload: ./test_upload_case.sh"
echo ""
echo "🎯 Infrastructure Status: $([ -f "github_secrets.txt" ] && echo "Ready for testing" || echo "Needs deployment")"
