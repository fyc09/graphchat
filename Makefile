.PHONY: py-install web-install web-build web-dev dev run build clean

NPM := npm.cmd

py-install:
	python -m pip install -e .

web-install:
	$(NPM) --prefix graphchat/web install

web-build:
	$(NPM) --prefix graphchat/web run build

web-dev:
	$(NPM) --prefix graphchat/web run dev

build: py-install web-install web-build

run:
	python -m graphchat.main

dev:
	python -m uvicorn graphchat.main:app --reload --host 127.0.0.1 --port 8000

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['build', 'dist', 'graphchat.egg-info', 'graphchat/static', 'graphchat/data']]"
