#!/bin/zsh
# Quick Start Guide for GenX Azure Infrastructure
# Run this script to get started with your GenX cloud deployment

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 GenX Azure Infrastructure - Quick Start${NC}"
echo "=================================================="
echo ""

echo -e "${GREEN}✅ Implementation Status: COMPLETE${NC}"
echo ""

echo -e "${YELLOW}📋 Next Steps:${NC}"
echo ""

echo "1. 🏗️  Deploy Infrastructure:"
echo "   ./scripts/deploy_complete_workflow.sh"
echo ""

echo "2. 🧪 Validate Deployment:"
echo "   python scripts/validate_deployment.py --resource-group genx-rg --storage-account <storage-name> --registry <registry-name> --function-app <function-name>"
echo ""

echo "3. 📊 Monitor System:"
echo "   python scripts/production_monitor.py --resource-group genx-rg monitor"
echo ""

echo "4. 🔄 Upload Test Case:"
echo "   python scripts/azure_blob_utils.py upload --account-name <storage-account> --account-key <key> --container cases --local-path example_systems/1_three_zones --blob-prefix test-case"
echo ""

echo "5. 📈 Check Results:"
echo "   python scripts/azure_blob_utils.py list --account-name <storage-account> --account-key <key> --container results"
echo ""

echo -e "${BLUE}📚 Documentation:${NC}"
echo "- AZURE_README.md - Complete deployment and operational guide"
echo "- AZURE_QUICK_REFERENCE.md - Essential commands and quick access"
echo ""

echo -e "${GREEN}🎯 Your GenX Azure infrastructure is ready for production!${NC}"
echo ""

echo -e "${YELLOW}Need help? Check the documentation or run validation scripts.${NC}"
