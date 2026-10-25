"""通过核心容器的网络验证本地 Qwen；模拟内容不发送到 QQ。"""

from pathlib import Path

import argparse
import json
import sys
import time
import tomllib

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--health-only", action="store_true")
    args = parser.parse_args()
    with httpx.Client(base_url="http://qwen:8080", timeout=120, trust_env=False) as client:
        client.get("/health").raise_for_status()
        response = client.get("/v1/models")
        response.raise_for_status()
        assert any(model["id"] == "qwen3-8b-local" for model in response.json()["data"])
        print("PASS: local Qwen health and model endpoint.")
        if args.health_only:
            return
        bot = tomllib.loads(Path("/MaiMBot/config/bot_config.toml").read_text())
        persona = bot["personality"]
        system = "\n".join(persona[key] for key in ["personality", "behavior_style", "reply_style"])
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": "这是一段离线模拟。大肥鱼，你是不是又在摸鱼？简短回应一句。"},
        ]
        for prompt in [None, "我刚才叫你什么？记得按你自己的口吻说话。"]:
            if prompt is not None:
                messages.append({"role": "user", "content": prompt})
            started = time.monotonic()
            response = client.post("/v1/chat/completions", json={
                "model": "qwen3-8b-local", "messages": messages,
                "temperature": 0.8, "max_tokens": 128,
            })
            response.raise_for_status()
            data = response.json()
            message = data["choices"][0]["message"]
            content = message["content"]
            assert content and "<think>" not in content
            assert not message.get("reasoning_content"), "Thinking was not disabled"
            messages.append({"role": "assistant", "content": content})
            print("Offline reply:", content)
            print("Timing:", json.dumps({
                "wall_seconds": round(time.monotonic() - started, 2),
                "usage": data.get("usage", {}), "timings": data.get("timings", {}),
            }, ensure_ascii=False))
        print("PASS: persona generation, multi-turn request, non-thinking response; no QQ message sent.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"FAIL: {type(error).__name__}; Qwen check failed, credentials omitted.")
        sys.exit(1)
