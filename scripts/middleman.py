#!/usr/bin/env python3
"""Middleman — who stands between your quote and your fill, per pool. Live, keyless, stdlib.

    python3 scripts/middleman.py                                   # the hero rule picks the token
    python3 scripts/middleman.py --address 0x… --symbol MOTO --pages 8 --json moto.json

The engine is the `middleman/` package one directory up; this file is the door a judge walks
through. See DEMO.md for a real run with its receipt.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleman.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
