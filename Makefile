.PHONY: test run doctor
test:
	.venv/bin/python run_tests.py

run:
	.venv/bin/python companion.py

doctor:
	.venv/bin/python doctor.py
