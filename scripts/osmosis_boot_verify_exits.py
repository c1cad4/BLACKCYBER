#!/usr/bin/env python3
"""BLACKCYBER: verify and rank archival BOOT LP-exit candidates.

Input: research/data/boot-lp-exits.json (candidate tx hashes collected separately).
Output: research/data/boot-lp-exits-verified.json

This script is READ ONLY. It NEVER infers real-world wallet ownership.
Verified=successful transaction, decoded message referencing target pool and
exit/withdraw semantics. USD valuation is intentionally omitted until an
independently sourced contemporaneous price is available.
"""
import datetime as dt
import json
import os
import time
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LCD = os.environ.get("OSMOSIS_ARCHIVE_LCD", "https://lcd.archive.osmosis.zone").rstrip("/")
RPC = os.environ.get("OSMOSIS_ARCHIVE_RPC", "https://rpc.archive.osmosis.zone").rstrip("/")
SOURCE = Path("research/data/boot-lp-exits.json")
DEST = Path("research/data/boot-lp-exits-verified.json")
POOLS = {596, 597}
MAX_CANDIDATES = int(os.environ.get("BOOT_MAX_CANDIDATES","250"))
BOOT_DENOM = "ibc/FE2CD1E6828EC0FAB8AF39BAC45BC25B965BA67CCBC50C13A14BD610B0D1E2C4"

def request(url):
    with urlopen(Request(url, headers={"Accept":"application/json",
                                      "User-Agent":"BLACKCYBER-Forensics/0.3"}),
                 timeout=25) as response:
        return json.load(response)

def normalize_hash(value):
    h = str(value or "").upper().removeprefix("0X")
    if len(h) != 64 or any(x not in "0123456789ABCDEF" for x in h):
        raise ValueError("Invalid transaction hash")
    return h

def coins(value):
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        denom=item.get("denom")
        amount=item.get("amount")
        try:
            n = Decimal(str(amount))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if denom and n >= 0:
            out.append({"denom":denom,"amount_atomic":str(n)})
    return out

def classify_messages(tx, pool):
    """Only accept explicit decoded LP exit messages with matching pool id."""
    found = []
    body=tx.get("tx",{}).get("body",{})
    messages=body.get("messages",[])
    if not isinstance(messages,list):
        return found
    for msg in messages:
        ty = str(msg.get("@type",msg.get("type","")))
        if not ("MsgExitPool" in ty or "MsgWithdrawPosition" in ty):
            continue
        pid=msg.get("pool_id",msg.get("poolId"))
        try: pid=int(pid)
        except (TypeError,ValueError): continue
        if pid!=pool:
            continue
        sender=msg.get("sender",msg.get("owner",""))
        shares=msg.get("share_in_amount",msg.get("liquidity_amount"))
        found.append({"message_type":ty,"pool_id":pid,"sender_address":sender,
                      "shares_or_liquidity_atomic":str(shares) if shares is not None else None,
                      "minimum_tokens_out":coins(msg.get("token_out_mins",[]))})
    return found

def extract_actual_out(tx):
    """Collect event-delivered amounts as unverified hints; no inference of USD."""
    logs=tx.get("logs",[]) or []
    raw=tx.get("events",[]) or []
    events=list(raw)
    for log in logs:
        events.extend(log.get("events",[]) or [])
    result=[]
    for event in events:
        kind=event.get("type","")
        if kind not in ("pool_exited","transfer","coin_received","withdraw_position"):
            continue
        attrs=event.get("attributes",[]) or []
        clean={}
        for a in attrs:
            k=a.get("key");v=a.get("value")
            if k is not None: clean[str(k)]=str(v)
        result.append({"event_type":kind,"attributes":clean})
    return result

def parse_token_amounts(s):
    """Parse Cosmos comma-separated integer coin quantities without prices."""
    import re
    if not isinstance(s,str):
        return []
    pieces=s.split(",")
    parsed=[]
    for item in pieces:
        m=re.fullmatch(r"\s*(\d+)([A-Za-z][^\s,]*)\s*",item)
        if not m:
            return []
        parsed.append({"amount_atomic":m.group(1),"denom":m.group(2)})
    return parsed

def match_pool_exit_events(tx_response,pool,sender):
    """Actual tokens_out only if exactly ONE unambiguous event matches pool/sender."""
    matches=[]
    # Prefer per-message ABCI logs; each carries a msg_index.
    for log in tx_response.get("logs",[]) or []:
        for ev in log.get("events",[]) or []:
            if ev.get("type")!="pool_exited":
                continue
            attrs={str(a.get("key")):str(a.get("value"))
                   for a in ev.get("attributes",[]) or []}
            if str(attrs.get("pool_id"))!=str(pool) or attrs.get("sender")!=sender:
                continue
            parsed=parse_token_amounts(attrs.get("tokens_out"))
            if parsed:
                matches.append({"message_index":log.get("msg_index"),"tokens_out":parsed})
    return matches if len(matches)==1 else []

