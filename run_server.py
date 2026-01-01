#!/usr/bin/env python3
"""
启动 HTTP 服务器的入口脚本
"""

import os
import sys

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载 .env 文件（必须在导入其他模块之前）
from dotenv import load_dotenv
load_dotenv()

from src.ec2.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    print(f"启动 HTTP 服务器 - 端口: {port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
