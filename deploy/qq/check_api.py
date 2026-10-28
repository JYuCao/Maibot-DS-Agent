"""在 core 容器中执行，只进行 API/向量检查，不发送 QQ 消息、不打印凭据。"""

from pathlib import Path
from openai import OpenAI

import argparse
import asyncio
import json
import sys
import tomllib

import aiohttp
import httpx


async def check_qq() -> None:
    settings = tomllib.loads(Path("/MaiMBot/plugins/MaiBot-Napcat-Adapter/config.toml").read_text())["napcat_server"]
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(
            f"ws://{settings['host']}:{settings['port']}",
            headers={"Authorization": "Bearer " + settings["token"]}, timeout=aiohttp.ClientWSTimeout(ws_receive=10),
        ) as websocket:
            await websocket.send_json({"action": "get_login_info", "params": {}, "echo": "deployment-readonly"})
            async with asyncio.timeout(15):
                async for message in websocket:
                    if message.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(message.data)
                        if data.get("echo") == "deployment-readonly":
                            assert data.get("retcode") == 0 and data.get("data", {}).get("user_id"), "QQ is not logged in"
                            print("PASS: QQ OneBot authenticated WebSocket and read-only get_login_info.")
                            return
            raise RuntimeError("No login response from QQ OneBot gateway")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deepseek", action="store_true", help="发起一次极短的付费模型请求")
    parser.add_argument("--qq", action="store_true", help="只读检查 QQ OneBot 网关登录与 WebSocket，不发送消息")
    args = parser.parse_args()
    config = tomllib.loads(Path("/MaiMBot/config/model_config.toml").read_text())
    with httpx.Client(timeout=60, trust_env=False) as client:
        response = client.post("http://embedding:8080/v1/embeddings", json={
            "model": "BAAI/bge-small-zh-v1.5", "input": ["喜欢听音乐", "周末一起打游戏"], "encoding_format": "float",
        })
        response.raise_for_status()
        vectors = response.json()["data"]
        assert len(vectors) == 2 and all(len(item["embedding"]) == 512 for item in vectors)
        assert vectors[0]["embedding"] != vectors[1]["embedding"]
        print("PASS: CPU embeddings return distinct 512-dimensional vectors.")
        with OpenAI(base_url="http://embedding:8080/v1", api_key="unused-local-service", max_retries=0) as sdk:
            vector = sdk.embeddings.create(model="BAAI/bge-small-zh-v1.5", input="SDK 协议检查").data[0].embedding
            assert len(vector) == 512
            print("PASS: OpenAI SDK default base64 embedding protocol.")
        if args.deepseek:
            provider = next(item for item in config["api_providers"] if item["name"] == "DeepSeek")
            if provider["api_key"] in {"NOT_CONFIGURED", "your-api-key", ""}:
                print("PENDING: DeepSeek key has not been configured.")
                return 2
            response = client.post(provider["base_url"].rstrip("/") + "/chat/completions",
                                   headers={"Authorization": "Bearer " + provider["api_key"]},
                                   json={"model": "deepseek-flash", "messages": [{"role": "user", "content": "只回复 OK"}],
                                         "max_tokens": 16, "thinking": {"type": "disabled"}})
            if response.status_code != 200:
                print(f"FAIL: DeepSeek HTTP {response.status_code}; response body omitted to protect credentials.")
                return 1
            payload = response.json()
            assert payload["choices"][0]["message"]["content"]
            print("PASS: DeepSeek completion; token usage: " + json.dumps(payload.get("usage", {})))
    if args.qq:
        asyncio.run(check_qq())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"FAIL: {type(error).__name__}; no request headers or credentials printed.")
        sys.exit(1)
