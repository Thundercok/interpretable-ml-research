"""
rat.main — Primary entry point for rat (GUI & CLI).
"""

from __future__ import annotations

import logging
import os
import sys

from rat.app.router import cli_main, route_request, run_resident_app

os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
)
logger = logging.getLogger("rat.main")


def main() -> None:
    route_request(sys.argv[1:])


if __name__ == "__main__":
    main()
