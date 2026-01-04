"""
DeepSeek-OCR Web UI Backend
使用 Docker vLLM API 进行 OCR 识别
支持单文件和批量 PDF 处理
"""

import uuid
import asyncio
import shutil
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks, Form
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
import fitz  # PyMuPDF
import json
import zipfile
import io
from PIL import Image
from collections import Counter


# ============ 批量处理数据模型 ============

@dataclass
class BatchFile:
    """批量处理中的单个文件"""
    file_id: str
    filename: str
    original_path: str
    size: int
    status: str = "pending"  # pending, processing, completed, error
    progress: int = 0
    page_count: Optional[int] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BatchFile":
        return cls(**data)


@dataclass
class BatchTask:
    """批量处理任务"""
    batch_id: str
    created_at: str
    status: str = "idle"  # idle, processing, completed, error
    prompt: str = "<image>\nFree OCR."
    files: List[BatchFile] = field(default_factory=list)
    current_file_index: int = 0
    output_dir: str = ""
    
    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "status": self.status,
            "prompt": self.prompt,
            "files": [f.to_dict() for f in self.files],
            "current_file_index": self.current_file_index,
            "output_dir": self.output_dir
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "BatchTask":
        files = [BatchFile.from_dict(f) for f in data.get("files", [])]
        return cls(
            batch_id=data["batch_id"],
            created_at=data["created_at"],
            status=data.get("status", "idle"),
            prompt=data.get("prompt", "<image>\nFree OCR."),
            files=files,
            current_file_index=data.get("current_file_index", 0),
            output_dir=data.get("output_dir", "")
        )
    
    def calculate_overall_progress(self) -> int:
        """计算整体进度百分比"""
        if not self.files:
            return 0
        completed = sum(1 for f in self.files if f.status == "completed")
        return round((completed / len(self.files)) * 100)
    
    def get_next_pending_file(self) -> Optional[BatchFile]:
        """获取下一个待处理文件"""
        for f in self.files:
            if f.status == "pending":
                return f
        return None


# 批量任务存储
batch_tasks: dict[str, BatchTask] = {}
batch_connections: dict[str, WebSocket] = {}

app = FastAPI(title="DeepSeek OCR Web UI", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置
import os
UPLOAD_DIR = Path("uploads")
RESULTS_DIR = Path("results")
LOGS_DIR = Path("logs")
WORKSPACE_DIR = Path(os.getenv("WORKSPACE_DIR", "/workspace"))
VLLM_API_URL = os.getenv("VLLM_API_URL", "http://localhost:8000/v1/chat/completions")

# 创建目录
for dir_path in [UPLOAD_DIR, RESULTS_DIR, LOGS_DIR, WORKSPACE_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# WebSocket 连接管理
active_connections = {}


# ============ 工具函数 ============

def save_task_state(task_id: str, state: dict):
    """保存任务状态"""
    state_file = LOGS_DIR / f"task_{task_id}.json"
    state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding='utf-8')


def load_task_state(task_id: str) -> Optional[dict]:
    """加载任务状态"""
    state_file = LOGS_DIR / f"task_{task_id}.json"
    if not state_file.exists():
        return None
    return json.loads(state_file.read_text(encoding='utf-8'))


def save_batch_state(batch: BatchTask):
    """保存批量任务状态到磁盘"""
    batch_dir = RESULTS_DIR / f"batch_{batch.batch_id}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    state_file = batch_dir / "state.json"
    state_file.write_text(json.dumps(batch.to_dict(), indent=2, ensure_ascii=False), encoding='utf-8')


def load_batch_state(batch_id: str) -> Optional[BatchTask]:
    """从磁盘加载批量任务状态"""
    state_file = RESULTS_DIR / f"batch_{batch_id}" / "state.json"
    if not state_file.exists():
        return None
    data = json.loads(state_file.read_text(encoding='utf-8'))
    return BatchTask.from_dict(data)


def load_all_batch_states():
    """启动时加载所有批量任务状态"""
    global batch_tasks
    for batch_dir in RESULTS_DIR.glob("batch_*"):
        state_file = batch_dir / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding='utf-8'))
                batch = BatchTask.from_dict(data)
                batch_tasks[batch.batch_id] = batch
            except Exception as e:
                print(f"⚠️ 加载批次状态失败: {batch_dir.name}, {e}")


