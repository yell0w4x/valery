FROM python:3.11-bookworm

RUN apt-get update -y
RUN apt-get install -y iproute2 htop ffmpeg nodejs npm
RUN cd /tmp && wget https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb
RUN apt-get install /tmp/dumb-init_1.2.5_amd64.deb

WORKDIR /app
COPY src/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt
COPY src /app/
RUN cd /app/tokenizer && npm install llama-tokenizer-js && node main.mjs --run-tests
# RUN pytest
COPY config /config/

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "-u", "/app/main.py", "--log-level", "DEBUG", "--deps-log-level", "WARNING"]
