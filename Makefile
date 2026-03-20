
install:
	uv venv --python 3.12
	source .venv/bin/activate
	uv sync

start:
	./start_server.sh