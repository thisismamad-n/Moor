#!/usr/bin/env python3
import argparse, csv, json, math, statistics, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com"
UA = "moor-polymarket-scanner/0.1"


def fetch_json(url: str, timeout: float, retries: int = 2) -> Any:
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            if i < retries:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def get_json(path: str, params: Dict[str, Any], base: str, timeout: float) -> Any:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return fetch_json(base + path + (("?" + qs) if qs else ""), timeout)


def jfield(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def f(value: Any, default: float = 0.0) -> float:
    try:
        return default if value is None or value == "" else float(value)
    except Exception:
        return default


def i(value: Any, default: int = 0) -> int:
    try:
        return default if value is None or value == "" else int(float(value))
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def slugify(text: str, fallback: str) -> str:
    s = "".join(ch if ch.isalnum() else "-" for ch in (text or fallback).lower())
    s = "-".join(p for p in s.split("-") if p)
    return (s[:90] or fallback)


def fetch_markets(limit: int, min_volume: float, timeout: float) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    raw = get_json("/markets", {"limit": limit, "active": "true", "closed": "false", "order": "volume", "ascending": "false"}, GAMMA, timeout)
    markets = raw.get("markets", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])
    meta = raw if isinstance(raw, dict) else {"count": len(markets)}
    out = []
    for idx, m in enumerate(markets):
        outcomes = jfield(m.get("outcomes"), [])
        prices = jfield(m.get("outcomePrices"), [])
        tokens = jfield(m.get("clobTokenIds"), [])
        vol = f(m.get("volume"))
        if vol < min_volume:
            continue
        yes = f(prices[0] if len(prices) else None)
        no = f(prices[1] if len(prices) > 1 else None)
        slug = m.get("slug") or slugify(m.get("question", ""), m.get("id", ""))
        out.append({
            "index": idx,
            "id": m.get("id") or "",
            "condition_id": m.get("conditionId") or "",
            "slug": slug,
            "question": m.get("question") or "",
            "category": m.get("category") or "Uncategorized",
            "market_type": m.get("marketType") or "binary",
            "active": m.get("active"),
            "closed": m.get("closed"),
            "outcomes": outcomes,
            "yes_outcome": outcomes[0] if len(outcomes) else "Yes",
            "no_outcome": outcomes[1] if len(outcomes) > 1 else "No",
            "yes_token_id": tokens[0] if len(tokens) else "",
            "no_token_id": tokens[1] if len(tokens) > 1 else "",
            "yes_price": yes,
            "no_price": no,
            "implied_sum": yes + no,
            "binary_error": abs(1.0 - (yes + no)),
            "volume": vol,
            "liquidity": f(m.get("liquidity")),
            "open_interest": f(m.get("openInterest")),
            "created_at": m.get("createdAt"),
            "end_date": m.get("endDate"),
            "description": m.get("description") or "",
            "url": f"https://polymarket.com/event/{slug}",
            "raw": m,
        })
    return out, meta


def fetch_history(m: Dict[str, Any], interval: str, fidelity: int, timeout: float) -> List[Dict[str, Any]]:
    if not m.get("condition_id"):
        return []
    pts = []
    try:
        raw = get_json("/prices-history", {"market": m["condition_id"], "interval": interval, "fidelity": fidelity}, CLOB, timeout)
        hist = raw.get("history") if isinstance(raw, dict) else None
        if isinstance(hist, list):
            for row in hist:
                t, p = i(row.get("t")), f(row.get("p"), -1.0)
                if t > 0 and 0 <= p <= 1:
                    pts.append({"t": t, "p": p})
    except Exception:
        pass
    if pts:
        pts.sort(key=lambda x: x["t"])
        return pts[-fidelity:] if fidelity and len(pts) > fidelity else pts
    return fetch_trades_history(m, timeout, fidelity)


