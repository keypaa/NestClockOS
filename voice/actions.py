"""Execute a parsed voice intent against the companion Store."""
import time
import uuid


def try_execute(store, category, text, slots):
    if category == "alarm" and slots and slots.get("hour") is not None:
        a = {
            "id": str(uuid.uuid4()),
            "hour": slots["hour"],
            "minute": slots["minute"],
            "days": [],
            "label": text,
            "enabled": True,
            "once": bool(slots.get("once")),
            "date": slots.get("date"),
        }
        store.alarms.append(a)
        store.save()
        return True, f"alarm set {a['hour']:02d}:{a['minute']:02d}"
    if category == "timer" and slots and slots.get("seconds"):
        t = {
            "id": str(uuid.uuid4()),
            "duration": slots["seconds"],
            "ends_at": time.time() + slots["seconds"],
            "label": text,
        }
        store.timers.append(t)
        store.save()
        return True, f"timer set {slots['seconds']}s"
    if category == "fallback":
        low = text.lower()
        if any(w in low for w in ("heure", "time", "quelle heure")):
            import datetime
            return True, "time: " + datetime.datetime.now().strftime("%H:%M")
        if any(w in low for w in ("date", "jour", "day")):
            import datetime
            return True, "date: " + datetime.date.today().isoformat()
    return False, None
