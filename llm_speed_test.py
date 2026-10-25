#!/usr/bin/env python3
"""NestClockOS — Mistral cloud-fallback LLM speed test.

Measures wall-clock latency of the cloud LLM leg (the path every deferred /
fallback utterance pays: STT -> router -> LLM -> [TTS]). Non-streaming full
completion, short clock-assistant answers — representative of fallback use.

Setup:
    pip install mistralai
    export MISTRAL_API_KEY="your-key-here"   # or put it in .env (export wins)

Usage:
    python llm_speed_test.py [--model mistral-small-latest] [--repeat 2]
    python llm_speed_test.py --csv my_prompts.csv --out timings.csv
    python llm_speed_test.py --dry-run   # no API calls, shows what would run

CSV format (optional): header must include a `phrase` column; a `language`
column is used for the per-language breakdown when present.
"""
import argparse
import csv
import os
import re
import statistics
import sys
import time


def import_client():
    try:
        from mistralai import Mistral  # v1 SDK (Phase-0 era import path)
    except ImportError:
        from mistralai.client import Mistral  # v3 SDK
    return Mistral


_last_start = [0.0]


def pace(min_interval_s):
    """Enforce a minimum gap between request starts (default 1/s limit)."""
    now = time.monotonic()
    wait = min_interval_s - (now - _last_start[0])
    if wait > 0:
        time.sleep(wait)
    _last_start[0] = time.monotonic()


def load_dotenv(path=".env"):
    """Minimal .env loader (KEY=VALUE, # comments, optional quotes).

    stdlib only — no python-dotenv dependency. Never overwrites variables
    already present in the environment; export still wins over .env.
    """
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    return True

SYSTEM_PROMPT = (
    "You are NestClock, a smart-clock voice assistant. "
    "Answer briefly, in the user's language, in at most two sentences."
)

# Clock-domain fallback traffic: chatter, knowledge questions, weather phrasing
# (incl. the accepted French-syntax residual), song-ID, arithmetic. Tagged for
# the per-language breakdown.
DEFAULT_PROMPTS = [
    ("Tell me something interesting", "en"),
    ("Peux-tu m'expliquer la relativité", "fr"),
    ("Raconte-moi une blague", "fr"),
    ("What's the capital of France", "en"),
    ("Combien font 2 plus 2", "fr"),
    ("il pleut à Lyon en ce moment", "fr"),
    ("Is it going to rain this afternoon", "en"),
    ("who is this artist", "en"),
    ("what is 19 minus 14", "en"),
    ("euh ouais donc en fait", "fr"),
    ("Quelle est la capitale de l'Allemagne", "fr"),
    ("tell me une histoire", "mixed"),
]


def percentile(data, pct):
    if not data:
        return float("nan")
    ordered = sorted(data)
    k = (len(ordered) - 1) * pct / 100
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def run_once(client, model, system, prompt, max_tokens, retries=4):
    """One timed call with backoff on rate limits. Returns
    (dt_ms, prompt_toks, completion_toks, error). dt_ms is None on failure."""
    attempt, wait = 0, 5
    while True:
        try:
            t0 = time.perf_counter()
            resp = client.chat.complete(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
            )
            dt_ms = (time.perf_counter() - t0) * 1000
            usage = getattr(resp, "usage", None)
            prompt_toks = getattr(usage, "prompt_tokens", None) if usage else None
            completion_toks = getattr(usage, "completion_tokens", None) if usage else None
            return dt_ms, prompt_toks, completion_toks, None
        except Exception as e:  # SDKError (429 etc.) — SDK class differs v1/v3
            msg = str(e)
            rate_limited = "429" in msg or "rate_limit" in msg.lower() or "rate limit" in msg.lower()
            attempt += 1
            if not rate_limited or attempt > retries:
                return None, None, None, f"{type(e).__name__}: {msg[:120]}"
            # honor Retry-After when present, else exponential backoff
            retry_after = None
            m = re.search(r"[Rr]etry-?[Aa]fter[:\s]+(\d+)", msg)
            if m:
                retry_after = int(m.group(1))
            sleep_s = retry_after if retry_after else wait
            print(f"  rate-limited, sleeping {sleep_s}s (attempt {attempt}/{retries})...", flush=True)
            time.sleep(sleep_s)
            wait = min(wait * 2, 60)


