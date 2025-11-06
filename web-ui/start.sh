#\!/bin/bash

echo "🚀 启动 DeepSeek OCR Web UI"
echo ""

# 检查 vLLM API
echo "📡 检查 vLLM API 状态..."
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ vLLM API 运行正常"
else
    echo "❌ vLLM API 未运行，请先启动 Docker 容器:"
    echo "   cd /home/dsj/文档/DeepSeek-OCR && sudo docker compose up -d"
    exit 1
fi

echo ""
echo "🔧 启动后端服务..."
cd backend
python main.py &
BACKEND_PID=$\!
echo "✅ 后端已启动 (PID: $BACKEND_PID, Port: 8002)"

# 等待后端启动
sleep 3

echo ""
echo "🎨 启动前端服务..."
cd ../frontend
npm start &
FRONTEND_PID=$\!
echo "✅ 前端已启动 (PID: $FRONTEND_PID, Port: 3000)"

echo ""
echo "========================================="
echo "✨ DeepSeek OCR Web UI 已启动"
echo "========================================="
echo "前端地址: http://localhost:3000"
echo "后端地址: http://localhost:8002"
echo "========================================="
echo ""
echo "按 Ctrl+C 停止服务"

# 等待用户中断
wait
