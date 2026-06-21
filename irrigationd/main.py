import argparse

import uvicorn

from .config import load_config
from .web.app import create_app


def run() -> None:
    parser = argparse.ArgumentParser(description="Служба полива Wiren Board")
    parser.add_argument(
        "--config", default="/etc/wb-irrigation/config.yaml",
        help="путь к конфигурации",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    uvicorn.run(create_app(config), host=config.web.host, port=config.web.port)


if __name__ == "__main__":
    run()
