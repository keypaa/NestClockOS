"""Benchmark the Laya router on a CSV: latency p50/p90 and RSS."""
import argparse, csv, os, resource, time, sys

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--csv", default="stt_rec1_test_for_router.csv")
    ap.add_argument("--n", type=int, default=100)
    args = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "phase0_5"))
    os.environ.setdefault("NESTCLOCK_ROUTER_DIR", args.model_dir)
    from voice.router import RouterService
    rs = RouterService(args.model_dir)
    t0 = time.time(); rs.load(); load_ms = (time.time() - t0) * 1000
    rss_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
    phrases = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            phrases.append(r.get("phrase", ""))
    phrases = (phrases * (args.n // len(phrases) + 1))[:args.n]
    ms_list = []
    for p in phrases:
        t = time.time()
        rs.route(p)
        ms_list.append((time.time() - t) * 1000)
    ms_sorted = sorted(ms_list)
    def pct(q): return ms_sorted[min(len(ms_sorted)-1, int(q*len(ms_sorted)))]
    print(f"load_ms={load_ms:.0f} rss_peak_mb={rss_after:.0f} n={len(ms_list)}")
    print(f"p50={pct(0.5):.1f}ms p90={pct(0.9):.1f}ms p99={pct(0.99):.1f}ms")
    with open("results/router_bench.json", "w") as f:
        import json
        json.dump({"load_ms": load_ms, "rss_peak_mb": rss_after, "n": len(ms_list),
                   "p50": pct(0.5), "p90": pct(0.9), "p99": pct(0.99)}, f, indent=2)

if __name__ == "__main__":
    main()
