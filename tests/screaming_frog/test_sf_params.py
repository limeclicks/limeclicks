#!/usr/bin/env python
"""Test different Screaming Frog parameter combinations"""

import subprocess
import tempfile
import os

def test_parameter(param_name, value):
    """Test a specific parameter"""
    temp_dir = tempfile.mkdtemp()
    cmd = [
        '/usr/bin/screamingfrogseospider',
        '--headless',
        '--crawl', 'https://example.com',
        '--output-folder', temp_dir,
        param_name, str(value),
        '--overwrite'
    ]
    
    print(f"Testing: {param_name} {value}")
    
    env = os.environ.copy()
    env['DISPLAY'] = ''
    env['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, env=env)
        if "Unrecognized option" in result.stderr:
            print(f"  ❌ {param_name} not recognized")
            return False
        else:
            print(f"  ✅ {param_name} accepted")
            return True
    except subprocess.TimeoutExpired:
        print(f"  ⚠️  {param_name} timeout (might be working)")
        return True
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            os.system(f"rm -rf {temp_dir}")

print("Testing various parameter names for URL limit:")
print("=" * 60)

# Test different possible parameter names
params_to_test = [
    '--max-urls',
    '--max-url',
    '--max-crawl',
    '--crawl-limit',
    '--limit',
    '--max',
    '--maxurls'
]

for param in params_to_test:
    test_parameter(param, 100)

print("\nTrying without any limit parameter...")
temp_dir = tempfile.mkdtemp()
cmd = [
    '/usr/bin/screamingfrogseospider',
    '--headless',
    '--crawl', 'https://example.com',
    '--output-folder', temp_dir,
    '--overwrite',
    '--save-crawl'
]

print("Command: " + " ".join(cmd))

env = os.environ.copy()
env['DISPLAY'] = ''
env['QT_QPA_PLATFORM'] = 'offscreen'
env['SCREAMING_FROG_LICENSE'] = os.getenv('SCREAMING_FROG_LICENSE', '')

try:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
    print(f"Exit code: {result.returncode}")
    if result.returncode == 0:
        print("✅ Command executed successfully")
        files = os.listdir(temp_dir) if os.path.exists(temp_dir) else []
        print(f"Generated files: {files}")
    else:
        print(f"stderr: {result.stderr[:500] if result.stderr else 'None'}")
        print(f"stdout: {result.stdout[:500] if result.stdout else 'None'}")
except Exception as e:
    print(f"Error: {e}")
finally:
    if os.path.exists(temp_dir):
        os.system(f"rm -rf {temp_dir}")