#!/usr/bin/env python3
"""Read-only historical LP-exit search for Osmosis BOOT pools 596/597.

Uses archive RPC tx_search (indexed on-chain events), not SQS recent trade data.
Usage: python3 scripts/osmosis_boot_exits.py
Output: research/data/boot-lp-exits.json

Coverage is PARTIAL unless every query completes. Event indexing may omit
older events; zero results MUST NOT be interpreted as proof of no withdrawals.
No identity attribution is performed.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

RPC = os.environ.get("OSMOSIS_ARCHIVE_RPC", "https://rpc.archive.osmosis.zone")
POOLS = (596, 597)
PAGE_LIMIT = 30
PER_PAGE = 100
OUTPUT = Path("research/data/boot-lp-exits.json")
BOOT_PATH = "transfer/channel-95/boot"
BOOT_HASH = hashlib.sha256(BOOT_PATH.encode()).hexdigest().upper()
EXPECTED = "FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4"

def query_rpc(path, params):
    url = RPC.rstrip("/") + path + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": "BLACKCYBER-Forensics/0.2", "Accept": "application/json"})
    with urlopen(req, timeout=35) as resp:
        payload = json.load(resp)
    if "error" in payload:
        raise ValueError(str(payload["error"]))
    if "result" not in payload:
        raise ValueError("RPC result missing")
    return payload["result"], url

def main():
    if BOOT_HASH != EXPECTED:
        raise RuntimeError("Wrong BOOT denom; archive analysis aborted")
    result = {
      "date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "chain": "osmosis-1", "asset_denom": "ibc/"+BOOT_HASH,
      "pool_ids": list(POOLS), "rpc": RPC,
      "queries": [], "candidate_exits": [], "errors": [],
      "complete_coverage": False, "identity_attribution": "not established",
      "claim_liquidity_removed_by_team": "not established"
    }
    seen = set()
    for pool in POOLS:
        # On-chain GAMM TypeEvtPoolExited: pool_exited.pool_id.
        expr = "pool_exited.pool_id='"+str(pool)+"'"
        record = {"pool":pool, "indexed_event_query":expr, "pages_ok":0,
                  "total_count_reported":None,"complete":False}
        result["queries"].append(record)
        for page in range(1, PAGE_LIMIT+1):
            try:
                out, source = query_rpc("/tx_search", {
                    "query": expr, "prove": "false", "page": page,
                    "per_page": PER_PAGE, "order_by": "asc"
                })
                txs = out.get("txs") or []
                total = int(out.get("total_count") or 0)
                record["total_count_reported"] = total
                record["pages_ok"] += 1
                for item in txs:
                    h = item.get("hash")
                    code = item.get("tx_result",{}).get("code",0)
                    if h and h not in seen and code == 0:
                        seen.add(h)
                        result["candidate_exits"].append({
                          "tx_hash":h, "pool_id":pool,"height":item.get("height"),
                          "indexed_event":expr,
                          "source_rpc_query":source,
                          "status":"candidate, inspect decoded tx/messages and token_out before validating"
                        })
                if page*PER_PAGE>=total or not txs:
                    record["complete"]=True
                    break
            except Exception as e:
                record["error"]=str(e)
                result["errors"].append({"pool_id":pool,"page":page,"message":str(e)})
                break
        if not record["complete"] and "error" not in record:
            result["errors"].append({"pool_id":pool,"message":"page cap reached; incomplete results"})
    result["complete_coverage"] = all(q["complete"] for q in result["queries"])
    result["verified_lp_exit_transactions"] = []
    result["limitations"] = [
      "Event-index search is incomplete if archive index omits old events.",
      "Event match is only a candidate. Decode each transaction and receipt to confirm MsgExitPool and actual tokens_out.",
      "Do not confuse swaps, governance transfers, and LP removals.",
      "Do not identify people based only on wallet addresses.",
      "Historical pool balances and token price are needed to quantify USD value at transaction time."
    ]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("LP exit candidates:",len(result["candidate_exits"]))
    print("Coverage complete:",result["complete_coverage"])
    print("Verified transaction counts:",len(result["verified_lp_exit_transactions"]))
    print("Saved:",OUTPUT)
    if result["errors"]:
        print("Archive errors:",len(result["errors"]),"- see saved JSON")

if __name__=="__main__":
    main()
