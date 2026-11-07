#!/usr/bin/env python3
"""BLACKCYBER read-only historic BOOT pool reserve sampler (Osmosis archive).

Queries archival /block heights by UTC date, then the GAMM pool at that height.
Do not infer withdrawals from TVL/value changes; these snapshots are anchor
points requiring transaction reconciliation.
Run python3 scripts/osmosis_boot_reserves.py
"""
import datetime as dt
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

RPC=os.environ.get("OSMOSIS_ARCHIVE_RPC","https://rpc.archive.osmosis.zone").rstrip("/")
LCD=os.environ.get("OSMOSIS_ARCHIVE_LCD","https://lcd.archive.osmosis.zone").rstrip("/")
OUTPUT=Path("research/data/boot-pool-reserves.json")
POOLS=(596,597)
BOOT_DENOM="ibc/FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4"
DATES=(
 "2022-02-20", "2022-06-07", "2022-06-09", "2022-12-31",
 "2023-12-31", "2024-09-01", "2024-12-31",
 "2025-12-31", "2026-08-05", "2026-11-01"
)
DELAY=float(os.environ.get("OSMOSIS_RATE_DELAY_SECONDS","0.26"))

def fetch(url,block_height=None):
    headers={"User-Agent":"BLACKCYBER-Forensics/0.3","Accept":"application/json"}
    if block_height is not None:
        headers["x-cosmos-block-height"]=str(block_height)
    with urlopen(Request(url,headers=headers),timeout=25) as response:
        data=json.load(response)
        resp_height=response.headers.get("x-cosmos-block-height")
    time.sleep(DELAY)
    return data,resp_height

def parse_time(value):
    return dt.datetime.fromisoformat(value.replace("Z","+00:00"))

def block_info(height,cache):
    if height in cache:return cache[height]
    payload,_=fetch(RPC+"/block?height="+str(height))
    result=payload.get("result",{}).get("block",{}).get("header",{})
    when=parse_time(result["time"])
    cache[height]=when
    return when

def height_for_date(target,latest_height,cache):
    left,right=1,latest_height
    # Find first available block on/after target UTC.
    while left<right:
        mid=(left+right)//2
        stamp=block_info(mid,cache)
        if stamp<target:left=mid+1
        else:right=mid
    return left

def pool_balances(pid,height):
    path=f"/osmosis/gamm/v1beta1/pools/{pid}"
    data,response_height=fetch(LCD+path,block_height=height)
    pool=data.get("pool") or {}
    coins=[]
    for item in pool.get("pool_assets",pool.get("poolAssets",[])):
        token=item.get("token",{})
        if token.get("denom") and token.get("amount") is not None:
            coins.append({"denom":token["denom"],"amount_atomic":str(token["amount"])})
    return {"pool_id":pid,"requested_block":height,
            "response_block":response_height,"pool_type":pool.get("@type"),
            "balances":coins,
            "boot_denom_present":any(c["denom"]==BOOT_DENOM for c in coins),
            "total_shares_atomic":(pool.get("total_shares") or pool.get("totalShares") or {}).get("amount"),
            "status":"observed" if coins else "pool_not_decodable_or_unavailable"}

def main():
    output={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "network":"osmosis-1","token":"BOOT","denom":BOOT_DENOM,
            "block_samples":[],"failures":[],"time_coverage":"selected checkpoints only",
            "inference":"No LP removals or participant identities inferred from snapshots",
            "usd_valuation":None}
    try:
        status,_=fetch(RPC+"/status")
        latest=int(status["result"]["sync_info"]["latest_block_height"])
        output["latest_block_height"]=latest
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError) as e:
        output["failures"].append({"stage":"RPC status","error":str(e)})
        OUTPUT.parent.mkdir(parents=True,exist_ok=True)
        OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return
    cache={}
    latest_time=None
    try:latest_time=block_info(latest,cache)
    except Exception as e:output["failures"].append({"stage":"latest_block","error":str(e)})
    for day in DATES:
        target=parse_time(day+"T00:00:00Z")
        if latest_time and target>latest_time:
            output["failures"].append({"date":day,"error":"future relative to archive tip"})
            continue
        try:
            height=height_for_date(target,latest,cache)
            t=block_info(height,cache)
            sample={"target_date_utc":day,"block_height":height,
                    "block_time_utc":t.isoformat(),"pools":[]}
            for pid in POOLS:
                try:
                    sample["pools"].append(pool_balances(pid,height))
                except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError) as e:
                    sample["pools"].append({"pool_id":pid,"error":str(e)})
            output["block_samples"].append(sample)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError) as e:
            output["failures"].append({"date":day,"error":str(e)})
    output["date_samples_successful"]=len(output["block_samples"])
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Archive pool checkpoints saved:",len(output["block_samples"]),"failures:",len(output["failures"]))

if __name__=="__main__":
    main()
