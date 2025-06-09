#!/bin/bash

# GenX Azure Container Apps Deployment Script
# This script sets up the required Azure infrastructure for the GenX parallel processing system

set -e

echo "=== GenX Azure Container Apps Deployment ==="
echo "This script will create the required Azure resources for running GenX jobs in parallel."
echo ""

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-genx-rg}"
LOCATION="${LOCATION:-eastus}"
STORAGE_ACCOUNT="${STORAGE_ACCOUNT:-genxstor$(date +%s)}"
CONTAINER_NAME="${CONTAINER_NAME:-genx-data}"
FUNCTION_APP="${FUNCTION_APP:-genx-trigger-func-$(date +%s)}"

echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  Container Name: $CONTAINER_NAME"
echo "  Function App: $FUNCTION_APP"
echo ""

read -p "Continue with deployment? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Deployment cancelled."
    exit 0
fi

echo "=== Step 1: Creating Resource Group ==="
az group create \
    --name "$RESOURCE_GROUP" \
    --location "$LOCATION"

echo "✅ Resource group created: $RESOURCE_GROUP"

echo "=== Step 2: Creating Storage Account ==="
az storage account create \
    --name "$STORAGE_ACCOUNT" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku Standard_LRS \
    --kind StorageV2

echo "✅ Storage account created: $STORAGE_ACCOUNT"

echo "=== Step 3: Creating Blob Container ==="
az storage container create \
    --name "$CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --public-access off

echo "✅ Blob container created: $CONTAINER_NAME"

echo "=== Step 4: Getting Storage Account Key ==="
STORAGE_KEY=$(az storage account keys list \
    --resource-group "$RESOURCE_GROUP" \
    --account-name "$STORAGE_ACCOUNT" \
    --query "[0].value" -o tsv)

echo "✅ Storage key retrieved"

echo "=== Step 5: Creating Azure Function App ==="
az functionapp create \
    --resource-group "$RESOURCE_GROUP" \
    --consumption-plan-location "$LOCATION" \
    --runtime python \
    --runtime-version 3.9 \
    --functions-version 4 \
    --name "$FUNCTION_APP" \
    --storage-account "$STORAGE_ACCOUNT" \
    --os-type linux

echo "✅ Function app created: $FUNCTION_APP"

echo "=== Step 6: Creating Service Principal for GitHub Actions ==="
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)

# Create service principal
SP_OUTPUT=$(az ad sp create-for-rbac \
    --name "genx-github-actions" \
    --role "Contributor" \
    --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP" \
    --sdk-auth)

echo "✅ Service principal created"

echo "=== Step 7: Creating GitHub Secrets Template ==="
cat > github_secrets.txt << EOF
Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

AZURE_CREDENTIALS='$SP_OUTPUT'

AZURE_SUBSCRIPTION_ID=$SUBSCRIPTION_ID

AZURE_RESOURCE_GROUP=$RESOURCE_GROUP

AZURE_LOCATION=$LOCATION

AZURE_STORAGE_ACCOUNT=$STORAGE_ACCOUNT

AZURE_STORAGE_KEY=$STORAGE_KEY

Function App Configuration (Azure Portal → Function App → Configuration):
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=username/repository_name
GITHUB_WORKFLOW_ID=azure-container-apps-parallel.yml
EOF

echo "✅ GitHub secrets template created: github_secrets.txt"

echo "=== Step 8: Creating Event Grid System Topic ==="
TOPIC_NAME="genx-storage-events"
az eventgrid system-topic create \
    --name "$TOPIC_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --topic-type "Microsoft.Storage.StorageAccounts" \
    --source "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"

echo "✅ Event Grid system topic created: $TOPIC_NAME"

echo "=== Deployment Summary ==="
echo "✅ Resource Group: $RESOURCE_GROUP"
echo "✅ Storage Account: $STORAGE_ACCOUNT"
echo "✅ Blob Container: $CONTAINER_NAME"
echo "✅ Function App: $FUNCTION_APP"
echo "✅ Event Grid Topic: $TOPIC_NAME"
echo "✅ Service Principal: genx-github-actions"
echo ""
echo "🔑 GitHub secrets have been written to: github_secrets.txt"
echo ""
echo "Next steps:"
echo "1. Add the secrets from github_secrets.txt to your GitHub repository"
echo "2. Deploy the Azure Function using:"
echo "   cd azure-function && func azure functionapp publish $FUNCTION_APP"
echo "3. Create Event Grid subscription to link storage events to the function"
echo "4. Upload test data to: https://$STORAGE_ACCOUNT.blob.core.windows.net/$CONTAINER_NAME/inputs/"
echo ""
echo "Storage account connection string:"
echo "DefaultEndpointsProtocol=https;AccountName=$STORAGE_ACCOUNT;AccountKey=$STORAGE_KEY;EndpointSuffix=core.windows.net"
echo ""
echo "🎉 Deployment completed successfully!"
