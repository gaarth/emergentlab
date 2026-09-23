PY ?= python

.PHONY: test test-py test-viewer serve run paper fixtures

test: test-py test-viewer

test-py:
	$(PY) -m pytest -q

test-viewer:
	npx playwright test

serve:
	$(PY) -m http.server 8000

fixtures:
	$(PY) fixtures/make_big.py

run:
	$(PY) lab.py --question "Find a Life-like CA rule (B../S..) and a seed of at most 5x5 cells under which the seed self-replicates: after N steps the grid contains 2 or more disjoint copies of the seed." --minutes 60

paper:
	$(PY) render_paper.py
