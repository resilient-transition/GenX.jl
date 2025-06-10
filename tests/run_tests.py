#!/usr/bin/env python3
"""
Test runner for all GenX Azure deployment tests
"""

import os
import sys
import subprocess
import logging

def setup_logging():
    """Setup logging for test runner"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)

def install_test_dependencies():
    """Install required test dependencies"""
    logger = logging.getLogger(__name__)
    
    dependencies = [
        'pytest',
        'pytest-mock',
        'pytest-cov',
        'azure-functions',
        'azure-storage-blob',
        'azure-eventgrid',
        'azure-mgmt-containerinstance',
        'azure-identity'
    ]
    
    logger.info("Installing test dependencies...")
    
    for dep in dependencies:
        try:
            result = subprocess.run([
                sys.executable, '-m', 'pip', 'install', dep
            ], capture_output=True, text=True, check=True)
            logger.info(f"✓ Installed {dep}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠ Failed to install {dep}: {e}")
            logger.info(f"Stderr: {e.stderr}")

def run_tests():
    """Run all tests"""
    logger = logging.getLogger(__name__)
    
    test_files = [
        'test_azure_function.py',
        'test_blob_integration.py', 
        'test_eventgrid_integration.py',
        'test_end_to_end.py'
    ]
    
    test_dir = os.path.dirname(__file__)
    results = {}
    
    for test_file in test_files:
        test_path = os.path.join(test_dir, test_file)
        if os.path.exists(test_path):
            logger.info(f"Running {test_file}...")
            try:
                result = subprocess.run([
                    sys.executable, '-m', 'pytest', test_path, '-v', '--tb=short'
                ], capture_output=True, text=True)
                
                results[test_file] = {
                    'returncode': result.returncode,
                    'stdout': result.stdout,
                    'stderr': result.stderr
                }
                
                if result.returncode == 0:
                    logger.info(f"✓ {test_file} passed")
                else:
                    logger.error(f"✗ {test_file} failed")
                    if result.stderr:
                        logger.error(f"Error output: {result.stderr}")
                        
            except Exception as e:
                logger.error(f"✗ Failed to run {test_file}: {e}")
                results[test_file] = {'error': str(e)}
        else:
            logger.warning(f"⚠ Test file {test_file} not found")
    
    return results

def print_summary(results):
    """Print test summary"""
    logger = logging.getLogger(__name__)
    
    logger.info("\n" + "="*50)
    logger.info("TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    failed = 0
    
    for test_file, result in results.items():
        if 'error' in result:
            logger.error(f"✗ {test_file}: ERROR - {result['error']}")
            failed += 1
        elif result['returncode'] == 0:
            logger.info(f"✓ {test_file}: PASSED")
            passed += 1
        else:
            logger.error(f"✗ {test_file}: FAILED")
            failed += 1
    
    logger.info(f"\nTotal: {passed + failed}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    
    if failed == 0:
        logger.info("🎉 All tests passed!")
        return True
    else:
        logger.warning(f"⚠ {failed} test(s) failed")
        return False

def main():
    """Main test runner"""
    logger = setup_logging()
    
    logger.info("Starting GenX Azure deployment test suite...")
    
    # Install dependencies
    install_test_dependencies()
    
    # Run tests
    results = run_tests()
    
    # Print summary
    success = print_summary(results)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
