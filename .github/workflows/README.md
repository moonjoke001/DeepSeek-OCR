# GitHub Actions Workflows

## Docker Publish Workflow

自动构建并发布 Docker 镜像到 GitHub Container Registry (ghcr.io)。

### 触发条件

- **Push to main**: 推送到 main 分支时自动构建
- **Tags**: 创建版本标签 (v*) 时构建
- **Pull Request**: PR 时构建但不推送
- **Manual**: 手动触发

### 构建的镜像

1. **Backend (后端服务)**
   - 镜像名: `ghcr.io/moonjoke001/deepseek-ocr-backend`
   - 基于: `Dockerfile.vllm`
   - 包含: vLLM + DeepSeek-OCR 依赖

2. **WebUI (前端服务)**
   - 镜像名: `ghcr.io/moonjoke001/deepseek-ocr-webui`
   - 基于: `Dockerfile.webui`
   - 包含: FastAPI + Web 前端

### 镜像标签策略

- `latest` - 最新的 main 分支构建
- `main` - main 分支构建
- `v1.0.0` - 版本标签
- `v1.0` - 主次版本
- `v1` - 主版本
- `main-sha-abc123` - 带 commit SHA 的标签

### 使用方法

#### 1. 拉取镜像

```bash
# 后端镜像
docker pull ghcr.io/moonjoke001/deepseek-ocr-backend:latest

# 前端镜像
docker pull ghcr.io/moonjoke001/deepseek-ocr-webui:latest
```

#### 2. 更新 docker-compose.yml

```yaml
services:
  deepseek-ocr:
    image: ghcr.io/moonjoke001/deepseek-ocr-backend:latest
    # ... 其他配置

  deepseek-web:
    image: ghcr.io/moonjoke001/deepseek-ocr-webui:latest
    # ... 其他配置
```

#### 3. 启动服务

```bash
docker compose up -d
```

### 发布新版本

创建版本标签并推送:

```bash
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 会自动构建并发布带版本号的镜像。

### 查看构建状态

访问: https://github.com/moonjoke001/DeepSeek-OCR/actions

### 权限说明

- Workflow 使用 `GITHUB_TOKEN` 自动认证
- 无需额外配置 secrets
- 镜像自动发布到 GitHub Container Registry