# 启动时加载批量任务状态
@app.on_event("startup")
async def startup_event():
    load_all_batch_states()
    print(f"✅ 已加载 {len(batch_tasks)} 个批量任务状态")


def pdf_to_images(pdf_path: Path, output_dir: Path) -> list:
    """PDF 转图片"""
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf = fitz.open(str(pdf_path))
    image_paths = []
    
    for page_num in range(pdf.page_count):
        page = pdf[page_num]
        zoom = 2.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        
        img_path = output_dir / f"page_{page_num}.png"
        pixmap.save(str(img_path))
        image_paths.append(img_path)
    
    pdf.close()
    return image_paths


def call_vllm_api(image_path: Path, prompt: str) -> dict:
    """调用 vLLM API"""
    # 复制图片到 workspace
    workspace_img = WORKSPACE_DIR / image_path.name
    shutil.copy(image_path, workspace_img)
    
    payload = {
        "model": "deepseek-ocr",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"file:///workspace/{workspace_img.name}"}},
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 4096,
        "temperature": 0
    }
    
    response = requests.post(VLLM_API_URL, json=payload, timeout=120)
    response.raise_for_status()
    result = response.json()
    
    return {
        "text": result['choices'][0]['message']['content'],
        "usage": result.get('usage', {})
    }


