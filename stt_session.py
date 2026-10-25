"""
NestClockOS — Phase 4a: speech-to-text reality check (push-to-talk, no wake word yet).

Phase 0 tested the router on clean TEXT. Nobody has yet tested what Voxtral hears
when YOU speak in your room. This script does that, in both languages.

Setup:  pip install sounddevice numpy mistralai      (and: set MISTRAL_API_KEY in .env)&

    python stt_session.py devices                    # list microphones
    python stt_session.py meter [--device N]         # live level + verdict: is this the right mic?
    python stt_session.py talk                       # free-form: say anything, read the transcript
    python stt_session.py script --n 40 --save-audio rec1   # read prompted phrases aloud, get a score
    python stt_session.py replay rec1 --lang fr --out r_fr.csv   # same recordings, other language setting
    python stt_session.py compare stt_results.csv stt_rec1.csv r_fr.csv   # where do the runs disagree?
    python stt_session.py script --csv synthetic_dataset_raw.csv --split held_out_eval --n 60

How to speak: press Enter, pause HALF A SECOND (the script measures room noise during
that pause), then speak naturally. It stops by itself after ~0.8 s of silence.
"""

import argparse
import csv

import queue
import random
import re
import statistics
import sys
import tempfile
import time
import unicodedata
import wave
from collections import defaultdict
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
FRAME = 800  # 50 ms
from voice.endpoint import Endpointer, PRE_FRAMES, TAIL_FRAMES, GLITCH_RMS
from voice.audio import to_16k
from voice.text import normalize, wer

MODEL = "voxtral-mini-latest"
PRE_FRAMES = 6   # 0.3 s kept before speech onset, so the first phoneme isn't clipped
TAIL_FRAMES = 5  # 0.25 s kept after the last loud frame
GLITCH_RMS = 0.5  # louder than any real room or voice: a saturated signal


def _open_settings(device):
    """(rate, channels) this input device will accept. Raw hw: devices often refuse 16 kHz mono."""
    import sounddevice as sd

    native = int(sd.query_devices(device, "input")["default_samplerate"])
    for rate, ch in ((SAMPLE_RATE, 1), (native, 1), (native, 2)):
        try:
            sd.check_input_settings(device=device, channels=ch, samplerate=rate, dtype="float32")
            return rate, ch
        except Exception:
            continue
    raise RuntimeError(f"Cannot open input device {device!r} (tried 16 kHz and {native} Hz, mono and stereo).")


def record_utterance(device=None, info=None, **endpointer_kwargs):
    """Record one utterance. Returns int16 audio at 16 kHz, or None if nobody spoke.
    If `info` is a dict it is filled with diagnostics (room noise, trigger level, loudest moment)."""
    import sounddevice as sd

    rate, channels = _open_settings(device)
    q = queue.Queue()
    ep = Endpointer(**endpointer_kwargs)
    frames, skipped, peak = [], 0, 0.0

    def callback(indata, n, t, status):
        q.put(indata.mean(axis=1).copy())  # mono, at the device's own rate

    with sd.InputStream(samplerate=rate, channels=channels, dtype="float32",
                        blocksize=int(rate * ep.frame_s), device=device, callback=callback):
        while True:
            try:
                block = q.get(timeout=3)
            except queue.Empty:
                raise RuntimeError("No audio from the microphone (wrong --device?)") from None
            if skipped < 3:  # drop the first 150 ms: the Enter-key click
                skipped += 1
                continue
            frames.append(block)
            rms = float(np.sqrt(np.mean(block ** 2)))
            if ep.threshold is not None:
                peak = max(peak, rms)
            status = ep.feed(rms)
            if status != "wait":
                break

    if info is not None:
        info.update(floor=ep.floor, threshold=ep.threshold, peak=peak, rate=rate,
                    channels=channels, glitches=ep.glitches)
    if status == "timeout":
        return None
    start, end = ep.span()
    audio = to_16k(np.concatenate(frames[start:end]), rate)
    return (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)


