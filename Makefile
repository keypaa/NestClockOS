.PHONY: test run doctor
test:
	.venv/bin/python run_tests.py

run:
	set -a; [ -f .env ] && . ./.env; set +a; .venv/bin/python companion.py

doctor:
	.venv/bin/python doctor.py
