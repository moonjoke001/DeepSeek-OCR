# DeepSeek-OCR Docker 部署指南

基于 vLLM 官方 nightly 镜像的 DeepSeek-OCR 离线部署方案，支持本地 RTX 5090 和远程 H100 服务器。

## 📋 项目结构

```
DeepSeek-OCR/
├── docker-compose.yml          # 本地 5090 生产环境配置
├── docker-compose.h100.yml     # H100 服务器生产环境配置
├── Dockerfile.vllm             # 后端服务 Dockerfile (基于 vLLM nightly)
├── Dockerfile.webui            # 前端服务 Dockerfile
├── models/                     # 模型文件目录
├── workspace/                  # 工作区目录
└── web-ui/                     # Web UI 源码
    ├── backend/                # 后端 API
    └── frontend/               # 前端页面
```

## 🚀 快速开始

### 本地部署 (RTX 5090)

```bash
# 1. 构建镜像
docker build -t deepseek-ocr:h100 -f Dockerfile.vllm .
docker build -t deepseek-ocr-deepseek-web:latest -f Dockerfile.webui .

# 2. 启动服务
docker compose up -d

# 3. 查看日志
docker compose logs -f

# 4. 访问服务
# 后端 API: http://localhost:8000
# 前端 Web UI: http://localhost:8002
```

### H100 服务器部署

```bash
# 使用 H100 专用配置
docker compose -f docker-compose.h100.yml up -d
docker compose -f docker-compose.h100.yml logs -f
```

## 📦 离线部署流程

### 1. 本地准备 (RTX 5090)

```bash
# 导出 Docker 镜像
docker save deepseek-ocr:h100 -o deepseek-ocr-h100.tar
docker save deepseek-ocr-deepseek-web:latest -o deepseek-web.tar

# 准备部署文件
# - deepseek-ocr-h100.tar (~17GB)
# - deepseek-web.tar (~200MB)
# - docker-compose.h100.yml
# - models/ 目录 (如果 H100 服务器没有模型文件)
```

### 2. H100 服务器部署

```bash
# 加载镜像
docker load -i deepseek-ocr-h100.tar
docker load -i deepseek-web.tar

# 验证镜像
docker images | grep deepseek

# 启动服务
docker compose -f docker-compose.h100.yml up -d

# 查看日志
docker compose -f docker-compose.h100.yml logs -f deepseek-ocr
```

## ⚙️ 配置说明

### 本地配置 (docker-compose.yml)

- **GPU**: 第 0 块 GPU
- **GPU 利用率**: 90%
- **后端端口**: 8000
- **前端端口**: 8002
- **模型路径**: `./models` (只读挂载)
- **工作区**: `./workspace`

### H100 配置 (docker-compose.h100.yml)

- **GPU**: 第 3 块 GPU
- **GPU 利用率**: 95%
- **其他配置**: 与本地配置相同

## 🔧 技术栈

### 后端服务
- **基础镜像**: vLLM nightly (sha256:f32c2d7673b8a6fdece522f5cc7de4755c35eb3a315d3ad39767e004f9cf70b0)
- **推理引擎**: vLLM v0.11.1rc6+
- **模型**: DeepSeek-OCR
- **额外依赖**: PyMuPDF, img2pdf, einops, matplotlib, timm

### 前端服务
- **基础镜像**: python:3.11-slim
- **框架**: FastAPI + Uvicorn
- **依赖**: python-multipart, PyMuPDF, requests, websockets

## 📝 关键参数说明

### vLLM 启动参数

```yaml
command:
  - /workspace/models                    # 模型路径
  - --served-model-name                  # 模型服务名称
  - deepseek-ocr
  - --logits_processors                  # 自定义 logits 处理器
  - vllm.model_executor.models.deepseek_ocr:NGramPerReqLogitsProcessor
  - --no-enable-prefix-caching           # 禁用前缀缓存
  - --mm-processor-cache-gb              # 多模态处理器缓存
  - "0"
  - --gpu-memory-utilization             # GPU 显存利用率
  - "0.9"                                # 本地 90%, H100 95%
  - --allowed-local-media-path           # 允许访问的本地媒体路径
  - /workspace
  - --trust-remote-code                  # 信任远程代码
```

## 🔍 常见问题

### 1. 模型加载时间
- 首次启动需要 30-60 秒加载模型
- 可通过健康检查确认服务就绪: `curl http://localhost:8000/health`

### 2. GPU 显存不足
- 调整 `--gpu-memory-utilization` 参数 (默认 0.9)
- 确保 GPU 显存至少 16GB

### 3. 前端连接失败
- 确认后端服务已启动: `docker compose ps`
- 检查后端日志: `docker compose logs deepseek-ocr`
- 验证模型名称: `curl http://localhost:8000/v1/models`

### 4. 容器重启循环
- 查看详细日志: `docker logs <container_name>`
- 检查 GPU 是否可用: `nvidia-smi`
- 确认模型文件完整性

## 📊 性能参考

### RTX 5090 Laptop GPU
- **显存**: 16GB
- **KV Cache**: 236,704 tokens
- **并发能力**: 28.89x (8192 tokens/request)
- **模型加载**: ~7 秒
- **初始化时间**: ~35 秒

### H100
- **显存**: 80GB
- **推荐 GPU 利用率**: 95%
- **适合生产环境高并发场景**

## 🛠️ 服务管理

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f deepseek-ocr
docker compose logs -f deepseek-web
```

## 📚 API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔗 相关链接

- [DeepSeek-OCR 官方仓库](https://github.com/deepseek-ai/DeepSeek-OCR)
- [vLLM 官方文档](https://docs.vllm.ai/)
- [vLLM Docker Hub](https://hub.docker.com/r/vllm/vllm-openai)

## 📄 许可证

本项目遵循 MIT 许可证。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request!

---

**注意**: 本部署方案基于 vLLM nightly 构建，适用于离线环境。确保在部署前完成所有镜像和模型文件的准备工作。
