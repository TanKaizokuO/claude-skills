#!/usr/bin/env python3
"""Populate a COPY of the verified Token Ledger DB and reprice it from pricing.json.

Usage:
  populate.py --db <copy.sqlite3> [--src <verified.sqlite3>] [--pricing <pricing.json>]

- --src (optional): first make the copy with the sqlite backup API. The source is
  opened read-only (mode=ro). Omit --src to reprice an existing copy in place.
- --db: the COPY to write. Must not be the verified DB (path with /verified/ is refused).
- FX rate comes from pricing.json currency.per_usd. Nothing is hardcoded.

Run before token_ledger.store.database.open_database(run_migrations=True) on the copy.
"""
import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys
import time

DEFAULT_PRICING = os.path.join(
    os.environ.get("TOKEN_TRACKER_REPO", "/home/tankaizokuo/Code/projects/token-tracker"),
    "pricing.json",
)
EFF = ("low", "medium", "high", "xhigh", "max")


def normalize_model(model):
    if not model:
        return "unknown"
    model = model.rsplit("/", 1)[-1]
    if model.startswith("claude-"):
        model = model.replace(".", "-")
    parts = model.split("-")
    if parts[-1].isdigit() and len(parts[-1]) == 8:
        return "-".join(parts[:-1])
    if model.startswith("gemini-") and parts[-1] in ("low", "medium", "high", "xhigh"):
        return "-".join(parts[:-1])
    return model


def make_rate_key(models):
    def rate_key(model):
        if model in models:
            return model
        base, sep, eff = model.rpartition("-")
        if sep and eff in EFF and base in models:
            return base
        return model

    return rate_key


def provider_of(key):
    for p, v in (("claude", "anthropic"), ("gpt", "openai"), ("gemini", "google"),
                 ("glm", "z-ai"), ("kimi", "moonshot")):
        if key.startswith(p):
            return v
    return "unknown"


def backup(src_path, dst_path):
    if os.path.exists(dst_path):
        os.remove(dst_path)
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    t = time.time()
    src = sqlite3.connect("file:%s?mode=ro" % os.path.abspath(src_path), uri=True)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    print("backup ok seconds", round(time.time() - t, 1), "bytes", os.path.getsize(dst_path), flush=True)


