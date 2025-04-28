stop:
	docker stop plex-monitor || true
	docker rm plex-monitor || true

start:
	docker build -t eve-plex-api .
	docker run -d -p 8000:8000 --name plex-monitor --dns 8.8.8.8 --env-file .env eve-plex-api

restart:
	make stop
	make start
