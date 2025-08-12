#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Log Viewing Tool
Used to view TraePy application log files
"""

import os
import sys
from datetime import datetime

def view_logs(log_file_path="logs/traepy.log", lines=50):
    """
    View the last N lines of a log file
    
    Args:
        log_file_path: Log file path
        lines: Number of lines to display
    """
    if not os.path.exists(log_file_path):
        print(f"Log file does not exist: {log_file_path}")
        return
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # Get the last N lines
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        print(f"\n=== TraePy Log Viewer ===")
        print(f"File: {log_file_path}")
        print(f"Total lines: {len(all_lines)}")
        print(f"Displaying last {len(last_lines)} lines")
        print(f"View time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        for line in last_lines:
            print(line.rstrip())
            
    except Exception as e:
        print(f"Error reading log file: {e}")

def main():
    """
    Main function
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='TraePy Log Viewing Tool')
    parser.add_argument('-f', '--file', default='logs/traepy.log', 
                       help='Log file path (default: logs/traepy.log)')
    parser.add_argument('-n', '--lines', type=int, default=50,
                       help='Number of lines to display (default: 50)')
    
    args = parser.parse_args()
    
    view_logs(args.file, args.lines)

if __name__ == '__main__':
    main()