def explain(info):
    """Say WHY nothing was heard, in terms of what the microphone actually delivered."""
    if info and info.get("threshold") is None and info.get("glitches"):
        return ("heard nothing: the input signal is saturated (full scale) for seconds on end. "
                "Lower the mic gain or try another --device (see: python stt_session.py meter).")
    if not info or info.get("threshold") is None:
        return "heard nothing (no audio analysed)."
    floor, thr, peak = info["floor"], info["threshold"], info["peak"]
    msg = f"heard nothing (room noise {floor:.4f}, trigger {thr:.4f}, loudest {peak:.4f}). "
    if floor > 0.02:
        msg += "The room measured as loud: did you speak right after Enter? Pause half a second first."
    elif peak < thr:
        msg += "Your voice never reached the trigger: wrong input, muted, or too quiet. Run: python stt_session.py meter"
    elif floor > 0.004 or thr > 0.8 * peak:
        msg += ("The noise estimate was inflated (noisy room, or speaking before the half-second pause): "
                "pause a full half second after Enter.")
    else:
        msg += "Too briefly or too softly."
    return msg


def record_with_hint(device):
    info = {}
    audio = record_utterance(device, info=info)
    if audio is None:
        print("  " + explain(info))
    return audio


def analyze_levels(levels, frame_s=0.05, quiet_s=2.0):
    """Meter verdict from per-frame loudness: first quiet_s seconds silent, the rest talking."""
    k = int(quiet_s / frame_s)
    quiet, talk = levels[:k], levels[k:]
    floor = statistics.median(quiet) if quiet else 0.0
    voice = sorted(talk)[int(0.9 * (len(talk) - 1))] if talk else 0.0
    thr = max(3.0 * floor, 0.012)
    verdict = "too quiet" if voice < thr else ("borderline" if voice < 2 * thr else "good")
    return {"floor": floor, "voice": voice, "threshold": thr, "verdict": verdict}


def write_wav(path, audio):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def make_client():
    env_path = Path(__file__).resolve().with_name(".env")
    key = None
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if separator and name.strip().removeprefix("export ") == "MISTRAL_API_KEY":
                key = value.strip().strip('"').strip("'")
                break

    if not key:
        sys.exit(f"Set MISTRAL_API_KEY in {env_path}.")
    try:
        from mistralai.client import Mistral  # current docs
    except ImportError:
        from mistralai import Mistral         # older SDKs
    return Mistral(api_key=key)


def transcribe_audio(client, audio, language=None):
    """Returns (text, detected_language_or_None, latency_ms)."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "utterance.wav"
        write_wav(path, audio)
        t0 = time.time()
        with open(path, "rb") as f:
            kwargs = {"model": MODEL, "file": {"content": f, "file_name": path.name}}
            if language:
                kwargs["language"] = language
            resp = client.audio.transcriptions.complete(**kwargs)
        ms = (time.time() - t0) * 1000
    return (resp.text or "").strip(), getattr(resp, "language", None), ms


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def pick_phrases(rows, n, seed=7, weights=(("fr", 0.5), ("en", 0.35), ("mixed", 0.15))):
    """Stratified sample: languages by weight, categories round-robin inside each language."""
    rng = random.Random(seed)
    picked = []
    for lang, w in weights:
        by_cat = defaultdict(list)
        for r in rows:
            if r.get("language") == lang:
                by_cat[r.get("expected_category", "")].append(r)
        for lst in by_cat.values():
            rng.shuffle(lst)
        pools, k, want = list(by_cat.values()), 0, round(n * w)
        while want > 0 and any(pools):
            pool = pools[k % len(pools)]
            if pool:
                picked.append(pool.pop())
                want -= 1
            k += 1
    rng.shuffle(picked)
    return picked


RESULT_FIELDS = ["phrase", "transcript", "language", "expected_category",
                 "wer", "latency_ms", "audio_s", "detected_language"]


def summarize(results, say=print):
    if not results:
        say("No results.")
        return
    say("\n" + "=" * 70)
    say(f"{'language':<8} {'n':>3} {'mean WER':>9} {'exact':>7} {'empty':>6} {'lat p50':>8} {'lat p90':>8}")
    groups = defaultdict(list)
    for r in results:
        groups[r["language"]].append(r)
    groups["ALL"] = results
    for lang, rs in groups.items():
        lat = sorted(r["latency_ms"] for r in rs if r["latency_ms"])
        p50 = statistics.median(lat) if lat else 0
        p90 = lat[min(len(lat) - 1, int(0.9 * len(lat)))] if lat else 0
        exact = sum(1 for r in rs if r["wer"] == 0) / len(rs)
        empty = sum(1 for r in rs if not r["transcript"])
        say(f"{lang:<8} {len(rs):>3} {statistics.mean(r['wer'] for r in rs):>9.1%} "
            f"{exact:>7.0%} {empty:>6} {p50:>7.0f}ms {p90:>7.0f}ms")
    worst = sorted(results, key=lambda r: r["wer"], reverse=True)[:5]
    say("\nWorst 5 (what you said -> what it heard):")
    for r in worst:
        if r["wer"] > 0:
            say(f"  [{r['wer']:.0%}] {r['phrase']!r} -> {r['transcript']!r}")


def _lang_for(row, mode):
    """Which language to tell Voxtral. auto = let it guess; label = use the CSV's language for en/fr rows."""
    if mode == "auto":
        return None
    if mode == "label":
        return row.get("language") if row.get("language") in ("en", "fr") else None
    return mode


