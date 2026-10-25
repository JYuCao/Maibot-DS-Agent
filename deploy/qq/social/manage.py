"""本地扩展管理；generate/retry 显式请求本地日记，所有命令均不发送 QQ。"""

from datetime import date
from pathlib import Path

import argparse
import json
import sqlite3
import tomllib

import httpx


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/MaiMBot-plugin-data/jycao.social-life"


def live_call(kind: str, name: str, arguments: dict) -> dict:
    # 凭据只在内存中作本机 Cookie 使用，不进入参数、环境变量、日志或报告。
    token = json.loads((ROOT / "data/MaiMBot/webui.json").read_text())["access_token"]
    with httpx.Client(base_url="http://127.0.0.1:18001", trust_env=False, timeout=15,
                      cookies={"maibot_session": token}) as client:
        response = client.post(f"/api/webui/plugins/runtime/webui/jycao.social-life/social/{kind}/{name}",
                               json={"args": arguments, "confirmed": name == "retry"})
        response.raise_for_status()
        return response.json()["result"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    diary = sub.add_parser("diary")
    diary.add_argument("--day", required=True)
    generate = sub.add_parser("generate", help="通过运行中插件生成一次本地日记，不发 QQ")
    generate.add_argument("--day", default="")
    retry = sub.add_parser("retry", help="明确同意额外模型调用后重试失败日记")
    retry.add_argument("--day", required=True)
    retry.add_argument("--confirm-model-call", action="store_true", required=True)
    relation = sub.add_parser("relation", help="查看指定真实会话、用户的关系")
    relation.add_argument("--session", required=True)
    relation.add_argument("--user", required=True)
    event = sub.add_parser("event", help="按同流消息证据登记或更正关系事件")
    for argument in ["session", "user", "event-id", "evidence-id", "reason"]:
        event.add_argument("--" + argument, required=True)
    event.add_argument("--delta", required=True, type=float)
    args = parser.parse_args()
    if args.command in {"generate", "retry", "relation", "event"}:
        if args.command == "generate":
            result = live_call("actions", "generate", {"day": args.day})
        elif args.command == "retry":
            result = live_call("actions", "retry", {"day": args.day, "allow_new_model_call": True})
        elif args.command == "relation":
            result = live_call("actions", "relationship", {"session_id": args.session, "user_id": args.user})
        else:
            result = live_call("actions", "event", {"session_id": args.session, "user_id": args.user,
                               "event_id": args.event_id, "evidence_id": args.evidence_id,
                               "reason": args.reason, "delta": args.delta})
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "status":
        path = DATA / "social.sqlite3"
        if not path.exists():
            print("插件尚未启动，没有运行状态库。")
            return
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            print(json.dumps({"metrics": [dict(row) for row in db.execute("SELECT *,elapsed/calls AS mean_seconds FROM metrics ORDER BY day DESC LIMIT 30")],
                              "jobs": [dict(row) for row in db.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT 30")]}, ensure_ascii=False, indent=2))
        return
    day = str(date.fromisoformat(args.day))
    cfg = tomllib.loads((ROOT / "plugins/social_life_plugin/config.toml").read_text())
    path = (DATA / cfg["diary"]["directory"] / (day + ".md")).resolve()
    if not path.is_relative_to(DATA.resolve()):
        raise ValueError("日记必须位于插件数据目录")
    if not path.exists():
        print("该日期没有本地日记。")
        return
    print(path.read_text())


if __name__ == "__main__":
    main()