def extract_dominant_color(image_path: Path, sample_region: str = "top") -> str:
    """从图片中提取主色调（用于表格表头）
    
    Args:
        image_path: 图片路径
        sample_region: 采样区域 - "top" 表示顶部区域（通常是表头）
    
    Returns:
        十六进制颜色值，如 "#0d7c66"
    """
    try:
        img = Image.open(image_path)
        
        # 转换为 RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        width, height = img.size
        
        # 采样顶部 15% 区域（通常是表头位置）
        if sample_region == "top":
            crop_height = int(height * 0.15)
            crop_box = (0, 0, width, max(crop_height, 50))
        else:
            crop_box = (0, 0, width, height)
        
        cropped = img.crop(crop_box)
        
        # 缩小图片以加快处理速度
        cropped.thumbnail((100, 100))
        
        # 获取所有像素
        pixels = list(cropped.getdata())
        
        # 过滤掉接近白色和接近黑色的像素
        colored_pixels = []
        for r, g, b in pixels:
            # 跳过太亮（接近白色）或太暗（接近黑色）的像素
            brightness = (r + g + b) / 3
            if 30 < brightness < 220:
                # 跳过灰色像素（R、G、B 值接近）
                max_diff = max(abs(r-g), abs(g-b), abs(r-b))
                if max_diff > 20:  # 有一定的颜色差异
                    colored_pixels.append((r, g, b))
        
        if not colored_pixels:
            return "#0d7c66"  # 默认绿色
        
        # 量化颜色（减少颜色数量以便统计）
        def quantize(color, factor=32):
            return tuple((c // factor) * factor for c in color)
        
        quantized = [quantize(p) for p in colored_pixels]
        
        # 统计最常见的颜色
        color_counts = Counter(quantized)
        most_common = color_counts.most_common(1)[0][0]
        
        # 转换为十六进制
        hex_color = "#{:02x}{:02x}{:02x}".format(*most_common)
        
        return hex_color
        
    except Exception as e:
        print(f"⚠️ 颜色提取失败: {e}")
        return "#0d7c66"  # 默认绿色


async def update_progress(task_id: str, progress: int):
    """更新进度"""
    if task_id in active_connections:
        try:
            await active_connections[task_id].send_json({
                "task_id": task_id,
                "progress": progress
            })
        except:
            pass


# ============ API 端点 ============

@app.get("/api/health")
async def health_check():
    """健康检查"""
    try:
        response = requests.get("http://deepseek-ocr:8000/health", timeout=5)
        vllm_status = "running" if response.status_code == 200 else "error"
    except:
        vllm_status = "error"
    
    return {
        "backend": "running",
        "vllm": vllm_status
    }


@app.get("/api/model/status")
async def model_status():
    """检查模型加载状态"""
    try:
        # 检查 vLLM health (使用容器名而不是localhost)
        health_response = requests.get("http://deepseek-ocr:8000/health", timeout=5)
        if health_response.status_code != 200:
            return {
                "status": "loading",
                "ready": False,
                "message": "vLLM 服务未就绪,模型正在加载中..."
            }
        
        # 检查模型列表
        models_response = requests.get("http://deepseek-ocr:8000/v1/models", timeout=5)
        if models_response.status_code == 200:
            models_data = models_response.json()
            if models_data.get("data") and len(models_data["data"]) > 0:
                return {
                    "status": "ready",
                    "ready": True,
                    "message": "模型已加载完成",
                    "model": models_data["data"][0].get("id", "deepseek-ocr")
                }
        
        return {
            "status": "loading",
            "ready": False,
            "message": "模型正在加载中,请稍候..."
        }
    except requests.exceptions.ConnectionError:
        # 连接被拒绝通常意味着服务正在启动
        return {
            "status": "loading",
            "ready": False,
            "message": "模型正在加载中,预计需要 30-60 秒..."
        }
    except requests.exceptions.Timeout:
        # 超时也可能是服务正在启动
        return {
            "status": "loading",
            "ready": False,
            "message": "模型正在加载中,请耐心等待..."
        }
    except Exception as e:
        # 其他未知错误才显示错误信息
        error_str = str(e)
        # 如果是连接相关错误,显示友好提示
        if "Connection refused" in error_str or "Failed to establish" in error_str:
            return {
                "status": "loading",
                "ready": False,
                "message": "模型正在启动中,请稍候..."
            }
        # 真正的错误才显示详细信息
        return {
            "status": "error",
            "ready": False,
            "message": f"服务异常: {error_str}"
        }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件"""
    try:
        # 生成唯一文件名
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4().hex[:8]}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        # 保存文件
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 检测文件类型
        file_type = "pdf" if file_ext.lower() == ".pdf" else "image"
        
        return {
            "status": "success",
            "file_path": str(file_path),
            "file_type": file_type,
            "filename": file.filename
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/extract-color")
async def extract_color(payload: dict):
    """从图片中提取主色调"""
    file_path = payload.get("file_path")
    
    if not file_path:
        return {"status": "error", "message": "缺少文件路径"}
    
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "message": "文件不存在"}
    
    try:
        # 如果是 PDF，先转换第一页为图片
        if path.suffix.lower() == ".pdf":
            temp_dir = UPLOAD_DIR / "temp_color"
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            pdf = fitz.open(str(path))
            page = pdf[0]
            zoom = 1.0
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            
            temp_img = temp_dir / f"{uuid.uuid4().hex[:8]}.png"
            pixmap.save(str(temp_img))
            pdf.close()
            
            color = extract_dominant_color(temp_img)
            
            # 清理临时文件
            temp_img.unlink()
        else:
            color = extract_dominant_color(path)
        
        return {
            "status": "success",
            "color": color
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "color": "#0d7c66"}


@app.post("/api/ocr")
async def start_ocr(payload: dict, background_tasks: BackgroundTasks):
    """启动 OCR 任务"""
    file_path = payload.get("file_path")
    prompt = payload.get("prompt", "<image>\nFree OCR.")
    file_type = payload.get("file_type", "image")
    
    if not file_path or not Path(file_path).exists():
        return {"status": "error", "message": "文件不存在"}
    
    task_id = uuid.uuid4().hex[:8]
    result_dir = RESULTS_DIR / f"task_{task_id}"
    result_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存初始状态
    save_task_state(task_id, {
        "status": "running",
        "progress": 0,
        "result_dir": str(result_dir)
    })
    
    async def process_task():
        try:
            if file_type == "pdf":
                # PDF 处理
                await update_progress(task_id, 10)
                
                # 转换为图片
                images_dir = result_dir / "images"
                image_paths = pdf_to_images(Path(file_path), images_dir)
                total_pages = len(image_paths)
                
                results = []
                for idx, img_path in enumerate(image_paths):
                    progress = 20 + int((idx / total_pages) * 70)
                    await update_progress(task_id, progress)
                    
                    result = call_vllm_api(img_path, prompt)
                    results.append({
                        "page": idx + 1,
                        "text": result['text']
                    })
                
                # 合并结果
                full_text = "\n\n<--- Page Split --->\n\n".join([r['text'] for r in results])
                output_file = result_dir / "result.md"
                output_file.write_text(full_text, encoding='utf-8')
                
                save_task_state(task_id, {
                    "status": "finished",
                    "progress": 100,
                    "result_dir": str(result_dir),
                    "output_file": str(output_file),
                    "total_pages": total_pages
                })
            else:
                # 图片处理
                await update_progress(task_id, 20)
                
                result = call_vllm_api(Path(file_path), prompt)
                
                await update_progress(task_id, 80)
                
                output_file = result_dir / "result.txt"
                output_file.write_text(result['text'], encoding='utf-8')
                
                save_task_state(task_id, {
                    "status": "finished",
                    "progress": 100,
                    "result_dir": str(result_dir),
                    "output_file": str(output_file)
                })
            
            await update_progress(task_id, 100)
            
            # 发送完成消息
            if task_id in active_connections:
                await active_connections[task_id].send_json({
                    "task_id": task_id,
                    "status": "finished"
                })
        
        except Exception as e:
            save_task_state(task_id, {
                "status": "error",
                "message": str(e)
            })
            if task_id in active_connections:
                await active_connections[task_id].send_json({
                    "task_id": task_id,
                    "status": "error",
                    "message": str(e)
                })
    
    background_tasks.add_task(process_task)
    return {"status": "running", "task_id": task_id}


# ============ 批量处理 API ============

# 批量处理限制
MAX_BATCH_FILES = 20
MAX_BATCH_SIZE = 500 * 1024 * 1024  # 500MB


@app.post("/api/batch/upload")
async def batch_upload(
    files: List[UploadFile] = File(...),
    prompt: str = Form(default="<image>\nFree OCR.")
):
    """批量上传 PDF 文件"""
    try:
        # 验证文件数量
        if len(files) > MAX_BATCH_FILES:
            return {
                "status": "error",
                "message": f"文件数量超过限制，最多 {MAX_BATCH_FILES} 个文件"
            }
        
        # 验证文件格式和计算总大小
        total_size = 0
        valid_files = []
        
        for file in files:
            # 检查文件扩展名
            ext = Path(file.filename).suffix.lower()
            if ext != ".pdf":
                return {
                    "status": "error",
                    "message": f"不支持的文件格式: {file.filename}，仅支持 PDF 文件"
                }
            
            # 读取文件内容获取大小
            content = await file.read()
            await file.seek(0)  # 重置文件指针
            
            total_size += len(content)
            valid_files.append((file, content))
        
        # 验证总大小
        if total_size > MAX_BATCH_SIZE:
            return {
                "status": "error",
                "message": f"文件总大小超过限制，最大 500MB，当前 {total_size / 1024 / 1024:.1f}MB"
            }
        
        # 创建批次
        batch_id = uuid.uuid4().hex[:8]
        batch_dir = RESULTS_DIR / f"batch_{batch_id}"
        uploads_dir = batch_dir / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存文件并创建 BatchFile 对象
        batch_files = []
        for file, content in valid_files:
            file_id = uuid.uuid4().hex[:6]
            safe_filename = f"{file_id}_{file.filename}"
            file_path = uploads_dir / safe_filename
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            batch_file = BatchFile(
                file_id=file_id,
                filename=file.filename,
                original_path=str(file_path),
                size=len(content),
                status="pending",
                progress=0
            )
            batch_files.append(batch_file)
        
        # 创建 BatchTask
        batch = BatchTask(
            batch_id=batch_id,
            created_at=datetime.now().isoformat(),
            status="idle",
            prompt=prompt,
            files=batch_files,
            current_file_index=0,
            output_dir=str(batch_dir)
        )
        
        # 保存状态
        batch_tasks[batch_id] = batch
        save_batch_state(batch)
        
        return {
            "status": "success",
            "batch_id": batch_id,
            "files": [
                {"file_id": f.file_id, "filename": f.filename, "size": f.size}
                for f in batch_files
            ],
            "total_files": len(batch_files),
            "total_size": total_size
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def update_batch_progress(batch_id: str, file_id: str, file_progress: int):
    """更新批量处理进度并通过 WebSocket 推送"""
    if batch_id in batch_connections:
        batch = batch_tasks.get(batch_id)
        if batch:
            overall_progress = batch.calculate_overall_progress()
            try:
                await batch_connections[batch_id].send_json({
                    "type": "progress",
                    "batch_id": batch_id,
                    "file_id": file_id,
                    "file_progress": file_progress,
                    "overall_progress": overall_progress,
                    "status": batch.status
                })
            except:
                pass


@app.post("/api/batch/{batch_id}/start")
async def batch_start(batch_id: str, background_tasks: BackgroundTasks):
    """启动批量处理任务"""
    # 检查批次是否存在
    batch = batch_tasks.get(batch_id)
    if not batch:
        # 尝试从磁盘加载
        batch = load_batch_state(batch_id)
        if batch:
            batch_tasks[batch_id] = batch
        else:
            return {"status": "error", "message": "批次不存在"}
    
    # 检查状态
    if batch.status == "processing":
        return {"status": "error", "message": "批次正在处理中"}
    
    if batch.status == "completed":
        return {"status": "error", "message": "批次已完成"}
    
    # 更新状态为处理中
    batch.status = "processing"
    save_batch_state(batch)
    
    async def process_batch():
        """顺序处理批次中的所有文件"""
        batch_dir = Path(batch.output_dir)
        individual_dir = batch_dir / "individual"
        individual_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            for idx, batch_file in enumerate(batch.files):
                # 跳过已完成或出错的文件
                if batch_file.status in ["completed", "error"]:
                    continue
                
                # 更新当前文件索引
                batch.current_file_index = idx
                batch_file.status = "processing"
                batch_file.progress = 0
                save_batch_state(batch)
                
                await update_batch_progress(batch_id, batch_file.file_id, 0)
                
                try:
                    # 处理 PDF 文件
                    pdf_path = Path(batch_file.original_path)
                    images_dir = batch_dir / "images" / batch_file.file_id
                    images_dir.mkdir(parents=True, exist_ok=True)
                    
                    # PDF 转图片
                    batch_file.progress = 10
                    await update_batch_progress(batch_id, batch_file.file_id, 10)
                    
                    image_paths = pdf_to_images(pdf_path, images_dir)
                    batch_file.page_count = len(image_paths)
                    
                    # OCR 每一页
                    results = []
                    for page_idx, img_path in enumerate(image_paths):
                        progress = 20 + int((page_idx / len(image_paths)) * 70)
                        batch_file.progress = progress
                        await update_batch_progress(batch_id, batch_file.file_id, progress)
                        
                        result = call_vllm_api(img_path, batch.prompt)
                        results.append({
                            "page": page_idx + 1,
                            "text": result['text']
                        })
                    
                    # 合并结果
                    full_text = "\n\n<--- Page Split --->\n\n".join([r['text'] for r in results])
                    
                    # 保存单个文件结果
                    result_filename = Path(batch_file.filename).stem + ".md"
                    result_path = individual_dir / result_filename
                    result_path.write_text(full_text, encoding='utf-8')
                    
                    # 更新文件状态
                    batch_file.status = "completed"
                    batch_file.progress = 100
                    batch_file.result_path = str(result_path)
                    save_batch_state(batch)
                    
                    # 发送文件完成通知
                    if batch_id in batch_connections:
                        try:
                            await batch_connections[batch_id].send_json({
                                "type": "file_complete",
                                "batch_id": batch_id,
                                "file_id": batch_file.file_id,
                                "filename": batch_file.filename,
                                "overall_progress": batch.calculate_overall_progress()
                            })
                        except:
                            pass
                    
                except Exception as e:
                    batch_file.status = "error"
                    batch_file.error = str(e)
                    save_batch_state(batch)
                    
                    # 发送错误通知
                    if batch_id in batch_connections:
                        try:
                            await batch_connections[batch_id].send_json({
                                "type": "error",
                                "batch_id": batch_id,
                                "file_id": batch_file.file_id,
                                "error": str(e)
                            })
                        except:
                            pass
            
            # 生成合并结果
            combined_results = []
            for batch_file in batch.files:
                if batch_file.status == "completed" and batch_file.result_path:
                    result_content = Path(batch_file.result_path).read_text(encoding='utf-8')
                    combined_results.append(f"# {batch_file.filename}\n\n{result_content}")
            
            combined_path = batch_dir / "combined_result.md"
            combined_path.write_text("\n\n---\n\n".join(combined_results), encoding='utf-8')
            
            # 更新批次状态
            batch.status = "completed"
            save_batch_state(batch)
            
            # 发送批次完成通知
            if batch_id in batch_connections:
                try:
                    await batch_connections[batch_id].send_json({
                        "type": "batch_complete",
                        "batch_id": batch_id,
                        "overall_progress": 100
                    })
                except:
                    pass
        
        except Exception as e:
            batch.status = "error"
            save_batch_state(batch)
            
            if batch_id in batch_connections:
                try:
                    await batch_connections[batch_id].send_json({
                        "type": "error",
                        "batch_id": batch_id,
                        "error": str(e)
                    })
                except:
                    pass
    
    background_tasks.add_task(process_batch)
    return {"status": "running", "batch_id": batch_id}


@app.get("/api/batch/{batch_id}/status")
async def batch_status(batch_id: str):
    """获取批次状态"""
    # 检查批次是否存在
    batch = batch_tasks.get(batch_id)
    if not batch:
        # 尝试从磁盘加载
        batch = load_batch_state(batch_id)
        if batch:
            batch_tasks[batch_id] = batch
        else:
            return {"status": "error", "message": "批次不存在"}
    
    # 计算整体进度
    overall_progress = batch.calculate_overall_progress()
    
    # 构建文件状态列表
    files_status = []
    for f in batch.files:
        files_status.append({
            "file_id": f.file_id,
            "filename": f.filename,
            "size": f.size,
            "status": f.status,
            "progress": f.progress,
            "page_count": f.page_count,
            "error": f.error
        })
    
    return {
        "status": "success",
        "batch_id": batch_id,
        "batch_status": batch.status,
        "overall_progress": overall_progress,
        "total_files": len(batch.files),
        "completed_files": sum(1 for f in batch.files if f.status == "completed"),
        "error_files": sum(1 for f in batch.files if f.status == "error"),
        "files": files_status,
        "created_at": batch.created_at
    }


@app.get("/api/batch/{batch_id}/result/{file_id}")
async def batch_file_result(batch_id: str, file_id: str):
    """获取单个文件的 OCR 结果"""
    # 检查批次是否存在
    batch = batch_tasks.get(batch_id)
    if not batch:
        batch = load_batch_state(batch_id)
        if batch:
            batch_tasks[batch_id] = batch
        else:
            return {"status": "error", "message": "批次不存在"}
    
    # 查找文件
    target_file = None
    for f in batch.files:
        if f.file_id == file_id:
            target_file = f
            break
    
    if not target_file:
        return {"status": "error", "message": "文件不存在"}
    
    if target_file.status != "completed":
        return {
            "status": "error",
            "message": f"文件尚未完成处理，当前状态: {target_file.status}"
        }
    
    if not target_file.result_path or not Path(target_file.result_path).exists():
        return {"status": "error", "message": "结果文件不存在"}
    
    # 读取结果
    content = Path(target_file.result_path).read_text(encoding='utf-8')
    
    return {
        "status": "success",
        "file_id": file_id,
        "filename": target_file.filename,
        "page_count": target_file.page_count,
        "content": content
    }


@app.get("/api/batch/{batch_id}/download")
async def batch_download(batch_id: str):
    """下载批次结果 ZIP 文件"""
    # 检查批次是否存在
    batch = batch_tasks.get(batch_id)
    if not batch:
        batch = load_batch_state(batch_id)
        if batch:
            batch_tasks[batch_id] = batch
        else:
            return {"status": "error", "message": "批次不存在"}
    
    # 检查是否有已完成的文件
    completed_files = [f for f in batch.files if f.status == "completed" and f.result_path]
    if not completed_files:
        return {"status": "error", "message": "没有已完成的文件可下载"}
    
    # 创建 ZIP 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 添加单个文件结果
        for f in completed_files:
            if Path(f.result_path).exists():
                content = Path(f.result_path).read_text(encoding='utf-8')
                result_filename = Path(f.filename).stem + ".md"
                zf.writestr(f"individual/{result_filename}", content)
        
        # 添加合并结果
        combined_path = Path(batch.output_dir) / "combined_result.md"
        if combined_path.exists():
            zf.writestr("combined_result.md", combined_path.read_text(encoding='utf-8'))
    
    zip_buffer.seek(0)
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=batch_{batch_id}_results.zip"
        }
    )


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    """获取任务结果"""
    state = load_task_state(task_id)
    if not state:
        return JSONResponse(status_code=404, content={"status": "error", "message": "任务不存在"})
    
    if state["status"] == "finished":
        output_file = Path(state["output_file"])
        if output_file.exists():
            content = output_file.read_text(encoding='utf-8')
            return {
                "status": "success",
                "task_id": task_id,
                "content": content,
                "output_file": str(output_file)
            }
    
    return state


@app.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 进度推送"""
    await websocket.accept()
    active_connections[task_id] = websocket
    print(f"🌐 WebSocket 连接: {task_id}")
    
    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print(f"❌ WebSocket 断开: {task_id}")
        if task_id in active_connections:
            del active_connections[task_id]


@app.websocket("/ws/batch/{batch_id}")
async def batch_websocket_endpoint(websocket: WebSocket, batch_id: str):
    """批量处理 WebSocket 进度推送"""
    await websocket.accept()
    batch_connections[batch_id] = websocket
    print(f"🌐 批量 WebSocket 连接: {batch_id}")
    
    # 发送当前状态
    batch = batch_tasks.get(batch_id)
    if batch:
        await websocket.send_json({
            "type": "connected",
            "batch_id": batch_id,
            "status": batch.status,
            "overall_progress": batch.calculate_overall_progress()
        })
    
    try:
        while True:
            # 保持连接，等待客户端消息或断开
            data = await websocket.receive_text()
            # 可以处理客户端发送的消息，如心跳
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        print(f"❌ 批量 WebSocket 断开: {batch_id}")
        if batch_id in batch_connections:
            del batch_connections[batch_id]


@app.delete("/api/batch/{batch_id}/file/{file_id}")
async def batch_delete_file(batch_id: str, file_id: str):
    """从批次中删除待处理文件"""
    batch = batch_tasks.get(batch_id)
    if not batch:
        batch = load_batch_state(batch_id)
        if batch:
            batch_tasks[batch_id] = batch
        else:
            return {"status": "error", "message": "批次不存在"}
    
    # 查找文件
    target_idx = None
    for idx, f in enumerate(batch.files):
        if f.file_id == file_id:
            target_idx = idx
            break
    
    if target_idx is None:
        return {"status": "error", "message": "文件不存在"}
    
    target_file = batch.files[target_idx]
    
    # 只能删除待处理的文件
    if target_file.status != "pending":
        return {
            "status": "error",
            "message": f"只能删除待处理的文件，当前状态: {target_file.status}"
        }
    
    # 删除物理文件
    if target_file.original_path and Path(target_file.original_path).exists():
        Path(target_file.original_path).unlink()
    
    # 从列表中移除
    batch.files.pop(target_idx)
    save_batch_state(batch)
    
    return {
        "status": "success",
        "message": f"文件 {target_file.filename} 已删除",
        "remaining_files": len(batch.files)
    }


@app.delete("/api/batch/cleanup")
async def batch_cleanup():
    """清理 24 小时前的批次数据"""
    from datetime import timedelta
    
    cutoff_time = datetime.now() - timedelta(hours=24)
    cleaned_count = 0
    
    # 遍历所有批次目录
    for batch_dir in RESULTS_DIR.glob("batch_*"):
        state_file = batch_dir / "state.json"
        if not state_file.exists():
            continue
        
        try:
            data = json.loads(state_file.read_text(encoding='utf-8'))
            created_at = datetime.fromisoformat(data.get("created_at", ""))
            
            if created_at < cutoff_time:
                # 删除整个批次目录
                shutil.rmtree(batch_dir)
                
                # 从内存中移除
                batch_id = data.get("batch_id")
                if batch_id and batch_id in batch_tasks:
                    del batch_tasks[batch_id]
                
                cleaned_count += 1
        except Exception as e:
            print(f"⚠️ 清理批次失败: {batch_dir.name}, {e}")
    
    return {
        "status": "success",
        "cleaned_batches": cleaned_count
    }


# 静态文件服务
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")


@app.get("/")
async def serve_index():
    """提供 Web UI 首页"""
    # 优先使用 index_unified.html
    html_file = Path(__file__).parent / "static" / "index_unified.html"
    if not html_file.exists():
        html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "DeepSeek OCR Web UI Backend", "status": "running"}


@app.get("/batch")
async def serve_batch():
    """提供批量处理页面"""
    html_file = Path(__file__).parent / "static" / "batch.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "Batch page not found", "status": "error"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
