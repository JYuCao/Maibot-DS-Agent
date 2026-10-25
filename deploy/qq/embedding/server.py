"""本地 CPU 中文向量服务，复用 MaiBot 已支持的 OpenAI Embedding 协议。"""

from threading import Lock
from typing import Any, Dict, List, Literal, Union

from fastapi import FastAPI, HTTPException
from fastembed import TextEmbedding
from pydantic import BaseModel, Field

import base64

MODEL = "BAAI/bge-small-zh-v1.5"
app = FastAPI()
lock = Lock()
encoder = TextEmbedding(
    model_name=MODEL, specific_model_path="/models/bge-small-zh-v1.5", cache_dir="/models",
    threads=2, providers=["CPUExecutionProvider"],
)


class EmbeddingRequest(BaseModel):
    model: Literal["BAAI/bge-small-zh-v1.5"]
    input: Union[str, List[str]]
    encoding_format: Literal["float", "base64"] = "float"
    dimensions: int = Field(default=512, ge=512, le=512)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ready", "model": MODEL, "dimension": 512, "device": "cpu"}


@app.post("/v1/embeddings")
def embeddings(request: EmbeddingRequest) -> Dict[str, Any]:
    texts = [request.input] if isinstance(request.input, str) else request.input
    if not texts or len(texts) > 32 or any(len(text) > 16000 for text in texts):
        raise HTTPException(status_code=422, detail="Expected 1-32 texts of at most 16000 characters")
    # 同步端点交给 FastAPI 线程池；锁避免多个调用同时挤占 CPU。
    with lock:
        vectors = list(encoder.embed(texts, batch_size=8))
    return {
        "object": "list",
        "model": MODEL,
        "data": [{"object": "embedding", "index": index,
                  "embedding": (base64.b64encode(vector.astype("<f4").tobytes()).decode("ascii")
                                if request.encoding_format == "base64" else vector.tolist())}
                 for index, vector in enumerate(vectors)],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
