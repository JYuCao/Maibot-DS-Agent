"""Store an optional Steam Web API key locally without displaying it."""

from getpass import getpass
from pathlib import Path
from tempfile import mkstemp
from time import time_ns

import os
import shutil

import tomlkit


def main() -> None:
    os.umask(0o077)
    root = Path(__file__).resolve().parents[3]
    path = root / "plugins/steam_browser_plugin/config.toml"
    document = tomlkit.parse(path.read_text())
    key = getpass("Steam Web API Key（隐藏输入，勿发送到聊天）: ").strip()
    if not key or any(char.isspace() for char in key):
        raise SystemExit("Key 为空或含空白，未修改配置。")
    backup = path.parent / "config_back" / f"before-key-{time_ns()}.toml"
    backup.parent.mkdir(exist_ok=True, mode=0o700)
    shutil.copy2(path, backup)
    backup.chmod(0o600)
    document["api_key"] = key
    descriptor, temporary = mkstemp(prefix=".steam-config-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(tomlkit.dumps(document))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("已保存到本机未跟踪配置（权限 600）；插件会热加载。未发起联网查询。")


if __name__ == "__main__":
    main()