def _result_row(row, text, detected, ms, dur):
    score = wer(normalize(row["phrase"]), normalize(text))
    return {"phrase": row["phrase"], "transcript": text, "language": row.get("language", ""),
            "expected_category": row.get("expected_category", ""), "wer": round(score, 4),
            "latency_ms": round(ms), "audio_s": round(dur, 2), "detected_language": detected or ""}


def _finish(results, out_path, say):
    # Same schema as the Phase 0 router test, so you can score "speech -> transcript -> router":
    #   python phase0_pipeline_test.py batch <this file>
    router_path = out_path.with_name(out_path.stem + "_for_router.csv")
    with open(router_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["phrase", "expected_category", "language"])
        for r in results:
            if r["transcript"]:
                w.writerow([r["transcript"], r["expected_category"], r["language"]])
    summarize(results, say)
    say(f"\nSaved: {out_path}  and  {router_path}")


MANIFEST_FIELDS = ["file", "phrase", "language", "expected_category"]


def _save_recording(save_dir, i, row, audio):
    name = f"{i:03d}.wav"
    write_wav(save_dir / name, audio)
    manifest = save_dir / "manifest.csv"
    entry = {"file": name, "phrase": row["phrase"], "language": row.get("language", ""),
             "expected_category": row.get("expected_category", "")}
    rows = []
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("file") != name:
                    rows.append(r)
    rows.append(entry)
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (SAMPLE_RATE, 1, 2):
            raise ValueError(f"{path}: expected 16 kHz mono 16-bit")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def run_script(rows, record_fn, transcribe_fn, out_path, input_fn=input, say=print, save_dir=None, overwrite_audio=False):
    """Prompted reading session. record_fn() -> audio|None; transcribe_fn(audio, lang) -> (text, detected, ms).
    With save_dir, every recording is kept (plus manifest.csv) so `replay` can re-run it later."""
    out_path = Path(out_path)
    new_file = not out_path.exists()
    save_dir = Path(save_dir) if save_dir else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        manifest = save_dir / "manifest.csv"
        if manifest.exists() and not overwrite_audio:
            say(f"Save folder {save_dir} already has a manifest.csv. Refusing to reuse it "
                f"(would mix sessions). Use --overwrite-audio to replace it.")
            return []
        if manifest.exists() and overwrite_audio:
            try:
                with open(manifest, newline="", encoding="utf-8") as fh:
                    for r in csv.DictReader(fh):
                        name = r.get("file")
                        if name:
                            pth = save_dir / name
                            if pth.is_file():
                                pth.unlink()
            except Exception:
                pass
            manifest.unlink(missing_ok=True)
    results = []
    with open(out_path, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=RESULT_FIELDS)
        if new_file:
            writer.writeheader()
        for i, row in enumerate(rows, 1):
            say(f"\n[{i}/{len(rows)}] Say ({row.get('language', '?')}):  {row['phrase']}")
            cmd = input_fn("  Enter = record, s = skip, q = quit > ").strip().lower()
            if cmd == "q":
                break
            if cmd == "s":
                continue
            audio = record_fn()
            if audio is None:
                text, detected, ms, dur = "", None, 0.0, 0.0  # record_with_hint already said why
            else:
                dur = len(audio) / SAMPLE_RATE
                if save_dir:
                    _save_recording(save_dir, i, row, audio)
                text, detected, ms = transcribe_fn(audio, row.get("_lang"))
            result = _result_row(row, text, detected, ms, dur)
            say(f"  heard: {text!r}   WER {result['wer']:.0%}   ({ms:.0f} ms)")
            writer.writerow(result)
            fh.flush()
            results.append(result)
    _finish(results, out_path, say)
    return results


