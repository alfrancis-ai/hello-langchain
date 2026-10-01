"""Pull a Portkey log export via the Admin API and land it as JSONL.

Flow: create -> start -> poll -> download signed URL -> write file -> quick cost rollup.
Needs in .env:
  PORTKEY_ADMIN_API_KEY   admin key with logs export/list/view scopes
  PORTKEY_WORKSPACE_ID    workspace to export from
Run:  python export_logs.py 1      (last 1 day)
"""

import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from portkey_ai import Portkey

load_dotenv(Path(__file__).with_name(".env"))

FIELDS = [
    "id", "trace_id", "created_at", "is_success", "ai_org", "ai_model",
    "req_units", "res_units", "total_units", "cost", "cost_currency",
    "response_time", "response_status_code", "metadata",
]  # request/response bodies left out on purpose: big, and not needed for FinOps


def _get(obj, key):
    """SDK responses can come back as objects or dicts."""
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def main(days: int) -> None:
    client = Portkey(api_key=os.environ["PORTKEY_ADMIN_API_KEY"])
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    export = client.logs.exports.create(
        workspace_id=os.environ["PORTKEY_WORKSPACE_ID"],
        description=f"home-lab export {start:%Y-%m-%d} to {end:%Y-%m-%d}",
        filters={
            "time_of_generation_min": start.isoformat(),
            "time_of_generation_max": end.isoformat(),
        },
        requested_data=FIELDS,
    )
    export_id = _get(export, "id")
    print(f"Created export {export_id} ({_get(export, 'total')} rows expected)")

    client.logs.exports.start(export_id=export_id)

    for _ in range(60):  # up to ~5 min
        status = str(_get(client.logs.exports.retrieve(export_id=export_id), "status")).lower()
        print(f"  status: {status}")
        if status in ("success", "completed"):
            break
        if status in ("failed", "cancelled"):
            raise SystemExit(f"Export {status}")
        time.sleep(5)
    else:
        raise SystemExit("Timed out waiting for export")

    signed_url = _get(client.logs.exports.download(export_id=export_id), "signed_url")
    body = requests.get(signed_url, timeout=120)
    body.raise_for_status()

    # Mirror the S3 layout you'll use later: raw zone, partitioned by date.
    out_dir = Path("landing/raw/portkey_logs") / f"dt={end:%Y-%m-%d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{export_id}.jsonl"
    out_file.write_bytes(body.content)
    print(f"Landed {out_file}")

    # Quick FinOps sanity check: cost and tokens by app.
    cost, tokens = defaultdict(float), defaultdict(int)
    for line in out_file.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            meta = json.loads(meta or "{}")
        app = meta.get("app_name", "(untagged)")
        cost[app] += float(row.get("cost") or 0)
        tokens[app] += int(row.get("total_units") or 0)

    print("\napp_name                      tokens      cost")
    for app in sorted(cost, key=cost.get, reverse=True):
        print(f"{app:<28} {tokens[app]:>8}  {cost[app]:>8.4f}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)