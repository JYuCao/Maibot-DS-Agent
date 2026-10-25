"""通过官方本地 WebSocket 做两轮验收；测试会保留在独立本地会话，不发送 QQ。"""

from pathlib import Path

import asyncio
import json

import websockets


async def main() -> None:
    root = Path(__file__).resolve().parents[3]
    token = json.loads((root / "data/MaiMBot/webui.json").read_text())["access_token"]
    async with websockets.connect("ws://127.0.0.1:18001/api/webui/ws", proxy=None,
                                  additional_headers={"Cookie": "maibot_session=" + token}) as ws:
        await ws.send(json.dumps({"op": "call", "id": "open", "domain": "chat", "method": "session.open",
                                 "session": "local-social-verification", "data": {"user_id": "social_local_verification",
                                 "user_name": "本地功能验收", "restore": True}}, ensure_ascii=False))
        while True:
            message = json.loads(await asyncio.wait_for(ws.recv(), 20))
            if message.get("id") == "open":
                assert message.get("ok"), "Native local chat session failed to open"
                break
        for index, content in enumerate(["本地功能验收：我喜欢拼图。请只用一句简短的话回应。", "刚才说我喜欢什么？简短回答。"]):
            await ws.send(json.dumps({"op": "call", "id": "turn" + str(index), "domain": "chat", "method": "message.send",
                                     "session": "local-social-verification", "data": {"content": content}}, ensure_ascii=False))
            async with asyncio.timeout(150):
                while True:
                    message = json.loads(await ws.recv())
                    if message.get("op") == "event" and message.get("event") == "bot_message":
                        text = message["data"].get("content", "")
                        assert text.strip()
                        if index == 1:
                            assert "拼图" in text, "Second turn did not recall the synthetic preference"
                        print(json.dumps({"turn": index + 1, "reply": text}, ensure_ascii=False))
                        break
            await asyncio.sleep(1)
    print("PASS: native local two-turn chat/context; no QQ message sent.")


if __name__ == "__main__":
    asyncio.run(main())
