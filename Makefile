PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
SCENARIO ?= scenarios/public_01_dev.yaml
NAME ?= $(basename $(notdir $(SCENARIO)))

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements.txt

baseline:
	$(PYTHON) -m sim baseline --scenario $(SCENARIO) --run-dir runs/base_$(NAME)
serve:
	$(PYTHON) -m sim serve --scenario $(SCENARIO) --run-dir runs/mine_$(NAME) --force
grade:
	mkdir -p reports && $(PYTHON) -m sim grade --run runs/mine_$(NAME) --baseline runs/base_$(NAME) --out reports/$(NAME).md
test:
	$(PYTHON) -m pytest -q tests
