"""Read-only checks for installed interaction plugins; never sends QQ messages."""

from pathlib import Path

import json
import sqlite3
import tomllib

import httpx


ROOT = Path(__file__).resolve().parents[3]
PLUGINS = {
    "smart_poke_plugin": "TAIY2020.smart_poke_plugin",
    "emoji_text_selector": "hsd221.emoji-text-selector",
    "steam_browser_plugin": "SengokuCola.steam-browser-plugin",
    "content_understanding_plugin": "YukiSakiko.content_understanding_plugin",
}


def main() -> None:
    token = json.loads((ROOT / "data/MaiMBot/webui.json").read_text())["access_token"]
    with httpx.Client(
        base_url="http://127.0.0.1:18001/api/webui/plugins",
        cookies={"maibot_session": token}, timeout=15, trust_env=False,
    ) as client:
        response = client.get("/installed")
        response.raise_for_status()
        installed = {item["id"]: item for item in response.json()["plugins"]}
        for folder, plugin_id in PLUGINS.items():
            assert installed[plugin_id]["load_status"] == "success", folder
            assert installed[plugin_id]["enabled"], folder
            print("PASS: loaded", plugin_id)
        assert "local.simple-search-plugin" not in installed

    config = tomllib.loads((ROOT / "plugins/smart_poke_plugin/config.toml").read_text())
    assert config["proactive"]["enabled"] and config["bystander"]["enabled"]
    assert config["proactive"]["max_pokes_per_day"] == 0
    assert config["proactive"]["per_chat_cooldown_seconds"] == 14400
    assert config["reaction"]["back_poke_max_times"] == 1
    adapter = tomllib.loads((ROOT / "plugins/MaiBot-Napcat-Adapter/config.toml").read_text())
    assert adapter["notice"]["enabled"] and adapter["notice"]["enable_poke"]
    print("PASS: active/bystander pokes enabled; no daily cap; cooldowns retained")

    with sqlite3.connect(f"file:{ROOT / 'data/MaiMBot/MaiBot.db'}?mode=ro", uri=True) as database:
        count = database.execute(
            "SELECT count(*) FROM images WHERE image_type='EMOJI' "
            "AND is_registered=1 AND is_banned=0 AND no_file_flag=0"
        ).fetchone()[0]
    assert count > 0
    print("PASS: registered emoji library:", count)


if __name__ == "__main__":
    main()
