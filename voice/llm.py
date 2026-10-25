"""Mistral chat fallback: short spoken-style replies, no tools."""
import datetime, os

SYSTEM = ("You are NestClock, a voice assistant for a home clock. Answer in one or two short sentences. "
          "No markdown, no lists. Match the user's language (French or English). If you do not know, say so briefly.")


def ask(client, text, reply_language="fr"):
    now = datetime.datetime.now().astimezone()
    user = f"Current date/time: {now.isoformat()} (timezone {now.tzname()}). User said: {text}"
    try:
        r = client.chat.complete(model=os.environ.get("NESTCLOCK_LLM_MODEL", "mistral-small-latest"),
                                 messages=[{"role": "system", "content": SYSTEM},
                                           {"role": "user", "content": user}],
                                 max_tokens=120)
        return r.choices[0].message.content.strip()
    except Exception as e:
        return f"(LLM unavailable: {e})"
