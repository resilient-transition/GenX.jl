#!/usr/bin/env python3
"""
Test script to validate the GenX Event Grid workflow setup.
This script checks all components before deploying to Azure.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import tempfile

def check_file_exists(filepath, description):
    """Check if a required file exists."""
    if Path(filepath).exists():
        print(f"✅ {description}: {filepath}")
        return True
    else:
        print(f"❌ Missing {description}: {filepath}")
        return False

def check_docker_build(dockerfile, image_name):
    """Test Docker build locally."""
    print(f"\n🐳 Testing Docker build: {dockerfile}")
    try:
        cmd = ["docker", "build", "-f", dockerfile, "-t", image_name, "."]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ Docker build successful: {image_name}")
            return True
        else:
            print(f"❌ Docker build failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Docker build timed out")
        return False
    except Exception as e:
        print(f"❌ Docker build error: {e}")
        return False

def validate_azure_function():
    """Validate Azure Function code."""
    print("\n⚡ Validating Azure Function...")
    
    function_file = "azure-function/function_app.py"
    requirements_file = "azure-function/requirements.txt"
    host_file = "azure-function/host.json"
    
    all_valid = True
    
    # Check files exist
    all_valid &= check_file_exists(function_file, "Function App code")
    all_valid &= check_file_exists(requirements_file, "Function requirements")
    all_valid &= check_file_exists(host_file, "Function host config")
    
    # Check function imports
    if Path(function_file).exists():
        with open(function_file) as f:
            content = f.read()
            if "azure.functions" in content and "EventGridEvent" in content:
                print("✅ Function imports look correct")
            else:
                print("❌ Function imports may be incorrect")
                all_valid = False
    
    return all_valid

def create_test_case():
    """Create a minimal test case for validation."""
    print("\n📁 Creating test case...")
    
    test_dir = Path("test_case_validation")
    test_dir.mkdir(exist_ok=True)
    
    # Create minimal GenX settings
    settings_content = """
NetworkExpansion: 0
Trans_Loss_Segments: 1
Reserves: 0
EnergyShareRequirement: 0
CapacityReserveMargin: 0
CO2Cap: 0
ParameterScale: 1
WriteShadowPrices: 1
UCommit: 0
TimeDomainReduction: 0
"""
    
    # Create minimal load data
    load_content = """Time_Index,Load_MW_z1,Load_MW_z2,Load_MW_z3
1,1000,800,600
2,1100,850,650
3,1050,825,625
4,1000,800,600
"""
    
    # Create minimal generator data
    gen_content = """Resource,Zone,Fuel,Var_OM_Cost_per_MWh,Start_Cost_per_MW,Cap_Size,Existing_Cap_MW,Max_Cap_MW,Min_Cap_MW,Inv_Cost_per_MWyr,Fixed_OM_Cost_per_MWyr,Heat_Rate_MMBTU_per_MWh,WACC,Capital_Recovery_Period,Lifetime
Gas_1,1,Natural_Gas,50,100,100,500,1000,0,100000,10000,7.5,0.07,20,30
Gas_2,2,Natural_Gas,55,100,100,400,800,0,100000,10000,7.5,0.07,20,30
Gas_3,3,Natural_Gas,60,100,100,300,600,0,100000,10000,7.5,0.07,20,30
"""
    
    # Create fuel data
    fuel_content = """Fuel,CO2_Content_Tons_per_MMBtu,Fuel_Price_per_MMBtu
Natural_Gas,0.0531,4.0
"""
    
    # Write test files
    (test_dir / "genx_settings.yml").write_text(settings_content)
    (test_dir / "Load_data.csv").write_text(load_content)
    (test_dir / "Generators_data.csv").write_text(gen_content)
    (test_dir / "Fuels_data.csv").write_text(fuel_content)
    
    print(f"✅ Test case created: {test_dir}")
    return test_dir

def test_azure_blob_utils():
    """Test the Azure blob utilities script."""
    print("\n☁️  Testing Azure blob utilities...")
    
    script_path = "scripts/azure_blob_utils.py"
    if not Path(script_path).exists():
        print(f"❌ Script not found: {script_path}")
        return False
    
    try:
        # Test help output
        result = subprocess.run([sys.executable, script_path, "--help"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "Azure Blob Storage utilities" in result.stdout:
            print("✅ Azure blob utilities script working")
            return True
        else:
            print("❌ Azure blob utilities script has issues")
            return False
    except Exception as e:
        print(f"❌ Error testing blob utils: {e}")
        return False

def main():
    """Main validation function."""
    print("🔍 GenX Event Grid Workflow Validation")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check required files
    print("\n📋 Checking required files...")
    required_files = [
        ("Dockerfile.eventgrid", "Event Grid Dockerfile"),
        ("scripts/setup_event_grid.sh", "Setup script"),
        ("scripts/monitor_deployment.sh", "Monitor script"),
        ("scripts/run_genx_case.py", "GenX case runner"),
        ("EVENT_GRID_README.md", "Documentation"),
        (".github/workflows/eventgrid-deploy.yml", "GitHub Actions workflow")
    ]
    
    for filepath, description in required_files:
        all_checks_passed &= check_file_exists(filepath, description)
    
    # Validate Azure Function
    all_checks_passed &= validate_azure_function()
    
    # Test Azure blob utilities
    all_checks_passed &= test_azure_blob_utils()
    
    # Create test case
    test_case_dir = create_test_case()
    
    # Test Docker builds (optional - can be slow)
    test_docker = os.environ.get('TEST_DOCKER_BUILD', 'false').lower() == 'true'
    if test_docker:
        print("\n🐳 Testing Docker builds...")
        all_checks_passed &= check_docker_build("Dockerfile", "genx-test")
        all_checks_passed &= check_docker_build("Dockerfile.eventgrid", "genx-eventgrid-test")
    else:
        print("\n🐳 Skipping Docker build tests (set TEST_DOCKER_BUILD=true to enable)")
    
    # Final summary
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("🎉 All validation checks passed!")
        print("\n📋 Next steps:")
        print("1. Deploy infrastructure: ./scripts/setup_event_grid.sh")
        print("2. Deploy function: cd azure-function && func azure functionapp publish genx-eventgrid-function")
        print("3. Test the system: ./scripts/monitor_deployment.sh test")
        print("4. Monitor processing: ./scripts/monitor_deployment.sh logs")
        print("\n📁 Test case created at:", test_case_dir)
    else:
        print("❌ Some validation checks failed. Please fix the issues above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