def load_prompts(csv_path):
    prompts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "phrase" not in (reader.fieldnames or []):
            sys.exit("CSV needs a 'phrase' column (plus optional 'language').")
        for row in reader:
            prompts.append((row["phrase"], row.get("language", "?")))
    return prompts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mistral-small-2603")
    ap.add_argument("--min-interval", type=float, default=1.0,
                    help="minimum seconds between request starts (rate limit pacing)")
    ap.add_argument("--csv", default=None, help="CSV with phrase[,language] columns; defaults to embedded list")
    ap.add_argument("--repeat", type=int, default=1, help="repeats per prompt (p90 stability)")
    ap.add_argument("--max-tokens", type=int, default=150)
    ap.add_argument("--system", default=SYSTEM_PROMPT)
    ap.add_argument("--out", default=None, help="write per-call timings CSV here (updated after every call, Ctrl+C-safe)")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N prompt×repeat calls (resume a throttled run)")
    ap.add_argument("--limit", type=int, default=None, help="run at most N calls (quota-friendly chunks)")
    ap.add_argument("--dry-run", action="store_true", help="print config + prompts, make no API calls")
    args = ap.parse_args()

    prompts = load_prompts(args.csv) if args.csv else list(DEFAULT_PROMPTS)
    total_calls = len(prompts) * args.repeat
    print(f"model={args.model} prompts={len(prompts)} repeat={args.repeat} "
          f"calls={total_calls} max_tokens={args.max_tokens}")

    if args.dry_run:
        for phrase, lang in prompts:
            print(f"  [{lang}] {phrase}")
        print("dry run — no API calls made")
        return

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and load_dotenv():
        api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("Set MISTRAL_API_KEY (env, export, or .env) before running (or use --dry-run).")

    Mistral = import_client()
    def save():
        if args.out:
            with open(args.out, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["phrase", "language", "lat_ms", "prompt_tokens", "completion_tokens", "error"])
                w.writeheader()
                w.writerows(rows)

    def summarize():
        print("-" * 60)
        if lat_all:
            print(f"overall: n={len(lat_all)} ok, {n_failed} failed | "
                  f"p50={percentile(lat_all, 50):.0f}ms p90={percentile(lat_all, 90):.0f}ms")
            for lang, lat in lat_by_lang.items():
                print(f"  {lang}: n={len(lat)} p50={percentile(lat, 50):.0f}ms p90={percentile(lat, 90):.0f}ms")
        else:
            print(f"no successful calls ({n_failed} failed) — check key/quota")

    client = Mistral(api_key=api_key)
    lat_all, lat_by_lang, rows = [], {}, []
    n_failed = 0
    call_idx = 0
    try:
        for phrase, lang in prompts:
            for _ in range(args.repeat):
                call_idx += 1
                if call_idx <= args.offset:
                    continue
                if args.limit is not None and len(rows) >= args.limit:
                    raise StopIteration
                pace(args.min_interval)
                dt_ms, ptoks, ctoks, err = run_once(client, args.model, args.system, phrase, args.max_tokens)
                if err:
                    n_failed += 1
                    print(f"   FAILED [{lang}] {phrase[:60]} :: {err}")
                    rows.append({"phrase": phrase, "language": lang, "lat_ms": "",
                                 "prompt_tokens": "", "completion_tokens": "", "error": err})
                    save()
                    continue
                lat_all.append(dt_ms)
                lat_by_lang.setdefault(lang, []).append(dt_ms)
                rows.append({"phrase": phrase, "language": lang, "lat_ms": round(dt_ms, 1),
                             "prompt_tokens": ptoks, "completion_tokens": ctoks, "error": ""})
                print(f"{dt_ms:8.0f}ms [{lang}] {phrase[:60]}")
                save()
    except (KeyboardInterrupt, StopIteration):
        pass

    summarize()
    save()
    if args.out:
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
