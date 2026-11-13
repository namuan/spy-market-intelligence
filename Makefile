UV ?= uv

.PHONY: help install app update report scheduler test

help:
	@printf '%s\n' \
	  'install    Sync project dependencies and test tools' \
	  'app        Start the Streamlit dashboard' \
	  'update     Fetch market data and run a forecast' \
	  'report     Generate the daily HTML report' \
	  'scheduler  Start the weekday update scheduler' \
	  'test       Run the test suite'

install:
	$(UV) sync --extra test

app:
	$(UV) run streamlit run app.py

update:
	$(UV) run python -m src.pipeline

report:
	$(UV) run python -m src.daily_report

scheduler:
	$(UV) run python -m src.scheduler

test:
	$(UV) run pytest
