"""下载固定版本官方 Qwen3-8B GGUF，并以官方 LFS SHA256 校验。"""

from pathlib import Path

import hashlib
import json
import subprocess

REVISION = "7c41481f57cb95916b40956ab2f0b139b296d974"
FILENAME = "Qwen3-8B-Q4_K_M.gguf"
SHA256 = "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
DIRECTORY = Path(__file__).resolve().parents[3] / "data/local-models/qwen3-8b"


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    target = DIRECTORY / FILENAME
    if target.exists():
        if checksum(target) != SHA256:
            raise SystemExit("Existing model checksum mismatch; existing file preserved.")
        print("Model already downloaded and verified.")
    else:
        temporary = DIRECTORY / (FILENAME + ".part")
        subprocess.run([
            "curl", "--fail", "--location", "--continue-at", "-", "--retry", "2",
            "--connect-timeout", "20", "--speed-limit", "1024", "--speed-time", "90",
            "--output", str(temporary),
            f"https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/{REVISION}/{FILENAME}",
        ], check=True)
        if checksum(temporary) != SHA256:
            raise SystemExit("Downloaded model checksum mismatch; partial file retained for inspection.")
        temporary.replace(target)
        print("Official model downloaded; SHA256 verified.")
    (DIRECTORY / "provenance.json").write_text(json.dumps({
        "repository": "Qwen/Qwen3-8B-GGUF", "revision": REVISION, "filename": FILENAME, "sha256": SHA256,
    }, indent=2) + "\n")
