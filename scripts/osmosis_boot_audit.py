#!/usr/bin/env python3
"""BLACKCYBER / BOOT liquidity: current Osmosis pool discovery and evidence snapshot.

READ ONLY: uses public Osmosis SQS API. No wallets or private keys.
Usage: python3 scripts/osmosis_boot_audit.py
Output: research/data/osmosis-boot-pools-latest.json
This captures CURRENT pool state only; it DOES NOT establish historical LP removals.
"""
import datetime as dt
import json
import pathlib
import urllib.parse
import urllib.request

SQS="https://sqs.osmosis.zone"
LCD="https://lcd.osmosis.zone"
BOOT_DENOM="ibc/E6931F78057F7CC5DA0FD6CEF82FF39373A6E0452BF1FD76910B93292CF356C1"
BOOT_HASH=BOOT_DENOM.split("/",1)[1]
OUTPUT=pathlib.Path("research/data/osmosis-boot-pools-latest.json")

def fetch(base, path, params=None):
    url=base+path
    if params:
        url+="?"+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={"User-Agent":"BLACKCYBER-research/0.1 (read-only)", "Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=35) as res:
        return json.load(res),url

def main():
    result={
      "generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "network":"osmosis-1","asset":"BOOT","denom":BOOT_DENOM,
      "purpose":"Discover current BOOT pools; NOT attribution of withdrawals",
      "sources":{},"pools":[],"errors":[],"historical_withdrawals_verified":False
    }
    # Verify that the historical asset IBC hash still points at boot/channel-95,
    # and not a different asset with a matching display symbol.
    try:
        trace,url=fetch(LCD,"/ibc/apps/transfer/v1/denom_traces/"+BOOT_HASH)
        result["sources"]["denom_trace"]=url
        result["denom_trace"]=trace
        v=trace.get("denom_trace",{})
        if v.get("base_denom")!="boot" or "channel-95" not in v.get("path",""):
            result["errors"].append("DENOM CHECK FAILED: requires manual confirmation; pool results not trusted")
            result["integrity_passed"]=False
            OUTPUT.parent.mkdir(parents=True,exist_ok=True)
            OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
            raise SystemExit(2)
        result["integrity_passed"]=True
    except Exception as err:
        result["errors"].append("Denom verification unavailable: "+str(err))
        result["integrity_passed"]=False

    # Historical BOOT pools: 595, 596 and 597 from Osmosis 2021-2023 public records.\n    # They must be verified against the BOOT IBC denom in current pool balances.\n    result["historical_pool_ids_to_check"]=[595,596,597]\n    # SQS /pools is an officially documented pool-discovery endpoint.
    # A successful match is an on-chain pool association, not an ownership claim.
    cursor=0
    for page in range(30):
        try:
            obj,url=fetch(SQS,"/pools",{"filter[denom]":BOOT_DENOM,"page[size]":100,"page[cursor]":cursor})
        except Exception as err:
            result["errors"].append(f"Pool query failed at cursor {cursor}: {err}")
            break
        result["sources"]["pools"]=SQS+"/pools?filter[denom]="+urllib.parse.quote(BOOT_DENOM,safe="/")
        rows=obj.get("data",[])
        result["pools"].extend(rows)
        if len(rows)==0:break
        nxt=obj.get("meta",{}).get("next_cursor",-1)
        if nxt in (-1,None) or str(nxt)==str(cursor):break
        cursor=int(nxt)
    # Independently request documented historical pool IDs.\n    # This is not a historical snapshot; data returned is the current state.\n    try:\n        known,url=fetch(SQS,"/pools",{"filter[id]":"595,596,597"})\n        result["sources"]["historical_pool_id_lookup"]=url\n        result["historical_pool_current_status"]=known.get("data",[]) if isinstance(known,dict) else known\n    except Exception as err:\n        result["errors"].append("Historical pool ID lookup unavailable: "+str(err))\n    # Do not interpret status until denom trace is validated.
    result["pool_count"]=len(result["pools"])
    result["analysis_limitations"]=[
       "Snapshot is latest state, not reserves in 2025/2026.",
       "An LP withdrawal requires a verified MsgExitPool or MsgWithdrawPosition tx, with pool_id, sender, amounts and tx hash.",
       "Swaps change reserves; reserve decrease alone is not evidence of LP withdrawal.",
       "An address does not identify a person without independent verification.",
       "If denom trace cannot be validated, this snapshot is unverified."
    ]
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Saved",OUTPUT,"pool_count=",result["pool_count"],"integrity=",result["integrity_passed"])
    for p in result["pools"]:
        print("pool ID:",p.get("id",p.get("pool_id",p.get("poolId","unknown"))))
    if not result["integrity_passed"]:
        raise SystemExit("Unverified denom: do NOT use pools as confirmed evidence")

if __name__=="__main__":
    main()
