"""Read-only SnowLuma readiness probe. No login, message, poke or space writes."""

from pathlib import Path
from uuid import uuid4

import argparse
import asyncio
import json
import subprocess
import tomllib

import aiohttp
import httpx

ROOT = Path(__file__).resolve().parents[3]


async def probe_onebot() -> None:
    adapter = tomllib.loads((ROOT / "plugins/MaiBot-Napcat-Adapter/config.toml").read_text())
    settings = adapter["napcat_server"]
    if settings["host"] != "snowluma":
        raise ValueError("The adapter is not configured for SnowLuma")
    bot = str(tomllib.loads((ROOT / "plugins/social_life_plugin/config.toml").read_text())["access"]["bot_account"])
    output = subprocess.check_output(["docker", "inspect", "maibot-qq-snowluma-1", "--format", "{{json .NetworkSettings.Networks}}"], text=True)
    networks = json.loads(output)
    address = networks["maibot-qq_default"]["IPAddress"]
    if not address:
        raise RuntimeError("SnowLuma is not running")
    actions = ["get_version_info", "get_status", "get_login_info", "get_friend_list", "get_group_list"]
    report = {}
    async with aiohttp.ClientSession(headers={"Authorization": "Bearer " + settings["token"]},
                                     timeout=aiohttp.ClientTimeout(total=30), trust_env=False) as client:
        async with client.ws_connect(f"ws://{address}:{settings['port']}/", heartbeat=20) as websocket:
            for action in actions:
                echo = uuid4().hex
                await websocket.send_json({"action": action, "params": {}, "echo": echo})
                async with asyncio.timeout(25):
                    async for message in websocket:
                        if message.type != aiohttp.WSMsgType.TEXT:
                            continue
                        result = json.loads(message.data)
                        if result.get("echo") != echo:
                            continue
                        if result.get("retcode") != 0:
                            raise RuntimeError("Read-only action failed: " + action)
                        data = result.get("data")
                        if action == "get_login_info":
                            if not isinstance(data, dict) or str(data.get("user_id")) != bot:
                                raise RuntimeError("Logged-in QQ identity does not match the configured bot")
                            report["expected_bot_identity"] = True
                        elif action == "get_status":
                            report["online"] = bool(data.get("online"))
                            if not report["online"]:
                                raise RuntimeError("QQ is not online")
                        elif action == "get_version_info":
                            report["version"] = {key: data.get(key) for key in ["app_name", "app_version", "protocol_version"]}
                        else:
                            report[action + "_count"] = len(data) if isinstance(data, list) else None
                        break
                    else:
                        raise RuntimeError("WebSocket closed before replying to " + action)
    report.update({"qq_messages_sent": 0, "poke_requests": 0, "qzone_write_requests": 0})
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onebot", action="store_true", help="After manual login, validate identity and read-only actions")
    args = parser.parse_args()
    with httpx.Client(trust_env=False, timeout=10) as client:
        for port in [5099, 6081]:
            response = client.get(f"http://127.0.0.1:{port}/")
            response.raise_for_status()
            print("PASS: local management HTTP " + str(port))
    if args.onebot:
        asyncio.run(probe_onebot())


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Upstream exceptions may embed response bodies or bearer credentials.
        print("FAIL: " + type(error).__name__ + "; sensitive response omitted. Check manual login/readiness.")
        raise SystemExit(1) from None
