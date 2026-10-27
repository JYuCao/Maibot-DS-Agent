"""Read-only database audit and authenticated retrieval probes; never prints chat text."""

from difflib import SequenceMatcher
from pathlib import Path

import argparse
import collections
import json
import sqlite3
import time

import httpx

ROOT = Path(__file__).resolve().parents[3]


def connect(relative: str) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{ROOT / relative}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieval", action="store_true", help="Runs 3 stored-text retrieval probes; normal access reinforcement may occur")
    args = parser.parse_args()
    with connect("data/MaiMBot/a-memorix/metadata/metadata.db") as db:
        paragraphs = [dict(r) for r in db.execute("SELECT hash,content,source,metadata,is_deleted FROM paragraphs")]
        active = [p for p in paragraphs if not p["is_deleted"]]
        counts = collections.Counter(p["content"].strip() for p in active)
        result = {"active_paragraphs": len(active), "deleted_paragraphs": len(paragraphs)-len(active),
                  "active_exact_duplicate_excess": sum(v-1 for v in counts.values()),
                  "sources": dict(collections.Counter(p["source"].split(":")[0] for p in active)),
                  "episodes": db.execute("SELECT count(*) FROM episodes").fetchone()[0],
                  "profile_snapshots": db.execute("SELECT count(*) FROM person_profile_snapshots").fetchone()[0],
                  "profile_people": db.execute("SELECT count(distinct person_id) FROM person_profile_snapshots").fetchone()[0],
                  "claims": [dict(r) for r in db.execute("SELECT status,count(*) AS count FROM fact_claims GROUP BY status")],
                  "exact_relation_duplicates": db.execute("SELECT count(*) FROM (SELECT subject,predicate,object FROM relations GROUP BY subject,predicate,object HAVING count(*)>1)").fetchone()[0],
                  "summary_windows": []}
        for p in paragraphs:
            metadata = json.loads(p["metadata"] or "{}")
            if "context_length" in metadata:
                result["summary_windows"].append({k: metadata.get(k) for k in ["context_length", "pending_message_count", "trigger"]})
    with connect("data/MaiMBot/MaiBot.db") as db:
        result["messages_by_day"] = [dict(r) for r in db.execute("SELECT substr(timestamp,1,10) AS day,count(*) AS count FROM mai_messages GROUP BY 1")]
        result["cumulative_model_usage"] = [dict(r) for r in db.execute("SELECT task_name,sum(request_count) AS calls,sum(failure_count) AS failures,round(sum(success_duration)/max(1,sum(request_count)-sum(failure_count)),3) AS mean_success_seconds FROM model_task_usage GROUP BY task_name")]
    token = json.loads((ROOT / "data/MaiMBot/webui.json").read_text())["access_token"]
    with httpx.Client(base_url="http://127.0.0.1:18001/api/webui/memory", trust_env=False,
                      cookies={"maibot_session": token}, timeout=45) as client:
        response = client.get("/runtime/self-check")
        response.raise_for_status()
        check = response.json()
        result["embedding"] = {k: check.get(k) for k in ["retrieval_ready", "runtime_ready", "degraded", "vector_health"]}
        result["embedding"]["report"] = {k: check.get("report", {}).get(k) for k in ["ok", "configured_dimension", "detected_dimension", "vector_store_dimension"]}
        if args.retrieval:
            probes = []
            for i, paragraph in enumerate(active[:3]):
                # A stored-text probe isolates indexing/retrieval from semantic question quality.
                query = paragraph["content"].strip()[:80]
                started = time.monotonic()
                response = client.get("/query/aggregate", params={"query": query, "limit": 3})
                response.raise_for_status()
                payload = response.json()
                hits = payload.get("hits", [])
                probes.append({"sample": f"stored-{i+1}", "success": payload.get("success"),
                               "target_in_top3": any(h.get("hash") == paragraph["hash"] for h in hits),
                               "hit_count": len(hits), "hit_types": [h.get("type") for h in hits],
                               "near_duplicate_pairs": sum(SequenceMatcher(None, a.get("content", ""), b.get("content", "")).ratio() >= 0.8
                                                           for j, a in enumerate(hits) for b in hits[j+1:]), "seconds": round(time.monotonic()-started, 3)})
            result["stored_text_retrieval_probes"] = probes
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
