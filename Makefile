PY ?= python

.PHONY: test test-py test-ui build dev serve run mock paper fixtures demo-check install

install:            ## python deps + root playwright + app deps
	pip install anthropic numpy scipy pillow markdown pytest
	npm install && npx playwright install chromium
	cd app && npm install

test: test-py test-ui

test-py:
	$(PY) -m pytest -q

test-ui: build      ## Playwright against the production build served by server.py
	npx playwright test

build:              ## app/dist, served by server.py at /app/dist/
	cd app && npm run build

dev:                ## hot-reloading UI on http://localhost:5173 (needs `make serve` in another terminal)
	cd app && npm run dev

serve:              ## static files + /api/start,/api/stop on http://localhost:8000
	$(PY) server.py

run:                ## real lab (needs ANTHROPIC_API_KEY in .env)
	$(PY) lab.py --question "Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed." --minutes 60

mock:               ## fake lab, no API
	$(PY) mock_lab.py --nodes 60 --interval 4

paper:
	$(PY) render_paper.py

fixtures:
	$(PY) fixtures/make_big.py

demo-check:
	$(PY) demo_check.py
