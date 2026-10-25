"""按当前源码配置模型初始化 QQ 实例，不覆盖已有配置，不输出凭据。"""

from getpass import getpass
from pathlib import Path
from typing import Any, Dict

import argparse
import hashlib
import os
import secrets
import subprocess
import sys
import tempfile

import tomlkit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["MAIBOT_INITIALIZE_ONLY"] = "1"
os.umask(0o077)

from src.config.config import CONFIG_VERSION, MODEL_CONFIG_VERSION, Config, ModelConfig, write_config_to_file


def read(path: Path) -> Dict[str, Any]:
    return tomlkit.loads(path.read_text(encoding="utf-8")).unwrap()


def merge(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    """只合并模板指定字段，完整默认值由当前仓库的配置模型提供。"""
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value


def private_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同目录原子替换也能更新容器升级时以 root 身份重建的文件。
    descriptor, temporary = tempfile.mkstemp(prefix=".qq-config-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set-key", action="store_true", help="隐藏输入 DeepSeek Key")
    parser.add_argument("--accept-agreements", action="store_true", help="本人阅读并接受 EULA.md 和 PRIVACY.md 后使用")
    parser.add_argument("--apply-personality", action="store_true")
    parser.add_argument("--enable-qq", action="store_true", help="模型及 QQ 只读预检通过后启用真实交互")
    model_selection = parser.add_mutually_exclusive_group()
    model_selection.add_argument("--use-qwen", action="store_true", help="预检后仅将 Replyer 切换为本地 Qwen")
    model_selection.add_argument("--use-deepseek", action="store_true", help="将 Replyer 切回已有 DeepSeek 模型")
    args = parser.parse_args()
    config_dir = ROOT / "docker-config/mmc"
    for directory in [config_dir, ROOT / "docker-config/napcat", ROOT / "data/qq",
                      ROOT / "data/MaiMBot", ROOT / "data/MaiMBot-plugin-data", ROOT / "data/embedding-models"]:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)
    exclude = ROOT / ".git/info/exclude"
    rules = exclude.read_text() if exclude.exists() else ""
    if "/docker-config/" not in rules:
        exclude.write_text(rules + "\n# Local QQ deployment credentials\n/docker-config/\n/deploy/qq/.env\n")
    bot_path = config_dir / "bot_config.toml"
    if not bot_path.exists():
        values = Config().model_dump()
        merge(values, read(HERE / "bot.template.toml"))
        merge(values, read(HERE / "personality.toml"))
        write_config_to_file(Config.model_validate(values), bot_path, CONFIG_VERSION)
        bot_path.chmod(0o600)
        print("Created bot config; empty identity and allowlists require setup.")
    elif args.apply_personality:
        doc = tomlkit.parse(bot_path.read_text())
        for section in ["bot", "personality"]:
            for key, value in read(HERE / "personality.toml")[section].items():
                doc[section][key] = value
        private_write(bot_path, tomlkit.dumps(doc))
        print("Applied personality.")
    model_path = config_dir / "model_config.toml"
    if not model_path.exists():
        model = ModelConfig.model_validate(read(HERE / "model.template.toml"))
        write_config_to_file(model, model_path, MODEL_CONFIG_VERSION, override_repr=True)
        model_path.chmod(0o600)
        print("Created model config; DeepSeek credential is not configured.")
    adapter_path = ROOT / "plugins/MaiBot-Napcat-Adapter/config.toml"
    if not adapter_path.exists():
        adapter = read(HERE / "adapter.template.toml")
        adapter["napcat_server"]["token"] = secrets.token_urlsafe(32)
        private_write(adapter_path, tomlkit.dumps(adapter))
        print("Created adapter config with empty allowlists and a private access token.")
    if args.set_key:
        key = getpass("DeepSeek API Key (hidden): ").strip()
        if not key or any(char.isspace() for char in key):
            raise SystemExit("Invalid key; no credential was changed.")
        document = tomlkit.parse(model_path.read_text())
        for provider in document["api_providers"]:
            if provider["name"] == "DeepSeek":
                provider["api_key"] = key
                break
        private_write(model_path, tomlkit.dumps(document))
        print("Credential saved in ignored config with mode 600.")
    if args.use_qwen or args.use_deepseek:
        if args.use_qwen:
            result = subprocess.run(
                ["docker", "compose", "-f", str(HERE / "compose.yaml"), "exec", "-T", "core",
                 "/MaiMBot/.venv/bin/python", "-", "--health-only"],
                input=(HERE / "qwen/check_qwen.py").read_text(), text=True, check=False,
            )
            if result.returncode:
                raise SystemExit("Local Qwen is not ready; existing Replyer configuration preserved.")
        document = tomlkit.parse(model_path.read_text())
        if args.use_qwen:
            additions = read(HERE / "qwen/model.template.toml")
            for section in ["api_providers", "models"]:
                existing_names = {item["name"] for item in document[section]}
                for item in additions[section]:
                    if item["name"] not in existing_names:
                        document[section].append(item)
            for key, value in additions["model_task_config"]["replyer"].items():
                document["model_task_config"]["replyer"][key] = value
        else:
            if not any(item["name"] == "deepseek-flash" for item in document["models"]):
                raise SystemExit("Existing DeepSeek model not found; configuration preserved.")
            document["model_task_config"]["replyer"]["model_list"] = ["deepseek-flash"]
        values = document.unwrap()
        values.pop("inner", None)
        ModelConfig.model_validate(values)
        backup_path = model_path.with_name("model_config.before-qwen.toml")
        if not backup_path.exists():
            private_write(backup_path, model_path.read_text())
        private_write(model_path, tomlkit.dumps(document))
        print("Replyer switched to " + ("local Qwen." if args.use_qwen else "DeepSeek."))
    if args.accept_agreements:
        env_path = HERE / ".env"
        if env_path.exists():
            raise SystemExit("Existing deploy/qq/.env preserved; update agreement values there manually.")
        lines = []
        for variable, filename in [("EULA_AGREE", "EULA.md"), ("PRIVACY_AGREE", "PRIVACY.md")]:
            lines.append(f"{variable}={hashlib.md5((ROOT / filename).read_bytes()).hexdigest()}")
        private_write(env_path, "\n".join(lines) + "\n")
        print("Recorded your explicit acceptance of the current agreements.")
    if args.enable_qq:
        # 先验证 Key、模型、向量服务和登录；预检只查询 QQ 登录状态，不发送 QQ 消息。
        result = subprocess.run(
            ["docker", "compose", "-f", str(HERE / "compose.yaml"), "exec", "-T", "core",
             "/MaiMBot/.venv/bin/python", "-", "--deepseek", "--qq"],
            input=(HERE / "check_api.py").read_text(), text=True, check=False,
        )
        if result.returncode:
            raise SystemExit("Preflight did not pass; QQ adapter remains unchanged.")
        document = tomlkit.parse(adapter_path.read_text())
        if not document["chat"]["private_list"] and not document["chat"]["group_list"]:
            raise SystemExit("Both allowlists are empty; configure them before enabling QQ.")
        document["plugin"]["enabled"] = True
        private_write(adapter_path, tomlkit.dumps(document))
        print("QQ adapter enabled. Incoming allowlisted QQ messages may now receive real replies.")


if __name__ == "__main__":
    main()
