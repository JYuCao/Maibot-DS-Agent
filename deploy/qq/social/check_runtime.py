"""检查已加载的社交插件、权限和日记去重；不调用模型或发送 QQ。"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import hashlib
import argparse
import json
import sqlite3
import subprocess
import tomllib

import httpx


ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:18001/api/webui/plugins"
PLUGIN = "/runtime/webui/jycao.social-life/social"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-qq-stopped", action="store_true", help="额外要求 QQ 客户端停止，用于离线验收")
    args = parser.parse_args()
    marker = ROOT / "deploy/qq/gateway.local"
    gateway = marker.read_text().strip() if marker.exists() else "snowluma"
    if gateway not in {"napcat", "snowluma"}:
        raise ValueError("Invalid QQ gateway selection")
    state = subprocess.run(["docker", "inspect", "maibot-qq-" + gateway + "-1", "--format", "{{.State.Status}}"],
                           capture_output=True, text=True, check=True)
    if args.require_qq_stopped:
        assert state.stdout.strip() == "exited", "此验收要求当前 QQ 网关保持停止"
    token = json.loads((ROOT / "data/MaiMBot/webui.json").read_text())["access_token"]
    with httpx.Client(base_url=BASE, trust_env=False, timeout=15) as client:
        result = client.post(PLUGIN + "/queries/status", json={"args": {}})
        assert result.status_code == 401, "私有管理接口未拒绝匿名访问"
        client.cookies.set("maibot_session", token)
        extensions = client.get("/runtime/webui")
        extensions.raise_for_status()
        assert any(item["plugin_id"] == "jycao.social-life" for item in extensions.json()["extensions"])

        def invoke(kind: str, name: str, args: dict) -> dict:
            response = client.post(PLUGIN + f"/{kind}/{name}", json={"args": args})
            response.raise_for_status()
            return response.json()["result"]

        before = invoke("queries", "status", {})
        config = tomllib.loads((ROOT / "plugins/social_life_plugin/config.toml").read_text())
        assert before["proactive_authorized"] == config["proactive"]["real_sending_authorized"]
        assert before["diary_delivery_authorized"] == config["diary"]["private_delivery_authorized"]
        if args.require_qq_stopped:
            assert not before["proactive_authorized"] and not before["diary_delivery_authorized"]
        day = str(datetime.now(ZoneInfo("Asia/Shanghai")).date())
        diary = invoke("queries", "diary", {"day": day})
        if diary["exists"]:
            assert not invoke("actions", "generate", {"day": day})["queued"]
            after = invoke("queries", "status", {})
            assert after["metrics"] == before["metrics"], "已有日记查询引发了额外模型调用"
            print(json.dumps({"diary_day": day, "chars": len(diary["text"]),
                              "sha256": hashlib.sha256(diary["text"].encode()).hexdigest()}, ensure_ascii=False))
        assert config["plugin"]["enabled"] and config["plugin"]["config_version"] == "0.9.0"
        db_path = ROOT / "data/MaiMBot-plugin-data/jycao.social-life/social.sqlite3"
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
            assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    print("PASS: native plugin registration/RPC, authentication, local diary idempotency, SQLite integrity; " + gateway + "=" + state.stdout.strip() + ".")


if __name__ == "__main__":
    main()
