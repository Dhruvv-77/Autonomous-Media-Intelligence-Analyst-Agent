"""One-command runner for Autonomous Media Intelligence Analyst Agent.

Usage:
  python run.py          # Launches the complete interactive React Web Dashboard
  python run.py --cli    # Runs the canonical pipeline via terminal CLI
"""

import sys
import time
import threading
import webbrowser
import subprocess
from pathlib import Path


def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8000")


def main():
    if "--cli" in sys.argv:
        # Forward to canonical CLI orchestrator
        from src.main import main as cli_main
        sys.argv.remove("--cli")
        valid_cmds = {"run", "evaluate", "benchmark"}
        if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] not in valid_cmds):
            sys.argv.insert(1, "run")
            if "--config" not in sys.argv:
                sys.argv.extend(["--config", "config.yaml"])
        cli_main()
    else:
        # Check if frontend is built
        dist_dir = Path("frontend/dist")
        if not dist_dir.exists():
            print("📦 Building React web dashboard assets...")
            subprocess.run(["npm", "run", "build"], cwd="frontend", shell=True)

        print("=" * 70)
        print("🚀 Starting Autonomous Media Intelligence Analyst Web Dashboard...")
        print("👉 Opening interactive React interface at http://localhost:8000")
        print("   - Configure target company, brands & executives directly in UI")
        print("   - View Dutch/German daily briefings with exact source citations")
        print("   - Inspect verbatim evidence spans [start:end] in raw articles")
        print("   - Policy-gated CRM task governance & audit logs")
        print("   - 1,500-article SLA latency benchmark")
        print("=" * 70)

        import os
        port = int(os.environ.get("PORT", 8000))
        # Listen on 0.0.0.0 when deployed on cloud or container
        host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")

        # Automatically open browser only in local interactive sessions
        if not os.environ.get("PORT") and not os.environ.get("RENDER") and not os.environ.get("CI"):
            threading.Thread(target=open_browser, daemon=True).start()

        import uvicorn
        uvicorn.run("src.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