def run_replay(audio_dir, transcribe_fn, out_path, lang_mode="auto", say=print):
    """Re-transcribe a saved session under a different setting. Same audio, so differences are real."""
    audio_dir, out_path = Path(audio_dir), Path(out_path)
    with open(audio_dir / "manifest.csv", newline="", encoding="utf-8") as f:
        seen = set()
        rows = []
        for r in csv.DictReader(f):
            if r.get("file") in seen:
                continue
            seen.add(r.get("file"))
            rows.append(r)
    results = []
    with open(out_path, "w", newline="", encoding="utf-8") as fh:  # a replay is a fresh experiment
        writer = csv.DictWriter(fh, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for k, row in enumerate(rows, 1):
            audio = read_wav(audio_dir / row["file"])
            text, detected, ms = transcribe_fn(audio, _lang_for(row, lang_mode))
            result = _result_row(row, text, detected, ms, len(audio) / SAMPLE_RATE)
            writer.writerow(result)
            results.append(result)
            say(f"[{k}/{len(rows)}] {row['phrase']!r} -> {text!r}   WER {result['wer']:.0%}")
    _finish(results, out_path, say)
    return results


def load_results(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["phrase"]: r for r in csv.DictReader(f)}  # the last entry wins if a phrase repeats


def non_latin(text):
    """True if the transcript contains letters outside Latin scripts (e.g. a Russian guess)."""
    return bool(re.search(r"[^\u0000-\u024F\u2000-\u206F\u20A0-\u20CF]", text))


def run_compare(paths, say=print, min_delta=0.2):
    """Line up several results CSVs on the phrases they share and show where they disagree."""
    for p in paths:
        if not Path(p).exists():
            say(f"File not found: {p}")
            return
    runs = [(Path(p).stem, load_results(p)) for p in paths]
    say("Files: " + ", ".join(f"{name} ({len(rows)} phrases)" for name, rows in runs))
    common = [ph for ph in runs[0][1] if all(ph in rows for _, rows in runs)]
    if not common:
        empties = [name for name, rows in runs if len(rows) == 0]
        if empties:
            say("No phrases in common. A 0-phrase file (" + ", ".join(empties) +
                ") is probably empty/leftover.")
        else:
            say("No phrases in common between these files.")
        return
    say(f"{len(common)} phrases in common across {len(runs)} files\n")
    say(f"{'file':<26} {'mean WER':>9} {'exact':>7} {'non-Latin':>10}")
    for name, rows in runs:
        w = [float(rows[p]["wer"]) for p in common]
        say(f"{name:<26} {statistics.mean(w):>9.1%} {sum(1 for x in w if x == 0):>3}/{len(w):<3} "
            f"{sum(1 for p in common if non_latin(rows[p]['transcript'])):>10}")
    say("\nPhrases where the files disagree (WER differs by 20+ points, or a wrong script appears):")
    shown = 0
    for p in common:
        ws = [float(rows[p]["wer"]) for _, rows in runs]
        bad = any(non_latin(rows[p]["transcript"]) for _, rows in runs)
        if max(ws) - min(ws) >= min_delta or bad:
            shown += 1
            say(f"- {p!r}")
            for (name, rows), w in zip(runs, ws):
                say(f"    {name:<22} {rows[p]['transcript']!r}  ({w:.0%})")
    if not shown:
        say("  (none: the files agree on every phrase)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_device(value):
    return int(value) if value and value.isdigit() else value


def cmd_devices(_):
    import sounddevice as sd
    print(sd.query_devices())


def cmd_meter(args):
    import math
    import sounddevice as sd

    device = parse_device(args.device)
    rate, ch = _open_settings(device)
    print(f"Input: {device if device is not None else 'default'}  ({rate} Hz, {ch} ch)")
    print(f"Stay SILENT for 2 s, then talk normally for {args.seconds - 2} s.\n")
    q, levels = queue.Queue(), []
    with sd.InputStream(samplerate=rate, channels=ch, dtype="float32", blocksize=int(rate * 0.05),
                        device=device, callback=lambda d, n, t, s: q.put(d.mean(axis=1).copy())):
        end = time.time() + args.seconds
        while time.time() < end:
            rms = float(np.sqrt(np.mean(q.get(timeout=3) ** 2)))
            levels.append(rms)
            fill = int(max(0.0, min(1.0, (20 * math.log10(rms + 1e-9) + 60) / 50)) * 30)
            phase = "silent" if len(levels) * 0.05 < 2 else "TALK  "
            print(f"\r  {phase} [{'#' * fill}{'.' * (30 - fill)}] {rms:.4f}", end="", flush=True)
    r = analyze_levels(levels)
    print(f"\n\nRoom noise {r['floor']:.4f}   your voice {r['voice']:.4f}   trigger level {r['threshold']:.4f}")
    if r["verdict"] == "too quiet":
        print("Verdict: TOO QUIET (or the wrong input). Try --device with another number, "
              "raise the input volume, or check the mic isn't muted.")
    elif r["verdict"] == "borderline":
        print("Verdict: BORDERLINE. It may work, but louder or closer is safer.")
    else:
        print("Verdict: GOOD. Use this device:  --device " + (str(device) if device is not None else "(default)"))


def cmd_talk(args):
    client = make_client()
    lang = None if args.lang == "auto" else args.lang
    device = parse_device(args.device)
    print("Push-to-talk. Press Enter, pause half a second, then speak. Ctrl+C to quit.")
    while True:
        input("\n[Enter] to listen... ")
        audio = record_with_hint(device)
        if audio is None:
            continue
        text, detected, ms = transcribe_audio(client, audio, lang)
        print(f"  heard: {text!r}")
        print(f"  {len(audio) / SAMPLE_RATE:.1f}s of audio, {ms:.0f} ms to transcribe"
              + (f", detected language: {detected}" if detected else ""))


def cmd_compare(args):
    run_compare(args.files)


def cmd_replay(args):
    client = make_client()
    run_replay(args.dir, lambda audio, lang: transcribe_audio(client, audio, lang), args.out, args.lang)


def cmd_script(args):
    with open(args.csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.split:
        rows = [r for r in rows if r.get("split") == args.split]
    rows = pick_phrases(rows, args.n, args.seed)
    for r in rows:
        r["_lang"] = _lang_for(r, args.lang)
    client = make_client()
    device = parse_device(args.device)
    print(f"{len(rows)} phrases. Press Enter, pause half a second, then read the phrase naturally.")
    run_script(rows, lambda: record_with_hint(device),
               lambda audio, lang: transcribe_audio(client, audio, lang), args.out,
               save_dir=args.save_audio, overwrite_audio=getattr(args, "overwrite_audio", False))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices").set_defaults(fn=cmd_devices)

    m = sub.add_parser("meter", help="live input level: find the right microphone")
    m.add_argument("--device")
    m.add_argument("--seconds", type=int, default=8)
    m.set_defaults(fn=cmd_meter)

    t = sub.add_parser("talk")
    t.add_argument("--lang", choices=["auto", "en", "fr"], default="auto")
    t.add_argument("--device")
    t.set_defaults(fn=cmd_talk)

    s = sub.add_parser("script")
    s.add_argument("--csv", default="test_phrases_large.csv")
    s.add_argument("--split", help="only rows with this split value (synthetic_dataset_raw.csv)")
    s.add_argument("--n", type=int, default=40)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--lang", choices=["auto", "en", "fr", "label"], default="auto",
                   help="auto = let Voxtral detect; label = force the CSV's language for en/fr rows")
    s.add_argument("--out", default="stt_results.csv")
    s.add_argument("--device")
    s.add_argument("--save-audio", metavar="DIR", help="keep every recording so `replay` can re-run it")
    s.add_argument("--overwrite-audio", action="store_true", help="allow reusing a save folder that already has a manifest.csv")
    s.set_defaults(fn=cmd_script)

    c = sub.add_parser("compare", help="line up several results CSVs and show where they disagree")
    c.add_argument("files", nargs="+")
    c.set_defaults(fn=cmd_compare)

    r = sub.add_parser("replay", help="re-transcribe a saved session under another language setting")
    r.add_argument("dir")
    r.add_argument("--lang", choices=["auto", "en", "fr", "label"], default="auto")
    r.add_argument("--out", default="replay.csv")
    r.set_defaults(fn=cmd_replay)

    args = p.parse_args()
    try:
        args.fn(args)
    except KeyboardInterrupt:
        print("\nBye.")


if __name__ == "__main__":
    main()