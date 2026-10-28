"""Prepare a backed-up SnowLuma configuration without logging in or sending messages."""

from pathlib import Path

import json
import os
import subprocess
import tempfile
import tomllib

import tomlkit

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/snowluma"
ADAPTER = ROOT / "plugins/MaiBot-Napcat-Adapter/config.toml"


def private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".migration-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def require_stopped(service: str) -> None:
    result = subprocess.run(["docker", "inspect", "maibot-qq-" + service + "-1", "--format", "{{.State.Running}}"],
                            text=True, capture_output=True)
    if result.returncode == 0 and result.stdout.strip() == "true":
        raise RuntimeError("Stop " + service + " before changing the QQ gateway")


def main() -> None:
    for service in ["core", "napcat", "snowluma"]:
        require_stopped(service)
    state_path = DATA / "migration-state.json"
    state = json.loads(state_path.read_text())
    backup = ROOT / state["backup"] / "plugins/MaiBot-Napcat-Adapter/config.toml"
    if not backup.is_file():
        raise RuntimeError("A verified adapter backup is required")
    adapter = tomlkit.parse(ADAPTER.read_text())
    token = adapter["napcat_server"]["token"]
    if not isinstance(token, str) or len(token) < 16:
        raise ValueError("The existing adapter needs a nonempty private token")
    bot = tomllib.loads((ROOT / "plugins/social_life_plugin/config.toml").read_text())["access"]["bot_account"]
    if not str(bot).isdigit():
        raise ValueError("Missing configured QQ bot identity")
    template = json.loads((Path(__file__).parent / "onebot.template.json").read_text())
    template["networks"]["wsServers"][0]["accessToken"] = token
    for directory in [DATA, DATA / "app", DATA / "app/config", DATA / "qq-config", DATA / "qq-share"]:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
    for filename in ["onebot.json", "onebot_" + str(bot) + ".json"]:
        path = DATA / "app/config" / filename
        if path.exists() and json.loads(path.read_text()) != template:
            raise RuntimeError("Existing SnowLuma config differs; refusing to overwrite it")
        if not path.exists():
            private_write(path, json.dumps(template, ensure_ascii=False, indent=2) + "\n")
    runtime = DATA / "app/config/runtime.json"
    if not runtime.exists():
        private_write(runtime, json.dumps({"webuiHost": "0.0.0.0", "webuiPort": 5099, "hookAutoLoad": True}, indent=2)+"\n")
    before = tomllib.loads(ADAPTER.read_text())
    adapter["napcat_server"]["host"] = "snowluma"
    private_write(ADAPTER, tomlkit.dumps(adapter))
    after = tomllib.loads(ADAPTER.read_text())
    after["napcat_server"]["host"] = before["napcat_server"]["host"]
    assert after == before, "Only the connection host may change"
    private_write(ROOT / "deploy/qq/gateway.local", "snowluma\n")
    state.update({"stage": "configured-awaiting-login", "active_gateway": "snowluma"})
    private_write(state_path, json.dumps(state, indent=2)+"\n")
    print("Prepared SnowLuma; changed adapter host only, preserving token, allowlists, account and scope.")
    print("QQ login data is separate. No consent was recorded and no QQ login or message send was performed.")


if __name__ == "__main__":
    main()
