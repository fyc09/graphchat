.PHONY: py-install py-wheel web-install web-build web-dev dev run build clean

NPM := npm.cmd

py-install:
	python -m pip install -e .

web-install:
	$(NPM) --prefix graphchat/web install

web-build:
	$(NPM) --prefix graphchat/web run build

web-dev:
	$(NPM) --prefix graphchat/web run dev

py-wheel:
	python -m pip install build
	python -m build --wheel

build: py-install web-install web-build py-wheel

run:
	python -m graphchat.main

dev:
	python -m uvicorn graphchat.main:app --reload --host 127.0.0.1 --port 8000

clean:
	rm -rf build dist graphchat.egg-info graphchat/static graphchat/data
