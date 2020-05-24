
build:
	docker build --rm --force-rm -t jupyterlab-rtc:latest ./

run:
	docker run --rm -p 8888:8888 -e JUPYTER_ENABLE_LAB=yes --name jupyterlab-rtc jupyterlab-rtc:latest

bash:
	docker exec -it jupyterlab-rtc /bin/bash

kill:
	docker kill jupyterlab-rtc