def inspect_candidate(entry):
    pool=int(entry["pool_id"])
    if pool not in POOLS:
        raise ValueError("Not an audited BOOT pool")
    h=normalize_hash(entry["tx_hash"])
    tx=request(LCD+"/cosmos/tx/v1beta1/txs/"+h)
    resp=tx.get("tx_response",{})
    if int(resp.get("code",0))!=0:
        return {"hash":h,"pool_id":pool,"status":"failed_tx","code":resp.get("code")}
    messages=classify_messages(tx,pool)
    if not messages:
        return {"hash":h,"pool_id":pool,"status":"unconfirmed_message",
                "reason":"No matching explicit decoded LP exit message"}
    height=str(resp.get("height") or entry.get("height") or "")
    stamp=resp.get("timestamp")
    if not stamp and height:
        block=request(RPC+"/block?height="+height)
        stamp=(block.get("result",{}).get("block",{}).get("header",{}).get("time"))
    actual=[]
    if len(messages)==1 and messages[0].get("sender_address"):
        actual=match_pool_exit_events(resp,pool,messages[0]["sender_address"])
    return {"hash":h,"pool_id":pool,"height":height,"timestamp_utc":stamp,
            "status":"confirmed_successful_lp_exit_message",
            "messages":messages,
            "event_hints":extract_actual_out(resp),
            "amounts_verified":len(actual)==1,
            "actual_tokens_out":actual[0]["tokens_out"] if actual else None,
            "amounts_note":"Matched unique pool_exited event" if actual else "No unique pool_exited event: actual amounts unresolved",
            "usd_value":None,
            "attributed_human":None}

def summarize(records):
    per_sender=defaultdict(lambda: {"exit_tx_count":0,"hashes":[],"pool_ids":set()})
    for record in records:
        if record.get("status")!="confirmed_successful_lp_exit_message":
            continue
        for msg in record.get("messages",[]):
            sender=msg.get("sender_address")
            if not sender:
                continue
            key=(record["hash"],msg["pool_id"])
            item=per_sender[sender]
            if record["hash"] not in item["hashes"]:
                item["hashes"].append(record["hash"])
                item["exit_tx_count"]+=1
            item["pool_ids"].add(msg["pool_id"])
    return [{"sender_address":k,"exit_tx_count":v["exit_tx_count"],
             "pool_ids":sorted(v["pool_ids"]),"hashes":v["hashes"],
             "total_removed_usd":None,"identity":"not independently attributed"}
             for k,v in sorted(per_sender.items(),key=lambda e:-e[1]["exit_tx_count"])]

def main():
    raw=json.loads(SOURCE.read_text(encoding="utf-8"))
    candidates=raw.get("candidate_exits",[])
    # Fail-safe: partial coverage stays partial, regardless of successes.
    result={"generated_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source_file":str(SOURCE),"source_complete_coverage":raw.get("complete_coverage") is True,
            "candidates_reported":len(candidates),"candidates_reviewed":0,
            "records":[],"failures":[],"ranking_by_exit_count":[],
            "ranking_by_usd_amount":None,
            "note":"Amounts and people are not inferred from raw events or addresses."}
    seen=set()
    for entry in candidates[:MAX_CANDIDATES]:
        key=(entry.get("tx_hash"),entry.get("pool_id"))
        if key in seen:continue
        seen.add(key)
        try:
            record=inspect_candidate(entry)
            result["records"].append(record)
        except (HTTPError,URLError,TimeoutError,OSError,ValueError,KeyError) as exc:
            result["failures"].append({"tx_hash":entry.get("tx_hash"),
                                      "pool_id":entry.get("pool_id"),"error":str(exc)})
        result["candidates_reviewed"]+=1
        time.sleep(.21)
    result["ranking_by_exit_count"]=summarize(result["records"])
    result["coverage_complete_and_verified"]=(
         result["source_complete_coverage"] and len(result["failures"])==0
         and len(candidates)<=MAX_CANDIDATES)
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Candidate events:",len(candidates))
    print("Successful LP exit messages:",
          sum(x.get("status")=="confirmed_successful_lp_exit_message" for x in result["records"]))
    print("Archive failures:",len(result["failures"]))
    print("Result:",DEST)

if __name__=="__main__":
    main()