def fetch_trades_history(m: Dict[str, Any], timeout: float, fidelity: int) -> List[Dict[str, Any]]:
    if not m.get("condition_id"):
        return []
    try:
        raw = get_json("/trades", {"market": m["condition_id"], "limit": min(300, max(50, fidelity * 4))}, DATA, timeout)
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    buckets: Dict[int, List[float]] = {}
    for row in raw:
        t = i(row.get("timestamp"))
        price = f(row.get("price"), -1.0)
        if t <= 0 or price < 0 or price > 1:
            continue
        outcome_index = i(row.get("outcomeIndex"), -1)
        yes_price = 1.0 - price if outcome_index == 1 else price
        if not 0 <= yes_price <= 1:
            continue
        bucket = (t // 3600) * 3600
        buckets.setdefault(bucket, []).append(yes_price)
    pts = [{"t": t, "p": round(sum(vals) / len(vals), 4)} for t, vals in sorted(buckets.items())]
    if not pts:
        return []
    pts.sort(key=lambda x: x["t"])
    return pts[-fidelity:] if fidelity and len(pts) > fidelity else pts


def fetch_book(m: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    if not m.get("yes_token_id"):
        return {}
    try:
        book = get_json("/book", {"token_id": m["yes_token_id"]}, CLOB, timeout)
        spread = get_json("/spread", {"token_id": m["yes_token_id"]}, CLOB, timeout)
    except Exception:
        return {}
    bids = book.get("bids") if isinstance(book, dict) else []
    asks = book.get("asks") if isinstance(book, dict) else []
    best_bid = f((bids[0] or {}).get("price") if bids else None, -1.0)
    best_ask = f((asks[0] or {}).get("price") if asks else None, -1.0)
    clob_spread = f(spread.get("spread") if isinstance(spread, dict) else None, -1.0)
    if best_bid >= 0 and best_ask >= 0:
        clob_spread = max(clob_spread, best_ask - best_bid)
    return {
        "best_bid": best_bid if best_bid >= 0 else None,
        "best_ask": best_ask if best_ask >= 0 else None,
        "clob_spread": clob_spread if clob_spread >= 0 else None,
        "last_trade_price": f(book.get("last_trade_price") if isinstance(book, dict) else None, -1.0),
        "min_order_size": f(book.get("min_order_size") if isinstance(book, dict) else None, -1.0),
        "tick_size": f(book.get("tick_size") if isinstance(book, dict) else None, -1.0),
    }


def enrich(m: Dict[str, Any], hist: List[Dict[str, Any]], book: Dict[str, Any]) -> Dict[str, Any]:
    prices = [p["p"] for p in hist if 0 <= p.get("p", -1) <= 1]
    yes = clamp(m.get("yes_price", 0.0), 0, 1)
    first = prices[0] if prices else yes
    last = prices[-1] if prices else yes
    mom = last - first if prices else 0.0
    vol = statistics.pstdev(prices) if len(prices) > 1 else 0.0
    uncertainty = 1.0 - abs(yes - 0.5) * 2.0
    volume = max(0.0, f(m.get("volume")))
    liquidity = max(0.0, f(m.get("liquidity")))
    spread = book.get("clob_spread") or 0.02
    score = uncertainty * 22 + min(abs(mom), 0.5) * 90 + min(vol, 0.35) * 120 + math.log10(max(volume, 1) + 1) * 2.5 + math.log10(max(liquidity, 1) + 1) * 1.5 - spread * 150 - m.get("binary_error", 0) * 35
    if m.get("binary_error", 0) >= 0.04:
        signal = "binary-mismatch-watch"
    elif uncertainty >= 0.82 and score >= 28:
        signal = "coinflip-high-volatility"
    elif abs(mom) >= 0.12 and volume >= 100000:
        signal = "strong-momentum"
    elif vol >= 0.10 and volume >= 50000:
        signal = "volatile"
    elif volume >= 1000000 and uncertainty <= 0.25:
        signal = "deep-liquidity-conviction"
    else:
        signal = "normal"
    m = dict(m)
    m.update({
        "history_points": len(prices),
        "first_price": first,
        "last_price": last,
        "momentum": mom,
        "abs_momentum": abs(mom),
        "volatility": vol,
        "uncertainty": uncertainty,
        "book": book,
        "best_bid": book.get("best_bid"),
        "best_ask": book.get("best_ask"),
        "clob_spread": book.get("clob_spread"),
        "opportunity_score": round(max(score, 0), 3),
        "signal": signal,
        "trend": "up" if mom > 0.03 else "down" if mom < -0.03 else "flat",
    })
    return m


def write_csv(path: Path, markets: List[Dict[str, Any]]) -> None:
    fields = ["rank", "id", "condition_id", "slug", "question", "category", "yes_outcome", "no_outcome", "yes_price", "no_price", "implied_sum", "binary_error", "volume", "liquidity", "open_interest", "first_price", "last_price", "momentum", "volatility", "uncertainty", "opportunity_score", "signal", "trend", "best_bid", "best_ask", "clob_spread", "history_points", "url"]
    with path.open("w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=fields)
        w.writeheader()
        for rank, m in enumerate(markets, 1):
            row = {k: m.get(k, "") for k in fields}
            row["rank"] = rank
            w.writerow(row)


def summarize(markets: List[Dict[str, Any]]) -> Dict[str, Any]:
    vols = [f(m.get("volume")) for m in markets]
    scores = [f(m.get("opportunity_score")) for m in markets]
    counts: Dict[str, int] = {}
    for m in markets:
        counts[m.get("signal", "unknown")] = counts.get(m.get("signal", "unknown"), 0) + 1
    return {"market_count": len(markets), "total_volume": sum(vols), "median_volume": statistics.median(vols) if vols else 0, "max_volume": max(vols) if vols else 0, "avg_opportunity_score": statistics.mean(scores) if scores else 0, "top_opportunity_score": max(scores) if scores else 0, "signal_counts": counts}


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Polymarket scanner and snapshot writer.")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--history-limit", type=int, default=25)
    ap.add_argument("--interval", default="1d", choices=["all", "1d", "1w", "1m", "3m", "6m", "1y"])
    ap.add_argument("--fidelity", type=int, default=96)
    ap.add_argument("--fetch-books", action="store_true")
    ap.add_argument("--min-volume", type=float, default=0.0)
    ap.add_argument("--timeout", type=float, default=12.0)
    ap.add_argument("--sleep", type=float, default=0.08)
    ap.add_argument("--out-dir", default="data")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Fetching up to {args.limit} active Polymarket markets...")
    markets, meta = fetch_markets(args.limit, args.min_volume, args.timeout)
    print(f"Normalized {len(markets)} markets after filters.")
    candidates = sorted(markets, key=lambda m: (f(m.get("volume")), f(m.get("liquidity"))), reverse=True)[:max(0, min(args.history_limit, len(markets)))]
    histories: Dict[str, List[Dict[str, Any]]] = {}
    books: Dict[str, Dict[str, Any]] = {}
    for idx, m in enumerate(candidates, 1):
        print(f"[{idx}/{len(candidates)}] history {m.get('question', '')[:80]}")
        histories[m["id"]] = fetch_history(m, args.interval, args.fidelity, args.timeout)
        if args.fetch_books:
            books[m["id"]] = fetch_book(m, args.timeout)
            time.sleep(args.sleep)
        else:
            time.sleep(args.sleep * 0.25)

    enriched = [enrich(m, histories.get(m["id"], []), books.get(m["id"], {})) for m in markets]
    enriched.sort(key=lambda m: (f(m.get("volume")), f(m.get("opportunity_score"))), reverse=True)
    top = sorted(enriched, key=lambda m: f(m.get("opportunity_score")), reverse=True)[:20]
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "not_financial_advice": True,
        "sources": {"gamma_markets": GAMMA + "/markets", "clob_history": CLOB + "/prices-history", "clob_books": CLOB + "/book" if args.fetch_books else "not fetched", "data_trades": DATA + "/trades"},
        "request": {"limit": args.limit, "history_limit": len(candidates), "interval": args.interval, "fidelity": args.fidelity, "min_volume": args.min_volume, "fetch_books": args.fetch_books},
        "gamma_meta": meta,
        "summary": summarize(enriched),
        "top_signals": top,
        "markets": enriched,
    }
    snap_path = out_dir / "polymarket_snapshot.json"
    csv_path = out_dir / "polymarket_markets.csv"
    hist_path = out_dir / "polymarket_history.json"
    snap_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(csv_path, enriched)
    hist_path.write_text(json.dumps({"generated_at": snapshot["generated_at"], "histories": [{"id": m["id"], "question": m.get("question"), "history": histories.get(m["id"], [])} for m in enriched if histories.get(m["id"])]}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {snap_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {hist_path}")
    print("Top opportunity signals:")
    for rank, m in enumerate(top[:5], 1):
        print(f"{rank}. {m.get('signal')} score={f(m.get('opportunity_score')):.1f} yes={f(m.get('yes_price')):.2f} vol=${f(m.get('volume')):,.0f} {m.get('question', '')[:72]}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