def reprice(db_path, pj_bytes):
    pj = json.loads(pj_bytes)
    models = pj["models"]
    currency = pj.get("currency") or {}
    if currency.get("code") != "INR" or not isinstance(currency.get("per_usd"), (int, float)):
        raise SystemExit("pricing.json currency must have code INR and numeric per_usd")
    FX = float(currency["per_usd"])
    VERSION = "pricing-json-" + hashlib.sha256(pj_bytes).hexdigest()[:12]
    NOW = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rate_key = make_rate_key(models)

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("BEGIN")
    cur.execute("DELETE FROM financial_facts")
    cur.execute(
        "INSERT OR REPLACE INTO pricing_versions (version_id, pricing_hash, currency_code, effective_start, "
        "effective_end, source_provenance_json, created_at) VALUES (?,?,?,?,?,?,?)",
        (VERSION, hashlib.sha256(pj_bytes).hexdigest(), "USD", "2026-01-01", None,
         json.dumps({"source": "token-tracker pricing.json",
                     "note": "copy-only build; costs from pricing.json with tokentrack formula"}), NOW),
    )
    cur.execute("DELETE FROM model_pricing_rates WHERE version_id = ?", (VERSION,))
    for key, r in models.items():
        if "in" not in r:
            continue
        tiered = r.get("long")
        cur.execute(
            """INSERT INTO model_pricing_rates (version_id, provider, model_identity, access_route, input_rate_per_m,
               output_rate_per_m, cache_read_rate_per_m, cache_write_5m_rate_per_m, cache_write_1h_rate_per_m,
               is_tiered, prompt_threshold, tiered_rates_json, status, source_url, verified_on, note)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (VERSION, provider_of(key), key, "default", r["in"], r["out"], r.get("cr"), r.get("cw5m"),
             r.get("cw1h"), 1 if tiered else 0, tiered["threshold"] if tiered else None,
             json.dumps(tiered) if tiered else "{}", r.get("status") or "verified",
             r.get("source_url"), r.get("verified_on"), r.get("note")),
        )
    cur.execute("DELETE FROM historical_fx WHERE base_currency='USD' AND target_currency='INR' "
                "AND effective_date='2026-01-01'")
    cur.execute("INSERT INTO historical_fx (base_currency, target_currency, rate_per_usd, effective_date, "
                "source_provenance, created_at) VALUES ('USD','INR',?,'2026-01-01','pricing.json currency',?)",
                (FX, NOW))

    rows = cur.execute(
        """select c.canonical_id, c.raw_model, c.request_timestamp,
           coalesce(u.fresh_input_tokens,0), coalesce(u.cache_read_tokens,0),
           coalesce(u.cache_write_5m_tokens,0) + coalesce(u.cache_write_unknown_ttl_tokens,0),
           coalesce(u.cache_write_1h_tokens,0),
           coalesce(u.output_tokens,0)
           from canonical_requests c left join normalized_usage u using(canonical_id)"""
    ).fetchall()
    ins = []
    priced = unpriced = 0
    total = 0.0
    # Unknown-TTL writes are priced at the 5m rate (the API default), so they are folded into cw5.
    for cid, raw, ts, fi, cr, cw5, cw1, out in rows:
        key = rate_key(normalize_model(raw))
        r = models.get(key)
        if not r or "in" not in r:
            ins.append((cid, None, None, None, None, None, "unpriced", None, NOW, None))
            unpriced += 1
            continue
        rr = r
        lg = r.get("long")
        if lg and (fi + cr + cw5 + cw1) > lg["threshold"]:
            rr = {**r, **{k: lg[k] for k in ("in", "out", "cw5m", "cw1h", "cr") if k in lg}}
        cost = (fi * rr["in"] + out * rr["out"] + cw5 * rr.get("cw5m", 0) + cw1 * rr.get("cw1h", 0)
                + cr * rr.get("cr", 0)) / 1e6
        status = "verified" if r.get("status") in (None, "verified") else "estimated"
        savings = None
        # No cache activity means savings of exactly 0, not unknown.
        if all(k in rr for k in ("cr", "cw5m", "cw1h")):
            savings = round(cr * (rr["in"] - rr["cr"]) / 1e6 + cw5 * (rr["in"] - rr["cw5m"]) / 1e6
                            + cw1 * (rr["in"] - rr["cw1h"]) / 1e6, 8)
        usd = round(cost, 8)
        ins.append((cid, VERSION, None, None, usd, round(usd * FX, 6), status, FX, NOW, savings))
        priced += 1
        total += usd
    cur.executemany(
        """INSERT INTO financial_facts (canonical_id, pricing_version_id, actual_billed_amount, actual_billed_currency,
           api_equivalent_usd, api_equivalent_inr, subscription_fee_usd, cache_savings_usd, pricing_status,
           fx_rate_applied, calculated_at, valuation_provenance_json)
           VALUES (?,?,?,?,?,?,NULL,?,?,?,?,NULL)""",
        [(c, v, a, cu, usd, inr, sv, st, fx, calc) for (c, v, a, cu, usd, inr, st, fx, calc, sv) in ins],
    )
    con.commit()
    print("version", VERSION)
    print("fx per_usd (from pricing.json)", FX)
    print("rows", len(rows), "priced", priced, "unpriced", unpriced)
    print("total_usd", round(total, 2), "INR", round(total * FX))
    print("financial_facts rows", cur.execute("select count(*) from financial_facts").fetchone()[0])
    con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the COPY to write")
    ap.add_argument("--src", help="verified DB to copy from (opened read-only)")
    ap.add_argument("--pricing", default=DEFAULT_PRICING, help="pricing.json path")
    args = ap.parse_args()

    dst = os.path.abspath(args.db)
    if "/verified/" in dst:
        sys.exit("refusing to write a path under /verified/")
    if args.src:
        if os.path.abspath(args.src) == dst:
            sys.exit("--db must not be the source")
        backup(args.src, dst)
    if not os.path.isfile(dst):
        sys.exit("copy not found: %s (pass --src to create it)" % dst)

    with open(args.pricing, "rb") as f:
        pj_bytes = f.read()
    reprice(dst, pj_bytes)


if __name__ == "__main__":
    main()
