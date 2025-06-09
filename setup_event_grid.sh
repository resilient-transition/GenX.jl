#!/bin/bash

# Event Grid Setup Script for GenX Azure Container Apps
# This script creates the Event Grid subscription to connect blob storage events to the Azure Function

set -e

echo "=== GenX Event Grid Setup ==="
echo "This script creates the Event Grid subscription to automatically trigger GenX jobs when files are uploaded."
echo ""

# Check if required parameters are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <resource-group> <storage-account> <function-app-name>"
    echo ""
    echo "Example:"
    echo "  $0 genx-rg genxstor1234567890 genx-trigger-func-1234567890"
    echo ""
    exit 1
fi

RESOURCE_GROUP="$1"
STORAGE_ACCOUNT="$2"
FUNCTION_APP="$3"
SUBSCRIPTION_NAME="genx-blob-trigger"

echo "Configuration:"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  Function App: $FUNCTION_APP"
echo "  Subscription Name: $SUBSCRIPTION_NAME"
echo ""

read -p "Continue with Event Grid setup? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo "=== Step 1: Getting Function Details ==="
SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)
FUNCTION_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Web/sites/$FUNCTION_APP"

# Get function key
echo "Getting function access key..."
FUNCTION_KEY=$(az functionapp keys list \
    --name "$FUNCTION_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "functionKeys.default" -o tsv)

if [ -z "$FUNCTION_KEY" ]; then
    echo "Warning: Could not retrieve function key. Using master key..."
    FUNCTION_KEY=$(az functionapp keys list \
        --name "$FUNCTION_APP" \
        --resource-group "$RESOURCE_GROUP" \
        --query "masterKey" -o tsv)
fi

# Get function hostname
FUNCTION_HOSTNAME=$(az functionapp show \
    --name "$FUNCTION_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --query "defaultHostName" -o tsv)

WEBHOOK_ENDPOINT="https://$FUNCTION_HOSTNAME/api/BlobTriggerGenX?code=$FUNCTION_KEY"

echo "✅ Function endpoint: https://$FUNCTION_HOSTNAME"

echo "=== Step 2: Creating Event Grid Subscription ==="
# Storage account resource ID
STORAGE_RESOURCE_ID="/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.Storage/storageAccounts/$STORAGE_ACCOUNT"

# Create Event Grid subscription
az eventgrid event-subscription create \
    --name "$SUBSCRIPTION_NAME" \
    --source-resource-id "$STORAGE_RESOURCE_ID" \
    --endpoint "$WEBHOOK_ENDPOINT" \
    --endpoint-type webhook \
    --included-event-types Microsoft.Storage.BlobCreated \
    --subject-begins-with "/blobServices/default/containers/genx-data/blobs/inputs/" \
    --advanced-filter data.api stringin PutBlob PutBlockList \
    --max-delivery-attempts 3 \
    --event-ttl 1440

echo "✅ Event Grid subscription created: $SUBSCRIPTION_NAME"

echo "=== Step 3: Testing Event Grid Subscription ==="
echo "Verifying Event Grid subscription..."

# Get subscription details
SUBSCRIPTION_STATUS=$(az eventgrid event-subscription show \
    --name "$SUBSCRIPTION_NAME" \
    --source-resource-id "$STORAGE_RESOURCE_ID" \
    --query "provisioningState" -o tsv)

if [ "$SUBSCRIPTION_STATUS" = "Succeeded" ]; then
    echo "✅ Event Grid subscription is active and ready"
else
    echo "⚠️  Event Grid subscription status: $SUBSCRIPTION_STATUS"
    echo "   This may take a few minutes to become active."
fi

echo "=== Setup Complete ==="
echo "✅ Event Grid subscription: $SUBSCRIPTION_NAME"
echo "✅ Webhook endpoint: https://$FUNCTION_HOSTNAME/api/BlobTriggerGenX"
echo "✅ Monitoring path: /blobServices/default/containers/genx-data/blobs/inputs/"
echo ""
echo "🎯 How to test:"
echo "1. Upload a file to: inputs/test_case/settings/genx_settings.yml"
echo "2. Check Azure Function logs for trigger event"
echo "3. Verify GitHub Actions workflow is triggered"
echo ""
echo "📋 Monitoring commands:"
echo "# Check Event Grid subscription"
echo "az eventgrid event-subscription show --name $SUBSCRIPTION_NAME --source-resource-id $STORAGE_RESOURCE_ID"
echo ""
echo "# View Function logs"
echo "az functionapp log tail --name $FUNCTION_APP --resource-group $RESOURCE_GROUP"
echo ""
echo "🎉 Event Grid setup completed successfully!"
