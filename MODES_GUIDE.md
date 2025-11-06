# DeepSeek-OCR 模式使用指南

## 📊 5种分辨率模式对比

| 模式 | base_size | image_size | crop_mode | 每页 Tokens | 最大页数 | 精度 | 速度 | 适用场景 |
|------|-----------|------------|-----------|-------------|----------|------|------|----------|
| **Tiny** | 512 | 512 | False | ~50 | 160+ | 低 | 最快 | 简单收据、标签 |
| **Small** | 640 | 640 | False | ~75 | 110 | 中 | 快 | 普通发票、表单 |
| **Base** | 1024 | 1024 | False | ~100 | 80 | 高 | 中 | 标准文档、合同 |
| **Large** | 1280 | 1280 | False | ~150 | 55 | 很高 | 慢 | 复杂图表、技术文档 |
| **Gundam** | 1024 | 640 | True | ~100-150 | 55-80 | 高 | 中 | 长文档、书籍 |

## 🔧 使用方法

### 方法 1: Python API 直接调用

```python
from vllm import LLM, SamplingParams
from vllm.model_executor.models.deepseek_ocr import NGramPerReqLogitsProcessor
from PIL import Image

# 创建模型实例
llm = LLM(
    model="deepseek-ai/DeepSeek-OCR",
    enable_prefix_caching=False,
    mm_processor_cache_gb=0,
    logits_processors=[NGramPerReqLogitsProcessor]
)

# 准备图片
image = Image.open("document.jpg").convert("RGB")

# 选择模式 - 通过 prompt 中的特殊标记
# 注意: vLLM 当前版本不支持直接传递 base_size 参数
# 需要在图像预处理阶段调整

prompt = "<image>\nFree OCR."

model_input = {
    "prompt": prompt,
    "multi_modal_data": {"image": image}
}

sampling_param = SamplingParams(
    temperature=0.0,
    max_tokens=8192,
    extra_args=dict(
        ngram_size=30,
        window_size=90,
        whitelist_token_ids={128821, 128822},
    ),
    skip_special_tokens=False,
)

# 生成输出
outputs = llm.generate([model_input], sampling_param)
print(outputs[0].outputs[0].text)
```

### 方法 2: 使用 Transformers (支持完整模式控制)

```python
from transformers import AutoModel, AutoTokenizer
import torch

model_name = 'deepseek-ai/DeepSeek-OCR'
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_name, 
    _attn_implementation='flash_attention_2',
    trust_remote_code=True,
    use_safetensors=True
)
model = model.eval().cuda().to(torch.bfloat16)

prompt = "<image>\n<|grounding|>Convert the document to markdown."
image_file = 'document.jpg'
output_path = './output'

# ===== 选择模式 =====

# Tiny 模式 - 最快
res = model.infer(
    tokenizer, 
    prompt=prompt, 
    image_file=image_file,
    output_path=output_path,
    base_size=512,
    image_size=512,
    crop_mode=False,
    save_results=True
)

# Small 模式 - 快速
res = model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path=output_path,
    base_size=640,
    image_size=640,
    crop_mode=False,
    save_results=True
)

# Base 模式 - 推荐 (默认)
res = model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path=output_path,
    base_size=1024,
    image_size=1024,
    crop_mode=False,
    save_results=True
)

# Large 模式 - 高质量
res = model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path=output_path,
    base_size=1280,
    image_size=1280,
    crop_mode=False,
    save_results=True
)

# Gundam 模式 - 长文档 (推荐)
res = model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path=output_path,
    base_size=1024,
    image_size=640,
    crop_mode=True,  # 启用裁剪模式
    save_results=True,
    test_compress=True  # 显示压缩统计
)
```

### 方法 3: 通过 HTTP API (当前 Docker 部署)

**注意**: 当前的 vLLM Docker 部署**不支持**直接指定模式参数。

vLLM 的 OpenAI 兼容 API 只接受标准的图像输入,模式参数需要在**客户端预处理**时指定。

#### 解决方案:

1. **客户端预处理** - 在发送到 API 前调整图像大小
2. **使用 Transformers** - 直接使用 transformers 库而不是 vLLM
3. **扩展 Web UI** - 添加模式选择功能

## 🎯 推荐配置

### 场景 1: 发票/收据处理
```python
base_size=640, image_size=640, crop_mode=False  # Small 模式
```

### 场景 2: 标准文档/合同
```python
base_size=1024, image_size=1024, crop_mode=False  # Base 模式
```

### 场景 3: 技术文档/图表
```python
base_size=1280, image_size=1280, crop_mode=False  # Large 模式
```

### 场景 4: 长文档/书籍
```python
base_size=1024, image_size=640, crop_mode=True  # Gundam 模式
```

## ⚠️ 重要提示

1. **vLLM 限制**: 当前 vLLM 部署使用默认模式,无法通过 API 动态切换
2. **性能权衡**: 更高分辨率 = 更好质量但更慢速度
3. **Token 预算**: 高分辨率模式会消耗更多 tokens,减少可处理页数
4. **推荐默认**: Gundam 模式 (base_size=1024, image_size=640, crop_mode=True)

## 🔄 如何在 Docker 部署中切换模式

目前的 Docker 部署**不支持**运行时切换模式。如需使用不同模式:

### 选项 1: 使用 Transformers 而非 vLLM
部署一个基于 transformers 的服务,支持完整的模式参数

### 选项 2: 客户端预处理
在调用 API 前,按照目标模式调整图像尺寸

### 选项 3: 扩展 vLLM (高级)
修改 vLLM 源码,添加自定义参数支持

## 📚 参考资料

- [官方 GitHub](https://github.com/deepseek-ai/DeepSeek-OCR)
- [Hugging Face 模型页](https://huggingface.co/deepseek-ai/DeepSeek-OCR)
- [vLLM 文档](https://docs.vllm.ai/projects/recipes/en/latest/DeepSeek/DeepSeek-OCR.html)
