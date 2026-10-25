"""通过宿主机现有代理下载固定版本 CPU 模型，并校验大文件 SHA256。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict
from urllib.request import urlopen

import hashlib
import json
import shutil

REVISION = "46fbe35fd4374a00fee7de77dfddaeb6dd6a2c59"
REPOSITORY = "Qdrant/bge-small-zh-v1.5"
DESTINATION = Path(__file__).resolve().parents[3] / "data/embedding-models/bge-small-zh-v1.5"


def download(item: Dict[str, Any]) -> None:
    name = item["path"]
    target = DESTINATION / name
    expected = item.get("lfs", {}).get("oid")
    if target.exists() and (not expected or hashlib.sha256(target.read_bytes()).hexdigest() == expected):
        return
    temporary = target.with_suffix(target.suffix + ".part")
    with urlopen(f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/{name}", timeout=120) as response:
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    if expected and hashlib.sha256(temporary.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"Model checksum mismatch: {name}")
    temporary.replace(target)
    print(f"Downloaded {name}")


if __name__ == "__main__":
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with urlopen(f"https://huggingface.co/api/models/{REPOSITORY}/tree/{REVISION}", timeout=30) as response:
        files = json.load(response)
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(download, [item for item in files if item["type"] == "file" and item["path"] != ".gitattributes"]))
    print(f"CPU model ready: {REPOSITORY}@{REVISION}")
