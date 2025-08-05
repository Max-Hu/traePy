#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志查看工具
用于查看TraePy应用的日志文件
"""

import os
import sys
from datetime import datetime

def view_logs(log_file_path="logs/traepy.log", lines=50):
    """
    查看日志文件的最后N行
    
    Args:
        log_file_path: 日志文件路径
        lines: 显示的行数
    """
    if not os.path.exists(log_file_path):
        print(f"日志文件不存在: {log_file_path}")
        return
    
    try:
        with open(log_file_path, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            
        # 获取最后N行
        last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        print(f"\n=== TraePy 日志查看器 ===")
        print(f"文件: {log_file_path}")
        print(f"总行数: {len(all_lines)}")
        print(f"显示最后 {len(last_lines)} 行")
        print(f"查看时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)
        
        for line in last_lines:
            print(line.rstrip())
            
    except Exception as e:
        print(f"读取日志文件时出错: {e}")

def main():
    """
    主函数
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='TraePy 日志查看工具')
    parser.add_argument('-f', '--file', default='logs/traepy.log', 
                       help='日志文件路径 (默认: logs/traepy.log)')
    parser.add_argument('-n', '--lines', type=int, default=50,
                       help='显示的行数 (默认: 50)')
    
    args = parser.parse_args()
    
    view_logs(args.file, args.lines)

if __name__ == '__main__':
    main()