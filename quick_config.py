#!/usr/bin/env python3
"""
Quick Camera Configuration Tool

This script allows you to quickly test different camera configurations
without manually editing config.py each time.

Usage:
    python quick_config.py [configuration_name]

Available configurations:
    - single    : 1 camera
    - two       : 2 cameras  
    - four      : 4 cameras
    - six       : 6 cameras
    - all       : 7 cameras (default)
    - webcam    : Webcam only
    - mixed     : Webcam + 2 RTSP cameras
    - large     : 12 cameras

Examples:
    python quick_config.py webcam
    python quick_config.py two
    python quick_config.py large
"""

import sys
import shutil
from config_examples import *

# Configuration mapping
CONFIGS = {
    'single': SINGLE_CAMERA,
    'two': TWO_CAMERAS,
    'four': FOUR_CAMERAS,
    'six': SIX_CAMERAS,
    'all': ALL_CAMERAS,
    'webcam': WEBCAM_ONLY,
    'mixed': MIXED_CAMERAS,
    'large': LARGE_SETUP
}

def update_config(config_name='all'):
    """Update config.py with the specified configuration."""
    
    if config_name not in CONFIGS:
        print(f"[ERROR] Unknown configuration: {config_name}")
        print(f"[INFO] Available configurations: {', '.join(CONFIGS.keys())}")
        return False
    
    # Backup original config
    try:
        shutil.copy('config.py', 'config.py.backup')
        print("[INFO] Created backup: config.py.backup")
    except Exception as e:
        print(f"[WARN] Could not create backup: {e}")
    
    # Read current config
    try:
        with open('config.py', 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read config.py: {e}")
        return False
    
    # Find and replace CAMERA_STREAMS
    lines = content.split('\n')
    new_lines = []
    in_camera_streams = False
    brace_count = 0
    
    for line in lines:
        if 'CAMERA_STREAMS = {' in line:
            in_camera_streams = True
            brace_count = line.count('{') - line.count('}')
            # Replace with new configuration
            new_lines.append('CAMERA_STREAMS = {')
            selected_config = CONFIGS[config_name]
            for url, location in selected_config.items():
                if isinstance(url, int):
                    new_lines.append(f'    {url}: "{location}",')
                else:
                    new_lines.append(f'    "{url}": "{location}",')
            new_lines.append('}')
            
        elif in_camera_streams:
            brace_count += line.count('{') - line.count('}')
            if brace_count <= 0:
                in_camera_streams = False
            # Skip lines that are part of the old CAMERA_STREAMS
            continue
        else:
            new_lines.append(line)
    
    # Write updated config
    try:
        with open('config.py', 'w') as f:
            f.write('\n'.join(new_lines))
        
        selected_config = CONFIGS[config_name]
        num_cameras = len(selected_config)
        
        print(f"[SUCCESS] Updated config.py with '{config_name}' configuration")
        print(f"[INFO] Number of cameras: {num_cameras}")
        print(f"[INFO] Cameras configured:")
        for i, (url, location) in enumerate(selected_config.items(), 1):
            print(f"  {i}. {location}: {url}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Could not write config.py: {e}")
        return False

def main():
    config_name = 'all'  # default
    
    if len(sys.argv) > 1:
        config_name = sys.argv[1].lower()
    
    if config_name in ['-h', '--help', 'help']:
        print(__doc__)
        return
    
    print(f"[INFO] Setting up configuration: {config_name}")
    
    if update_config(config_name):
        print(f"\n[INFO] Configuration '{config_name}' is now active!")
        print(f"[INFO] You can now run: python main_app.py")
        print(f"[INFO] To restore original config: mv config.py.backup config.py")
    else:
        print(f"[ERROR] Failed to update configuration")

if __name__ == "__main__":
    main()
