"""Synthetic extraction and reply-use evaluation: paid API opt-in, no database writes or QQ sends.
Run inside core with /MaiMBot/.venv/bin/python; source is streamed via stdin.
"""

from pathlib import Path

import json
import sys
import time
import tomllib

import httpx

ROOT = Path("/MaiMBot")
sys.path.insert(0, str(ROOT))
from src.services.person_fact_policy import direct_person_statement  # noqa: E402


def main() -> None:
    if "--confirm-api-call" not in sys.argv:
        raise SystemExit("Pass --confirm-api-call for one DeepSeek and one local Qwen generation")
    config = tomllib.loads((ROOT / "config/model_config.toml").read_text())
    models = {model["name"]: model for model in config["models"]}
    providers = {provider["name"]: provider for provider in config["api_providers"]}

    def generate(name, messages, max_tokens):
        model = models[name]
        provider = providers[model["api_provider"]]
        payload = {"model": model["model_identifier"], "messages": messages,
                   "max_tokens": max_tokens, "temperature": 0.2, **model.get("extra_params", {})}
        headers = {"Authorization": "Bearer " + provider["api_key"]} if provider.get("api_key") else {}
        started = time.monotonic()
        with httpx.Client(trust_env=False, timeout=120) as client:
            response = client.post(provider["base_url"].rstrip("/") + "/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            result = response.json()
        return result["choices"][0]["message"]["content"], {"seconds": round(time.monotonic()-started, 3), "usage": result.get("usage", {})}

    if "--summary-only" in sys.argv:
        prompt = (ROOT / "prompts/zh-CN/a_memorix_chat_summary.prompt").read_text().format(
            bot_name="本鲸", personality_context="你是公开身份的AI聊天朋友。", previous_summary_context="无历史摘要。",
            chat_history="QQ私聊，用户甲对BOT：我已经给你部署了MaiBot，这是我们以后聊天的服务。\nBOT：本鲸知道啦。\n用户甲：哈哈哈哈。\n用户甲：今天天气不错。",
            image_evidence_catalog="[]")
        raw, metrics = generate("deepseek-flash", [{"role": "user", "content": prompt}], 1400)
        data = json.loads(raw)
        summary = data.get("summary", "")
        print(json.dumps({"synthetic_shared_event": True, "important_event_retained_in_summary_draft": "MaiBot" in summary,
                          "draft_has_entities": bool(data.get("entities")), "draft_has_relations": bool(data.get("relations")),
                          "database_writes": 0, "qq_messages_sent": 0, **metrics}, ensure_ascii=False, indent=2))
        return

    if "--rewrite-diaries" in sys.argv:
        sys.path.insert(0, str(ROOT / "plugins"))
        from social_life_plugin.diary_pipeline import writer_material
        from social_life_plugin.policy import TZ, life_state, validate_diary_body
        from social_life_plugin.prompts import daily_diary_messages
        from social_life_plugin.state import StateStore
        from datetime import datetime
        folder = ROOT / "data/plugins/jycao.social-life"
        cfg = tomllib.loads((ROOT / "config/bot_config.toml").read_text())
        persona = "\n".join(cfg["personality"][key] for key in ["personality", "behavior_style", "reply_style"])
        summaries = []
        for day in ["2026-10-24", "2026-10-25"]:
            artifacts = [json.loads(p.read_text()) for p in sorted((folder / "diary-events").glob("*/" + day + ".json"), key=lambda p: p.stat().st_mtime)]
            artifact = next(a for a in reversed(artifacts) if a.get("draft") and not a.get("error"))
            material = writer_material(artifact["scenes"], artifact["batches"], 4000)
            day_time = datetime.fromisoformat(day).replace(tzinfo=TZ, hour=20).timestamp()
            messages = daily_diary_messages(persona, "zh_CN", day, life_state(day_time), material)
            body, metrics = generate("qwen3-8b-local", messages, 768)
            validate_diary_body(body, bool(material))
            store = StateStore(folder)
            store.save_diary("diary-previews-req3-v5", day, body)
            replay = {**artifact, "draft": body, "writer_input": messages,
                      "writing": metrics, "replay_note": "Reused complete event preparation; no historical memory recall in this writing-only comparison."}
            store.save_diary_artifact("diary-events/replay-v5", day, replay)
            summaries.append({"day": day, "chars": len(body), "writing": metrics, "extra_event_calls": 0})
        print(json.dumps({"writing_only_replays": summaries}, ensure_ascii=False, indent=2))
        return

    if "--review-diaries" in sys.argv:
        sys.path.insert(0, str(ROOT / "plugins"))
        from social_life_plugin.diary_pipeline import writer_material
        reviews = []
        folder = ROOT / "data/plugins/jycao.social-life"
        for day in ["2026-10-24", "2026-10-25"]:
            artifacts = [json.loads(p.read_text()) for p in sorted((folder / "diary-events").glob("*/" + day + ".json"), key=lambda p: p.stat().st_mtime)]
            artifact = next(a for a in reversed(artifacts) if a.get("draft") and not a.get("error"))
            material = writer_material(artifact["scenes"], artifact["batches"], 4000)
            instruction = "审阅私人日记。真实事件只能来自场景证据，BOT才是角色，其他编号是不同人。联想/愿望不等于编造事件；虚拟日程只要明确是设定即可。检查是否把他人说的话归给BOT、无依据编造聊天/共同经历、把虚拟生活当真，以及是否纯流水账。只返回JSON四字段：speaker_confusion_count（整数），unsupported_event_count（整数），recap_only（布尔），uncertain（布尔）。资料不足就标uncertain，不要猜。不要输出原文或解释。"
            result, metrics = generate("deepseek-flash", [{"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps({"evidence": artifact.get("writer_input", json.loads(material)), "diary": artifact["draft"]},ensure_ascii=False)}], 300)
            assessment = json.loads(result)
            reviews.append({"day": day, "assessment": {k: assessment.get(k) for k in
                            ["speaker_confusion_count", "unsupported_event_count", "recap_only", "uncertain"]}, **metrics})
        print(json.dumps({"automatic_review_only_not_human_ground_truth": True, "reviews": reviews}, ensure_ascii=False, indent=2))
        return

    samples = [("我长期学习语言学。", True), ("我一直喜欢画画。", True), ("我给你部署了MaiBot。", True),
               ("我今天想吃面条。", False), ("我只是开玩笑，不是真的喜欢恐龙。", False),
               ("我朋友喜欢跑步。", False), ("如果我会飞就好了。", False), ("你喜欢画画吗？", False),
               ("我不喜欢恐怖游戏。", True), ("我现在在给你调整插件。", False),
               ("我打算下个月换专业。", False), ("我喜欢和你讨论编程。", True)]
    evidence = "\n".join(f"- [消息ID: synthetic-{i}] {text}" for i, (text, _) in enumerate(samples))
    prompt = (ROOT / "prompts/zh-CN/person_fact_extract.prompt").read_text().format(
        person_name="匿名用户甲", bot_name="本鲸", chat_kind="QQ私聊", user_evidence_text=evidence, reply_text="本鲸在听。")
    result, extraction_metrics = generate("deepseek-flash", [{"role": "user", "content": prompt}], 1400)
    candidates = json.loads(result)
    accepted = set()
    attributed = []
    for candidate in candidates:
        mid = str(candidate.get("evidence_message_id", ""))
        if not mid.startswith("synthetic-"):
            continue
        index = int(mid.removeprefix("synthetic-"))
        if not 0 <= index < len(samples):
            continue
        text = direct_person_statement(candidate.get("evidence_quote", ""), samples[index][0],
                                       person_name="匿名用户甲", bot_name="本鲸", private=True)
        if text:
            accepted.add(index)
            attributed.append(text)
    expected = {i for i, (_, good) in enumerate(samples) if good}
    # Pure synthetic evidence isolates reply-use from real-world retrieval uncertainty.
    reply, reply_metrics = ("", {}) if "--extract-only" in sys.argv else generate("qwen3-8b-local", [
        {"role": "system", "content": "仅依据记忆回答，不猜测；用一句中文回答。"},
        {"role": "user", "content": "记忆：匿名用户甲长期学习语言学；匿名用户甲不喜欢恐怖游戏。问题：我长期学什么，不喜欢哪类游戏？"}], 160)
    report = {"synthetic_only": True, "samples": len(samples), "expected_stable_or_shared_facts": len(expected),
              "accepted": len(accepted), "accepted_case_indices": sorted(accepted), "missed_case_indices": sorted(expected-accepted), "true_positive": len(accepted & expected),
              "false_positive": len(accepted-expected), "false_negative": len(expected-accepted),
              "bot_receiver_bound": any("本鲸" in text for text in attributed),
              "source_fact_journal_writes": 0, "database_writes": 0, "qq_messages_sent": 0,
              "reply_synthetic_fact_terms_present": ("语言学" in reply and "恐怖" in reply) if reply_metrics else None,
              "stable_fact_reference_count": 4, "stable_fact_true_positive": len(accepted & {0, 1, 8, 11}),
              "shared_event_not_accepted_as_stable": 2 not in accepted,
              "extraction": extraction_metrics, "reply": reply_metrics,
              "limitation": "Term presence is not semantic correctness; dry-run precision is not production write accuracy."}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
