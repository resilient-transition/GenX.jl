#!/bin/bash

# GenX Azure Container Apps Test Script
# This script tests the deployed system with a simple test case

set -e

echo "=== GenX Azure Container Apps Test ==="
echo "This script tests your GenX Azure Container Apps deployment."
echo ""

# Configuration
if [ $# -lt 2 ]; then
    echo "Usage: $0 <storage-account> <container-name> [case-name]"
    echo ""
    echo "Example:"
    echo "  $0 genxstor1234567890 genx-data test_case"
    echo ""
    exit 1
fi

STORAGE_ACCOUNT="$1"
CONTAINER_NAME="$2"
CASE_NAME="${3:-test_case}"

echo "Configuration:"
echo "  Storage Account: $STORAGE_ACCOUNT"
echo "  Container: $CONTAINER_NAME"
echo "  Test Case: $CASE_NAME"
echo ""

echo "=== Creating Test Case Files ==="
# Create a minimal test case
mkdir -p "test_data/$CASE_NAME/settings"
mkdir -p "test_data/$CASE_NAME/system"

# Create minimal GenX settings file
cat > "test_data/$CASE_NAME/settings/genx_settings.yml" << EOF
# Minimal GenX settings for testing
UCommit: 1
TimeDomainReduction: 0
NetworkExpansion: 0
EnergyShareRequirement: 0
CapacityReserveMargin: 0
MinCapReq: 0
MaxCapReq: 0
EOF

# Create minimal generators data
cat > "test_data/$CASE_NAME/system/Generators_data.csv" << EOF
Resource,Zone,THERM,VRE,STOR,DR,ESR_1,ESR_2,LDS,MUST_RUN,RETRO,COMMIT,New_Build,Can_Retire,Existing_Cap_MW,Existing_Cap_MWh,Cap_Size,Min_Cap_MW,Max_Cap_MW,Min_Cap_MWh,Max_Cap_MWh,Inv_Cost_per_MWyr,Fixed_OM_Cost_per_MWyr,Inv_Cost_per_MWhyr,Fixed_OM_Cost_per_MWhyr,Var_OM_Cost_per_MWh,Heat_Rate_MMBTU_per_MWh,Fuel,Start_Cost_per_MW,Start_Fuel_MMBTU_per_MW,Up_Time,Down_Time,Ramp_Up_Percentage,Ramp_Dn_Percentage,Min_Power,Eff_Up,Eff_Down,VRE_STOR_VRE_1,Reg_Max,Rsv_Max,Reg_Cost,Rsv_Cost,LT_TDR,LT_Dur,NACC,VRE_STOR_STOR_1,VRE_STOR_STOR_2,VRE_STOR_WIND_1,VRE_STOR_SOLAR_1,region,Resource_Type,cluster
test_gen,1,1,0,0,0,0,0,0,0,0,1,0,0,100,0,0,-1,-1,-1,-1,0,10000,0,0,50,10,NG,0,0,1,1,1,1,0.3,0,0,0,0,0,0,0,0,0,0,0,0,0,0,R1,natural_gas_combined_cycle,1
EOF

# Create minimal load data
cat > "test_data/$CASE_NAME/system/Load_data.csv" << EOF
Time_Index,Demand_MW_z1,Voll,Rep_Periods,Timesteps_per_Rep_Period,Sub_Weights
1,100,1000,1,1,1
EOF

echo "✅ Test case files created in test_data/$CASE_NAME/"

echo "=== Uploading Test Case to Azure Blob Storage ==="
# Upload test case
az storage blob upload-batch \
    --source "test_data/$CASE_NAME" \
    --destination "$CONTAINER_NAME" \
    --destination-path "inputs/$CASE_NAME" \
    --account-name "$STORAGE_ACCOUNT"

echo "✅ Test case uploaded to: inputs/$CASE_NAME/"

echo "=== Verifying Upload ==="
# List uploaded files
echo "Files in blob storage:"
az storage blob list \
    --container-name "$CONTAINER_NAME" \
    --prefix "inputs/$CASE_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --output table

echo ""
echo "=== Test Instructions ==="
echo "✅ Test case '$CASE_NAME' is ready!"
echo ""
echo "🔥 To test automatic triggering:"
echo "   - If Event Grid is configured, uploading files should have triggered a workflow"
echo "   - Check GitHub Actions for any new workflow runs"
echo ""
echo "🚀 To test manual triggering:"
echo "   1. Go to GitHub Actions tab"
echo "   2. Select 'Parallel GenX Jobs on Azure Container Apps' workflow"
echo "   3. Click 'Run workflow'"
echo "   4. Enter:"
echo "      - blob_container: $CONTAINER_NAME"
echo "      - case_names: $CASE_NAME"
echo "      - cpu_cores: 0.5"
echo "      - memory_gb: 1.0"
echo "      - max_parallel: 1"
echo "   5. Click 'Run workflow'"
echo ""
echo "📊 To check results:"
echo "   - Results will appear in: results/$CASE_NAME_TIMESTAMP/"
echo "   - Use Azure Portal or Azure Storage Explorer to browse"
echo ""
echo "🧹 Cleanup:"
rm -rf test_data
echo "   Test files cleaned up locally"
echo ""
echo "🎉 Test setup completed!"
