"""NestClockOS health check (run offline)."""
import os, shutil, sys
from pathlib import Path

checks = []

def check(name, ok, detail=""):
    checks.append((name, ok, detail))
    print(f"{'OK ' if ok else 'FAIL'} {name}: {detail}".strip())

def main():
    base = Path(__file__).resolve().parent
    load_ok = False
    try:
        import companion
        load_ok = True
    except Exception as e:
        check("companion imports", False, str(e))
    if load_ok:
        check("companion imports", True, "ok")

    env = base / ".env"
    check(".env exists", env.is_file(), str(env))
    if env.is_file():
        key = ""
        for line in env.read_text().splitlines():
            if line.startswith("MISTRAL_API_KEY="):
                key = line.split("=", 1)[-1].strip().strip('"').strip("'")
        check("MISTRAL_API_KEY set", bool(key), "present" if key else "missing")

    companion_state = base / "companion_state.json"
    check("state file", companion_state.exists() or True, "optional")

    # Router model resolution
    import os as _os
    rd = _os.environ.get("NESTCLOCK_ROUTER_DIR")
    if rd:
        check("router dir", Path(rd).is_dir(), rd)
    else:
        check("router dir", False, "NESTCLOCK_ROUTER_DIR unset (routing disabled)")

    # audio tool availability
    for tool in ("aplay", "mpv", "systemd-inhibit", "xset"):
        check(f"tool: {tool}", shutil.which(tool) is not None)

    # whisper: NTP/timezone
    from datetime import datetime, timezone
    check("TZ", os.environ.get("TZ", "unset") in ("Europe/Paris", "unset"), os.environ.get("TZ", "unset"))

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} passed")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
