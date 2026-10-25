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
    if category == "music" and slots:
        return True, "music: " + (slots.get("subintent") or "play") + " (Spotify API pending)"
    if category == "weather" and slots:
        return True, "weather: " + slots.get("when", "today") + " / " + slots.get("kind", "general") + " (forecast API pending)"
    if category == "fallback":
        low = text.lower()
        if any(w in low for w in ("heure", "time", "quelle heure")):
            import datetime
            return True, "time: " + datetime.datetime.now().strftime("%H:%M")
        if any(w in low for w in ("date", "jour", "day")):
            import datetime
            return True, "date: " + datetime.date.today().isoformat()
    return False, None


def is_destructive(category, text):
    low = text.lower()
    if category in ("alarm", "timer"):
        return any(w in low for w in ("annule", "cancel", "delete", "supprime", "remove", "efface"))
    return False


def cancel(store, category, text):
    from .slots import parse_alarm_time
    if category == "alarm":
        time_val = parse_alarm_time(text)
        if time_val:
            h, m = time_val
            before = len(store.alarms)
            store.alarms = [a for a in store.alarms if not (a.get("hour") == h and a.get("minute") == m)]
            removed = before - len(store.alarms)
        else:
            if store.alarms:
                store.alarms.pop()
                removed = 1
            else:
                removed = 0
        if removed:
            store.save()
            return True, f"cancelled {removed} alarm(s)"
        return False, "no matching alarm"
    if category == "timer":
        if store.timers:
            store.timers.pop() if not ("tous" in text.lower() or "all" in text.lower()) else store.timers.clear()
            store.save()
            return True, "timer cancelled"
        return False, "no timer"
    return False, None
