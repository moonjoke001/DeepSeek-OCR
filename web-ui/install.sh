#\!/bin/bash

echo "📦 安装 DeepSeek OCR Web UI 依赖"
echo ""

# 安装后端依赖
echo "🐍 安装 Python 后端依赖..."
cd backend
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    echo "✅ 后端依赖安装成功"
else
    echo "❌ 后端依赖安装失败"
    exit 1
fi

cd ..

# 安装前端依赖
echo ""
echo "📦 安装 Node.js 前端依赖..."
cd frontend

# 检查 npm 是否安装
if \! command -v npm &> /dev/null; then
    echo "❌ npm 未安装，请先安装 Node.js"
    echo "   sudo apt install nodejs npm"
    exit 1
fi

npm install
if [ $? -eq 0 ]; then
    echo "✅ 前端依赖安装成功"
else
    echo "❌ 前端依赖安装失败"
    exit 1
fi

cd ..

echo ""
echo "========================================="
echo "✨ 安装完成\!"
echo "========================================="
echo "运行以下命令启动服务:"
echo "  ./start.sh"
echo ""
echo "或手动启动:"
echo "  后端: cd backend && python main.py"
echo "  前端: cd frontend && npm start"
echo "========================================="
