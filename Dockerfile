ARG BASE=python:3.11-bookworm
FROM "${BASE}"

RUN apt-get update -y
RUN apt-get install -y iproute2 htop ffmpeg nodejs npm
RUN cd /tmp && wget https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb
RUN apt-get install /tmp/dumb-init_1.2.5_amd64.deb

RUN groupadd -r valery && \
    useradd --uid 1000 -m -r -g valery -G audio,video,users -m valery

USER valery

WORKDIR /home/valery/app
COPY --chown=valery:valery src/requirements.txt /home/valery/app/requirements.txt
RUN pip install -r requirements.txt
COPY --chown=valery:valery src /home/valery/app/
RUN cd /home/valery/app/tokenizer && npm install llama-tokenizer-js && node main.mjs --run-tests
# RUN pytest
COPY --chown=valery:valery config /home/valery/config/

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["python", "-u", "/home/valery/app/main.py", "--log-level", "DEBUG", "--deps-log-level", "WARNING"]
