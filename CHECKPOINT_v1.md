# DeepSeek-OCR 项目检查点 v1

**创建时间**: 2025-12-28
**Git Commit**: c1ddbb1 (main)
**用途**: 改进前的基线版本，如有问题可回退到此状态

---

## 项目结构概览

```
DeepSeek-OCR/
├── docker-compose.yml          # 本地 RTX 5090 配置
├── docker-compose.h100.yml     # H100 服务器配置
├── Dockerfile.vllm             # vLLM 推理引擎镜像
├── Dockerfile.webui            # Web UI 镜像
├── models/                     # 模型文件目录 (约 7-8GB)
├── workspace/                  # 工作区 (图片/PDF 处理)
└── web-ui/
    ├── backend/
    │   ├── main.py             # FastAPI 后端 (1142 行)
    │   ├── requirements.txt    # Python 依赖
    │   └── test_batch_properties.py
    └── frontend/
        ├── index_unified.html  # 主页面 (1902 行)
        ├── index_fixed.html    # 备用页面
        └── batch.html          # 批量处理页面
```

---

## 核心组件分析

### 1. Docker 配置

**docker-compose.yml**:
- `deepseek-ocr`: vLLM 推理服务，端口 8000
- `deepseek-web`: FastAPI Web UI，端口 8002
- 使用 `deepseek-net` 网络互联
- GPU 内存利用率设置为 90%

**Dockerfile.vllm**:
- 基于 vLLM 官方 nightly 镜像
- 安装 PyMuPDF, einops, timm 等依赖
- 入口点: `vllm serve`

**Dockerfile.webui**:
- 基于 Python 3.11-slim
- 复制 `index_unified.html` 作为主页面

### 2. 后端 API (main.py)

**数据模型**:
- `BatchFile`: 批量处理中的单个文件
- `BatchTask`: 批量处理任务

**核心功能**:
- `/api/health`: 健康检查
- `/api/model/status`: 模型加载状态
- `/api/upload`: 文件上传
- `/api/ocr`: 启动 OCR 任务
- `/api/result/{task_id}`: 获取结果
- `/ws/{task_id}`: WebSocket 进度推送

**批量处理 API**:
- `/api/batch/upload`: 批量上传 (最多 20 个文件, 500MB)
- `/api/batch/{batch_id}/start`: 启动批量处理
- `/api/batch/{batch_id}/status`: 获取状态
- `/api/batch/{batch_id}/download`: 下载 ZIP 结果

**工具函数**:
- `pdf_to_images()`: PDF 转图片
- `call_vllm_api()`: 调用 vLLM API
- `extract_dominant_color()`: 提取表头颜色

### 3. 前端 (index_unified.html)

**识别模式**:
- 基础 OCR: `<image>\nFree OCR.`
- Markdown: `<image>\n<|grounding|>Convert the document to markdown.`
- 表格识别: `<image>\n<|grounding|>OCR this image.`
- 图表解析: `<image>\nParse the figure.`
- 自定义提示词

**功能特性**:
- 拖拽上传
- 多文件批量处理
- 实时进度显示 (WebSocket)
- 表格预览和复制
- 结果下载

---

## 当前问题/待改进点

### 架构层面
1. 前端代码全部在单个 HTML 文件中 (1902 行)，难以维护
2. 没有前后端分离，静态文件直接嵌入
3. 缺少错误重试机制

### 功能层面
1. 批量处理只支持 PDF，不支持图片批量
2. 没有任务队列，大量并发可能导致 OOM
3. 缺少处理历史记录功能
4. 没有用户认证/权限控制

### 性能层面
1. PDF 转图片是同步操作，可能阻塞
2. 每次 OCR 都复制图片到 workspace，有 IO 开销
3. 没有结果缓存机制

### 用户体验
1. 模型加载状态提示不够友好
2. 错误信息不够详细
3. 缺少处理时间估算

---

## 回退方法

如果改进出现问题，可以通过以下方式回退：

```bash
# 方法 1: 回退到此 commit
git checkout c1ddbb1

# 方法 2: 重置到此 commit (丢弃后续更改)
git reset --hard c1ddbb1

# 方法 3: 创建新分支保存当前状态
git checkout -b backup-before-improvement
git checkout main
```

---

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| vLLM API | 8000 | OpenAI 兼容 API |
| Web UI | 8002 | FastAPI + 静态页面 |

---

## 依赖版本

**Python (后端)**:
- fastapi==0.115.0
- uvicorn==0.32.0
- PyMuPDF==1.24.13
- requests==2.32.3
- websockets==14.1
- hypothesis==6.100.0 (测试)

**Docker**:
- vLLM: nightly (sha256:f32c2d7673b8a6fdece522f5cc7de4755c35eb3a315d3ad39767e004f9cf70b0)
- Python: 3.11-slim
