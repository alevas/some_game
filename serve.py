#!/usr/bin/env python3
"""
Noir Language Riddles: The Babel Conspiracy
Serve the full-screen version as a web page (needs: pip install textual-serve)

Run with: python serve.py                  (then open http://localhost:8000)
          python serve.py --host 0.0.0.0   (let others on your network play)
          python serve.py --port 9000
          python serve.py --public-url https://example.com   (behind a proxy or tunnel)

Every browser tab gets its own game with its own saves, which last until the tab is closed.

On Render the defaults come from its environment (RENDER, PORT, RENDER_EXTERNAL_URL),
so the start command is just: python serve.py
"""

import argparse
import os
import shlex
import sys
from pathlib import Path

from textual_serve.server import Server


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    on_render = "RENDER" in os.environ
    parser.add_argument("--host", default="0.0.0.0" if on_render else "localhost")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    # textual-serve builds the page's https/wss links from this; behind a proxy it must be the public address
    parser.add_argument("--public-url", default=os.environ.get("RENDER_EXTERNAL_URL"),
                        help="the address players use, if it differs from host:port")
    args = parser.parse_args()

    tui = Path(__file__).resolve().parent / "tui.py"
    command = f"{shlex.quote(sys.executable)} {shlex.quote(str(tui))} --web"
    Server(command, host=args.host, port=args.port, title="Noir Language Riddles",
           public_url=args.public_url).serve()


if __name__ == "__main__":
    main()
