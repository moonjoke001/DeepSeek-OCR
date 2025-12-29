# DeepSeek-OCR 项目指南

## 项目概述
基于 vLLM 的 DeepSeek-OCR 离线部署方案，支持本地 RTX 5090 和远程 H100 服务器。

## 技术栈
- **推理引擎**: vLLM (nightly build)
- **模型**: DeepSeek-OCR (deepseek-ai/DeepSeek-OCR)
- **后端**: FastAPI + Uvicorn
- **前端**: 静态 HTML (index_fixed.html)
- **容器化**: Docker + Docker Compose

## 项目结构
```
DeepSeek-OCR/
├── docker-compose.yml          # 本地 5090 配置
├── docker-compose.h100.yml     # H100 服务器配置
├── Dockerfile.vllm             # vLLM 后端镜像
├── Dockerfile.webui            # Web UI 镜像
├── models/                     # 模型文件 (约 7-8GB)
├── workspace/                  # 工作区目录
└── web-ui/
    ├── backend/main.py         # FastAPI 后端
    └── frontend/               # 前端页面
```

## 服务端口
- **vLLM API**: 8000
- **Web UI**: 8002

## Docker 命令
```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 查看日志
docker compose logs -f

# H100 服务器
docker compose -f docker-compose.h100.yml up -d
```

## API 端点
- 健康检查: `GET /api/health`
- 模型状态: `GET /api/model/status`
- 上传文件: `POST /api/upload`
- 启动 OCR: `POST /api/ocr`
- 获取结果: `GET /api/result/{task_id}`
- WebSocket: `WS /ws/{task_id}`

## OCR 模式
| 模式 | base_size | image_size | 适用场景 |
|------|-----------|------------|----------|
| Tiny | 512 | 512 | 简单收据 |
| Small | 640 | 640 | 普通发票 |
| Base | 1024 | 1024 | 标准文档 |
| Large | 1280 | 1280 | 技术文档 |
| Gundam | 1024 | 640 | 长文档 (推荐) |

## 常用提示词
- 基础 OCR: `<image>\nFree OCR.`
- 文档转 Markdown: `<image>\n<|grounding|>Convert the document to markdown.`
- 表格识别: `<image>\n<|grounding|>OCR this image.`
