#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
Serve the full-screen version as a web page (needs: pip install textual-serve)

Run with: python serve.py                  (then open http://localhost:8000)
          python serve.py --host 0.0.0.0   (let others on your network play)
          python serve.py --port 9000
          python serve.py --public-url https://example.com   (behind a proxy or tunnel)

Every browser tab gets its own game. Save files live on the machine running this server.
"""

import argparse
import shlex
import sys
from pathlib import Path

from textual_serve.server import Server


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--public-url", default=None, help="the address players use, if it differs from host:port")
    args = parser.parse_args()

    tui = Path(__file__).resolve().parent / "tui.py"
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(tui))}"
    Server(command, host=args.host, port=args.port, title="Noir Language Riddles",
           public_url=args.public_url).serve()


if __name__ == "__main__":
    main()
