FROM python:3.11-bullseye

RUN apt-get update -y
RUN apt-get install -y iproute2 htop
RUN cd /tmp && wget https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb
RUN apt-get install /tmp/dumb-init_1.2.5_amd64.deb

WORKDIR /app
COPY src/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY src /app/
COPY config /config/

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "-u", "/app/main.py", "--log-level", "DEBUG"]
