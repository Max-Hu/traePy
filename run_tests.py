#!/usr/bin/env python3
"""
本地测试运行脚本
用于在没有Docker的情况下测试应用功能
"""

import os
import sys
import subprocess
from pathlib import Path

def setup_environment():
    """设置测试环境变量"""
    os.environ['DATABASE_URL'] = 'sqlite:///./test.db'
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-testing-only'
    os.environ['JWT_ALGORITHM'] = 'HS256'
    os.environ['JWT_ACCESS_TOKEN_EXPIRE_MINUTES'] = '30'
    
def install_minimal_deps():
    """安装最小依赖包"""
    minimal_deps = [
        'fastapi',
        'uvicorn[standard]',
        'python-jose[cryptography]',
        'passlib[bcrypt]',
        'python-multipart',
        'sqlalchemy',
        'pytest',
        'pytest-asyncio',
        'httpx'
    ]
    
    print("安装最小依赖包...")
    for dep in minimal_deps:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', dep], 
                         check=True, capture_output=True)
            print(f"✓ {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"✗ {dep} 安装失败: {e}")
            return False
    return True

def run_tests():
    """运行测试"""
    print("\n运行单元测试...")
    try:
        # 运行认证测试
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_auth.py', '-v'], 
                              capture_output=True, text=True)
        print("认证测试结果:")
        print(result.stdout)
        if result.stderr:
            print("错误信息:", result.stderr)
            
        # 运行WebSocket测试
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_websocket.py', '-v'], 
                              capture_output=True, text=True)
        print("\nWebSocket测试结果:")
        print(result.stdout)
        if result.stderr:
            print("错误信息:", result.stderr)
            
        # 运行扫描测试
        result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/test_scan.py', '-v'], 
                              capture_output=True, text=True)
        print("\n扫描测试结果:")
        print(result.stdout)
        if result.stderr:
            print("错误信息:", result.stderr)
            
    except Exception as e:
        print(f"测试运行失败: {e}")
        return False
    return True

def start_demo_server():
    """启动演示服务器"""
    print("\n启动演示服务器...")
    print("服务器将在 http://localhost:8000 启动")
    print("前端演示页面: http://localhost:8000/static/index.html")
    print("API文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务器")
    
    try:
        subprocess.run([sys.executable, '-m', 'uvicorn', 'app.main:app', 
                       '--host', '0.0.0.0', '--port', '8000', '--reload'])
    except KeyboardInterrupt:
        print("\n服务器已停止")

def main():
    """主函数"""
    print("TraePy JWT + WebSocket Demo 测试脚本")
    print("=" * 50)
    
    # 设置环境
    setup_environment()
    
    # 检查是否需要安装依赖
    choice = input("是否安装最小依赖包? (y/n): ").lower().strip()
    if choice == 'y':
        if not install_minimal_deps():
            print("依赖安装失败，退出")
            return
    
    # 运行测试
    choice = input("\n是否运行单元测试? (y/n): ").lower().strip()
    if choice == 'y':
        run_tests()
    
    # 启动服务器
    choice = input("\n是否启动演示服务器? (y/n): ").lower().strip()
    if choice == 'y':
        start_demo_server()
    
    print("\n测试完成!")

if __name__ == '__main__':
    main()