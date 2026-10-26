.PHONY: test run doctor
test:
	.venv/bin/python run_tests.py

run:
	set -a; [ -f .env ] && . ./.env; set +a; PYTHONUNBUFFERED=1 .venv/bin/python -u companion.py

doctor:
	.venv/bin/python doctor.py
