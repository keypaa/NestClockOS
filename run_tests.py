"""Run the project's lightweight Python tests with the installed venv."""
import tests.test_voice as t

tests = [t.test_endpointer_basic, t.test_ring_buffer_wrap, t.test_slots, t.test_text]
for fn in tests:
    fn()
    print(f"OK {fn.__name__}")
print("All tests passed.")
