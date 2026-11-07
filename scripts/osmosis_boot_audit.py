#!/usr/bin/env python3
"""BLACKCYBER / BOOT forensic evidence collector (read-only).
Run: python3 scripts/osmosis_boot_audit.py
Output: research/data/osmosis-boot-audit.json
Historical LP withdrawal attribution is NOT established by current pool snapshots.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ASSET_PATH = "transfer/channel-95/boot"
BOOT_HASH = hashlib.sha256(ASSET_PATH.encode()).hexdigest().upper()
BOOT_DENOM = "ibc/" + BOOT_HASH
EXPECTED_BOOT_HASH = "FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4"
EXCLUDED_CRO_HASH = "E6931F78057F7CC5DA0FD6CEF82FF39373A6E0452BF1FD76910B93292CF356C1"
POOLS = (596, 597)
OPTIONAL_POOL = 595  # Requires independent verification of asset contents.
SQS = os.environ.get("OSMOSIS_SQS", "https://sqs.osmosis.zone")
LCD = os.environ.get("OSMOSIS_LCD", "https://lcd.osmosis.zone")
OUT = Path("research/data/osmosis-boot-audit.json")

def get_json(base, path, params=None):
    url = base.rstrip("/") + path
    if params:
        url += "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "BLACKCYBER-Forensics/0.2",
                                "Accept": "application/json"})
    with urlopen(req, timeout=20) as response:
        return json.load(response), url

def contains_exact_denom(pool, denom):
    """Search only actual token denom fields, not labels or arbitrary strings."""
    found = []
    def walk(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in ("denom", "token_denom", "coinMinimalDenom") and v == denom:
                    found.append(True)
                else:
                    walk(v)
        elif isinstance(value, list):
            for sub in value:
                walk(sub)
    walk(pool)
    return bool(found)

def main():
    if BOOT_HASH != EXPECTED_BOOT_HASH or BOOT_HASH == EXCLUDED_CRO_HASH:
        raise RuntimeError("BOOT token integrity check failed")
    out = {
      "as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
      "chain_id": "osmosis-1",
      "network": "Bostrom / Osmosis IBC",
      "asset": "BOOT",
      "ibc_path": ASSET_PATH,
      "denom": BOOT_DENOM,
      "deterministic_hash_verified": True,
      "historic_pool_ids_from_2021_sources": list(POOLS),
      "pool_595_requires_independent_check": True,
      "pool_snapshots": [],
      "errors": [],
      "sources": [],
      "historical_lp_withdrawal_transactions": [],
      "wallet_owners_attributed": [],
      "historical_lp_withdrawals_verified": False,
      "conclusion": "Pool discovery is not proof of LP withdrawal or ownership."
    }
    try:
        trace, link = get_json(LCD, "/ibc/apps/transfer/v1/denom_traces/" + BOOT_HASH)
        out["sources"].append(link)
        trace_data = trace.get("denom_trace", trace.get("denomTrace", {}))
        out["live_denom_trace"] = trace_data
        out["live_denom_trace_verified"] = (
            trace_data.get("path") == "transfer/channel-95"
            and trace_data.get("base_denom", trace_data.get("baseDenom")) == "boot"
        )
        if not out["live_denom_trace_verified"]:
            out["errors"].append("Node IBC denom trace unavailable or mismatch; do not trust pool associations")
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        out["live_denom_trace_verified"] = False
        out["errors"].append("Denom trace request failed: " + str(exc))

    # SQS returns current (not historical) pool state.
    try:
        pools, link = get_json(SQS, "/pools", {"filter[id]": "595,596,597"})
        out["sources"].append(link)
        records = pools.get("data", []) if isinstance(pools, dict) else pools
        for p in records:
            chain = p.get("chain_model", {})
            pid = p.get("id", p.get("pool_id", chain.get("id")))
            try:
                pid = int(pid)
            except (ValueError, TypeError):
                continue
            out["pool_snapshots"].append({
                "pool_id": pid,
                "contains_verified_boot_denom": contains_exact_denom(p, BOOT_DENOM),
                "current_state": p
            })
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        out["errors"].append("SQS pool request failed: " + str(exc))

    # A local indexer export can be analyzed later, but is not presented as
    # independently validated on-chain evidence.
    out["limitations"] = [
      "SQS is current state only and trade list retention is limited.",
      "Historic BOOT reserve balances need archive RPC/LCD block-height queries or a historical indexer.",
      "Only verified MsgExitPool/MsgWithdrawPosition transactions show LP removal.",
      "Pool reserve decline also occurs after swaps; reserve levels alone do not prove LP removal.",
      "A publicly visible address does not identify the person who controls it.",
      "No transaction hash, withdrawn quantity or address will be fabricated."
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("BOOT IBC hash verified:", BOOT_HASH)
    print("Pools retrieved:", len(out["pool_snapshots"]))
    print("LP exit transactions established:", len(out["historical_lp_withdrawal_transactions"]))
    print("Output:", OUT)
    for error in out["errors"]:
        print("WARNING:", error)
    if not out["live_denom_trace_verified"]:
        print("NOTE: live denom trace NOT verified; results are provisional.")

if __name__ == "__main__":
    main()
