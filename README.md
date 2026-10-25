# NestClockOS

Single-file kiosk UI + Python companion. See `NESTCLOCKOS-HANDOFF.md` for architecture and roadmap.

## Setup (order matters)

1. Python 3.13 venv:
   ```sh
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
   Torch is CPU-only; if `pip` tries to pull GPU wheels, use the PyTorch CPU index:
   `pip install torch==2.14.0+cpu --index-url https://download.pytorch.org/whl/cpu`
2. Fill in `MISTRAL_API_KEY` in `.env` (see `.env.example`).
3. Optionally download the fine-tuned router checkpoint (see `phase0_5/COLAB_RUNBOOK.md`); set `NESTCLOCK_ROUTER_DIR` to its folder.
4. Start:
   ```sh
   .venv/bin/python companion.py          # ws://localhost:8765
   .venv/bin/python -m http.server 8000  # serves index.html
   ```

## Check
```sh
.venv/bin/python run_tests.py
python3 - <<'PY'
import re; open('index.html').read()  # placeholder: see check below
PY
node --check /tmp/page.js  # after extracting <script>
```
