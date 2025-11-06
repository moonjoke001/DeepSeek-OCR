# DeepSeek OCR Web UI 安装指南

## 📋 项目概述

这是一个基于 React + FastAPI + Docker vLLM 的 DeepSeek-OCR Web 界面。

**特点**:
- 🎨 现代化的 React 前端 (Ant Design)
- ⚡ 高性能 FastAPI 后端
- 🐳 使用已运行的 Docker vLLM API
- 📊 实时进度显示 (WebSocket)
- 📄 支持图片和 PDF 识别

## 🚀 快速开始

### 1. 确保 vLLM Docker 容器运行

```bash
cd /home/dsj/文档/DeepSeek-OCR
sudo docker compose up -d

# 检查状态
curl http://localhost:8000/health
```

### 2. 安装依赖

```bash
cd /home/dsj/文档/DeepSeek-OCR/web-ui
./install.sh
```

这将自动安装:
- Python 后端依赖 (FastAPI, PyMuPDF, etc.)
- Node.js 前端依赖 (React, Ant Design, etc.)

### 3. 启动服务

```bash
./start.sh
```

或手动启动:

**终端 1 - 后端**:
```bash
cd backend
python main.py
```

**终端 2 - 前端**:
```bash
cd frontend
npm start
```

### 4. 访问应用

打开浏览器访问: **http://localhost:3000**

## 📖 使用教程

### 基本流程

1. **选择识别模式**
   - 基础 OCR: 适合截图、普通图片
   - 文档转 Markdown: 适合文档、保留格式
   - 表格识别: 专门用于表格
   - 图表解析: 解析图表和图形
   - 自定义: 输入自己的提示词

2. **上传文件**
   - 点击或拖拽文件到上传区域
   - 支持: PDF, PNG, JPG, JPEG

3. **开始识别**
   - 点击"开始识别"按钮
   - 实时查看进度

4. **查看结果**
   - Markdown 模式会自动渲染
   - 可以复制结果文本

### 提示词说明

| 模式 | 提示词 | 适用场景 |
|------|--------|----------|
| 基础 OCR | `<image>\nFree OCR.` | 纯文本识别 |
| 文档转 Markdown | `<image>\n<|grounding|>Convert the document to markdown.` | 文档、保留格式 |
| 表格识别 | `<image>\n<|grounding|>OCR this image.` | 表格、结构化数据 |
| 图表解析 | `<image>\nParse the figure.` | 图表、图形 |

## 🔧 配置说明

### 后端配置

文件: `backend/main.py`

```python
# vLLM API 地址
VLLM_API_URL = "http://localhost:8000/v1/chat/completions"

# Docker workspace 目录
WORKSPACE_DIR = Path("/home/dsj/文档/DeepSeek-OCR/workspace")

# 后端端口
PORT = 8002
```

### 前端配置

文件: `frontend/src/App.js`

```javascript
// 后端 API 地址
const API_BASE = 'http://localhost:8002';
```

## 📁 项目结构

```
web-ui/
├── backend/
│   ├── main.py              # FastAPI 主程序
│   ├── requirements.txt     # Python 依赖
│   ├── uploads/             # 上传文件存储
│   ├── results/             # OCR 结果存储
│   └── logs/                # 任务状态日志
├── frontend/
│   ├── src/
│   │   ├── App.js           # React 主组件
│   │   ├── App.css          # 样式文件
│   │   └── index.js         # 入口文件
│   ├── public/
│   │   └── index.html       # HTML 模板
│   ├── package.json         # npm 配置
│   └── node_modules/        # npm 依赖 (安装后)
├── install.sh               # 依赖安装脚本
├── start.sh                 # 启动脚本
├── README.md                # 项目说明
└── SETUP_GUIDE.md           # 本文件
```

## 🐛 故障排查

### 问题 1: vLLM API 无法访问

**症状**: 后端启动失败,提示无法连接 vLLM

**解决**:
```bash
# 检查 Docker 容器状态
sudo docker ps | grep deepseek-ocr

# 如果未运行,启动容器
cd /home/dsj/文档/DeepSeek-OCR
sudo docker compose up -d

# 测试 API
curl http://localhost:8000/health
```

### 问题 2: 端口被占用

**症状**: 后端或前端启动失败,提示端口已被使用

**解决**:
```bash
# 检查端口占用
sudo lsof -i :8002  # 后端端口
sudo lsof -i :3000  # 前端端口

# 杀死占用进程
sudo kill -9 <PID>
```

### 问题 3: npm 依赖安装失败

**症状**: `npm install` 报错

**解决**:
```bash
# 清理 npm 缓存
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### 问题 4: Python 依赖安装失败

**症状**: `pip install` 报错

**解决**:
```bash
# 使用国内镜像
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 5: WebSocket 连接失败

**症状**: 进度不更新,控制台显示 WebSocket 错误

**解决**:
- 检查后端是否正常运行
- 确认防火墙没有阻止 WebSocket
- 查看浏览器控制台详细错误

## 📊 性能优化

### 后端优化

1. **调整并发数**: 修改 `main.py` 中的 worker 数量
2. **增加超时时间**: 修改 API 调用的 timeout 参数
3. **缓存结果**: 实现结果缓存机制

### 前端优化

1. **懒加载**: 大文件分批加载
2. **虚拟滚动**: 长文本使用虚拟滚动
3. **生产构建**: 使用 `npm run build` 构建优化版本

## 🔐 安全建议

1. **生产环境**: 
   - 修改 CORS 配置,限制允许的域名
   - 添加用户认证
   - 使用 HTTPS

2. **文件上传**:
   - 限制文件大小
   - 验证文件类型
   - 定期清理临时文件

3. **API 访问**:
   - 添加 API 密钥
   - 实现速率限制
   - 记录访问日志

## 📝 开发说明

### 添加新功能

1. **后端**: 在 `backend/main.py` 添加新的 API 端点
2. **前端**: 在 `frontend/src/App.js` 添加新的组件或功能

### 调试

**后端调试**:
```bash
cd backend
python main.py  # 查看控制台输出
```

**前端调试**:
- 打开浏览器开发者工具 (F12)
- 查看 Console 和 Network 标签

## 🎯 下一步计划

- [ ] 添加历史记录功能
- [ ] 支持批量处理
- [ ] 添加结果导出 (PDF, Word)
- [ ] 实现用户系统
- [ ] 添加 API 文档 (Swagger)
- [ ] Docker 化整个 Web UI

## 📞 技术支持

如有问题,请查看:
1. 本文档的故障排查部分
2. `/home/dsj/文档/DeepSeek-OCR/OCR_API_REFERENCE.md`
3. `/home/dsj/文档/DeepSeek-OCR/TEST_SUMMARY.md`

---

**版本**: 1.0.0  
**更新时间**: 2025-10-30  
**技术栈**: React 18 + Ant Design 5 + FastAPI + vLLM + Docker
