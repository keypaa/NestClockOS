import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio, json
import companion


class FakeWS:
    def __init__(self, msgs):
        self._msgs = list(msgs)
        self.sent = []

    async def send(self, data):
        self.sent.append(json.loads(data))

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._msgs:
            raise StopAsyncIteration
        return self._msgs.pop(0)


def get_type(ws, t):
    return [m for m in ws.sent if m.get("type") == t]


def run(coro):
    return asyncio.run(coro)


def test_set_alarm_and_state():
    async def main():
        companion.store.alarms.clear()
        companion.store.save()
        ws = FakeWS([json.dumps({"action": "set_alarm", "hour": 7, "minute": 0, "days": [1, 2]})])
        await companion.handle_client(ws)
        states = get_type(ws, "state")
        assert states and len(states[-1]["alarms"]) == 1
        assert states[-1]["alarms"][0]["hour"] == 7
    run(main())


def test_invalid_json_does_not_crash():
    async def main():
        ws = FakeWS(["{not json", json.dumps({"action": "ping"})])
        await companion.handle_client(ws)
        # should have sent an error or state; either way no exception
        assert isinstance(ws.sent, list)
    run(main())


def test_mic_mute_toggle():
    async def main():
        ws = FakeWS([json.dumps({"action": "mic_mute", "muted": True})])
        await companion.handle_client(ws)
        ms = get_type(ws, "mic_status")
        assert ms and ms[-1]["muted"] is True
    run(main())


def test_unknown_action_safe():
    async def main():
        ws = FakeWS([json.dumps({"action": "nonexistent_thing"})])
        await companion.handle_client(ws)  # no exception
    run(main())


if __name__ == "__main__":
    test_set_alarm_and_state()
    test_invalid_json_does_not_crash()
    test_mic_mute_toggle()
    test_unknown_action_safe()
    print("companion handler tests ok")

