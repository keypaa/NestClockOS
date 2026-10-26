"""Run the project's lightweight Python tests (no third-party test runner)."""
import os, sys
root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, root)

import tests.test_voice as tv
import tests.test_companion as tc

for fn in (tv.test_endpointer_basic, tv.test_ring_buffer_wrap, tv.test_slots, tv.test_text):
    fn()
    print(f"OK {fn.__name__}")

tc.test_set_alarm_and_state()
tc.test_invalid_json_does_not_crash()
tc.test_mic_mute_toggle()
tc.test_unknown_action_safe()
print("OK companion handler tests")
print("All tests passed.")
