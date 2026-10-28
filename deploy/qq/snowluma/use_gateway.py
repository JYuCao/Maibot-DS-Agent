"""Switch a stopped QQ deployment between SnowLuma and preserved NapCat."""

import argparse
import json

import tomlkit

from .prepare import ADAPTER, DATA, ROOT, private_write, require_stopped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gateway", choices=["napcat", "snowluma"])
    args = parser.parse_args()
    for name in ["core", "snowluma", "napcat"]:
        require_stopped(name)
    state_path = DATA / "migration-state.json"
    state = json.loads(state_path.read_text())
    config = tomlkit.parse(ADAPTER.read_text())
    config["napcat_server"]["host"] = args.gateway
    private_write(ADAPTER, tomlkit.dumps(config))
    private_write(ROOT / "deploy/qq/gateway.local", args.gateway + "\n")
    state["active_gateway"] = args.gateway
    private_write(state_path, json.dumps(state, indent=2)+"\n")
    print("Selected " + args.gateway + "; preserved all identity, token and allowlist settings. Services remain stopped.")


if __name__ == "__main__":
    main()
