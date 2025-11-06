# DeepSeek OCR Web UI

基于 React + FastAPI + vLLM 的 DeepSeek-OCR Web 界面

## 🚀 快速开始

### 前提条件
1. DeepSeek-OCR Docker 容器正在运行
   ```bash
   cd /home/dsj/文档/DeepSeek-OCR
   sudo docker compose up -d
   ```

2. 确认 vLLM API 可用
   ```bash
   curl http://localhost:8000/health
   ```

### 安装依赖

#### 后端
```bash
cd backend
pip install -r requirements.txt
```

#### 前端
```bash
cd frontend
npm install
```

### 启动服务

#### 方式 1: 使用启动脚本 (推荐)
```bash
./start.sh
```

#### 方式 2: 手动启动

**启动后端** (终端 1):
```bash
cd backend
python main.py
```

**启动前端** (终端 2):
```bash
cd frontend
npm start
```

### 访问应用
打开浏览器访问: http://localhost:3000

## 📖 使用说明

1. **选择识别模式**
   - 基础 OCR: 纯文本识别
   - 文档转 Markdown: 保留格式的文档识别
   - 表格识别: 专门用于表格
   - 图表解析: 解析图表和图形
   - 自定义: 输入自定义提示词

2. **上传文件**
   - 支持格式: PDF, PNG, JPG, JPEG
   - 拖拽或点击上传

3. **查看结果**
   - 实时进度显示
   - Markdown 格式渲染
   - 支持复制结果

## 🔧 配置说明

### 后端配置 (backend/main.py)
- `VLLM_API_URL`: vLLM API 地址 (默认: http://localhost:8000)
- `WORKSPACE_DIR`: Docker workspace 目录
- 端口: 8002

### 前端配置 (frontend/src/App.js)
- `API_BASE`: 后端 API 地址 (默认: http://localhost:8002)
- 端口: 3000

## 📁 项目结构
```
web-ui/
├── backend/
│   ├── main.py           # FastAPI 主程序
│   ├── requirements.txt  # Python 依赖
│   ├── uploads/          # 上传文件目录
│   ├── results/          # 结果输出目录
│   └── logs/             # 任务日志
├── frontend/
│   ├── src/
│   │   ├── App.js        # React 主组件
│   │   ├── App.css       # 样式文件
│   │   └── index.js      # 入口文件
│   ├── public/
│   │   └── index.html    # HTML 模板
│   └── package.json      # npm 依赖
├── start.sh              # 启动脚本
└── README.md             # 本文件
```

## 🐛 故障排查

### 后端无法启动
- 检查端口 8002 是否被占用
- 确认 Python 依赖已安装
- 检查 vLLM Docker 容器是否运行

### 前端无法连接后端
- 确认后端已启动 (http://localhost:8002/api/health)
- 检查 CORS 配置
- 查看浏览器控制台错误

### OCR 识别失败
- 检查 vLLM API 状态
- 查看后端日志
- 确认文件格式正确

## 📝 API 文档

### 后端 API

#### 健康检查
```
GET /api/health
```

#### 上传文件
```
POST /api/upload
Content-Type: multipart/form-data
Body: file
```

#### 启动 OCR
```
POST /api/ocr
Content-Type: application/json
Body: {
  "file_path": "string",
  "file_type": "image|pdf",
  "prompt": "string"
}
```

#### 获取结果
```
GET /api/result/{task_id}
```

#### WebSocket 进度
```
WS /ws/{task_id}
```

## 🎯 功能特性

- ✅ 支持图片和 PDF 上传
- ✅ 多种识别模式
- ✅ 实时进度显示
- ✅ WebSocket 推送
- ✅ Markdown 渲染
- ✅ 响应式设计
- ✅ 美观的 UI

## 📄 许可证

MIT License

---

**技术栈**: React 18 + Ant Design 5 + FastAPI + vLLM + Docker
