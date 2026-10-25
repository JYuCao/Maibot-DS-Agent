"""只向现有本地 Qwen 发合成测试；不调用 QQ、聊天存储、记忆或其他 API。"""

from pathlib import Path
from tempfile import TemporaryDirectory

import argparse
import json
import time
import tomllib

import httpx

from social_life_plugin.config import Settings
from social_life_plugin.policy import validate_diary_body
from social_life_plugin.prompts import SNAPSHOT, diary_messages
from social_life_plugin.state import StateStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    persona = tomllib.loads(Path("/MaiMBot/config/bot_config.toml").read_text())["personality"]
    system = "\n".join(persona[key] for key in ["personality", "behavior_style", "reply_style"])
    cfg = Settings()
    with TemporaryDirectory(prefix="social-offline-") as directory:
        store = StateStore(Path(directory))
        store.initialize()
        now = time.time()
        store.record_incoming(dict(sid="synthetic-group", mid="test1", uid="synthetic-user", text="哈哈", kind="group", target="synthetic"), cfg, now)
        snapshot = store.snapshot("synthetic-group", cfg, now)
        extra = SNAPSHOT["zh_CN"].format(state=json.dumps({k: snapshot[k] for k in ["serious", "valence", "life"]}, ensure_ascii=False), length=cfg.behavior.group_length)
        started = time.perf_counter()
        for index in range(100):
            store.record_incoming(dict(sid="synthetic-group", mid=str(index), uid="synthetic-user", text="谢谢", kind="group", target="synthetic"), cfg, now + index)
            store.snapshot("synthetic-group", cfg, now + index)
        print(json.dumps({"state_rule_pairs": 100, "mean_rule_pair_ms": round((time.perf_counter() - started) * 10, 3)}, ensure_ascii=False))
        prompts = [
            ("baseline_joke", "蓝鱼，你又在摸鱼吧", "", 128),
            ("extended_joke", "蓝鱼，你又在摸鱼吧", extra, 128),
            ("serious_private", "我有点难受，今天跟朋友吵架了，你能认真陪我捋一捋吗？", SNAPSHOT["zh_CN"].format(state='{"serious":true}', length=cfg.behavior.private_length), 300),
            ("quiet_day_diary", "", "", 512),
            ("serious_technical", "认真解释 WSL2 中 Docker 容器为什么能互相访问，但 localhost 不等于另一个容器。请按三个关键点说明，不要用玩笑代替。", SNAPSHOT["zh_CN"].format(state='{"serious":true}', length=cfg.behavior.private_length), 384),
        ]
        with httpx.Client(base_url="http://qwen:8080", timeout=120, trust_env=False) as client:
            for name, question, context, max_tokens in prompts:
                if args.case and name not in args.case:
                    continue
                messages = diary_messages(system, "zh_CN", "2026-10-24", {"virtual": True, "activity": "reading"}, "") if name == "quiet_day_diary" else [
                    {"role": "system", "content": system + "\n" + context}, {"role": "user", "content": question}]
                started = time.monotonic()
                response = client.post("/v1/chat/completions", json={"model": "qwen3-8b-local",
                    "messages": messages,
                    "temperature": 0.7, "max_tokens": max_tokens})
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]
                assert message["content"].strip() and not message.get("reasoning_content") and "<think>" not in message["content"]
                if name == "quiet_day_diary":
                    validate_diary_body(message["content"], has_evidence=False)
                print(json.dumps({"case": name, "seconds": round(time.monotonic() - started, 3), "chars": len(message["content"]),
                    "finish_reason": data["choices"][0]["finish_reason"], "usage": data.get("usage"), "reply": message["content"]}, ensure_ascii=False))
    print("PASS: offline local inference only; no QQ message, diary file or memory write.")


if __name__ == "__main__":
    main()
