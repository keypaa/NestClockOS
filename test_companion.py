"""
NestClockOS — Phase 2: companion service smoke test.

Connects to the running companion.py, prints the initial state, starts a
5-second timer, and prints every event until you Ctrl+C. Run this before
touching the browser at all — it should beep once the timer ends and print
a timer_fired message.

Setup:
    pip install websockets

Run (with companion.py already running in another terminal):
    python test_companion.py
"""

import asyncio
import json

import websockets

PORT = 8765


async def main():
    uri = f"ws://localhost:{PORT}"
    async with websockets.connect(uri) as ws:
        print(f"Connected to {uri}")

        initial = json.loads(await ws.recv())
        print("Initial state:", initial)

        print("Starting a 5-second test timer...")
        await ws.send(json.dumps({
            "action": "start_timer",
            "seconds": 5,
            "label": "smoke test",
        }))

        print("Listening for events (Ctrl+C to stop)...")
        async for raw in ws:
            print("Event:", json.loads(raw))


if __name__ == "__main__":
    asyncio.run(main())
