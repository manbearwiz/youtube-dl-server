.PHONY=venv
venv:
	test -d .venv || python3 -m venv .venv
	. .venv/bin/activate

requirements:
	pip install -r requirements.txt

build:
	docker build . --tag youtube-dl-server:develop

run:
	docker run -v /tmp/youtube-dl:/youtube-dl -p 8080:8080 youtube-dl-server:develop
