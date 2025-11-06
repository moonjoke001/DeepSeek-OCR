"""
DeepSeek-OCR Web UI Backend
使用 Docker vLLM API 进行 OCR 识别
"""

import uuid
import asyncio
import shutil
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
import fitz  # PyMuPDF
import json

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


@app.get("/api/result/{task_id}")
async def get_result(task_id: str):
    """获取任务结果"""
    state = load_task_state(task_id)
    if not state:
        return {"status": "error", "message": "任务不存在"}
    
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


# 静态文件服务
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")


@app.get("/")
async def serve_index():
    """提供 Web UI 首页"""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    return {"message": "DeepSeek OCR Web UI Backend", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
