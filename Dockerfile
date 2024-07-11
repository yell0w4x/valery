ARG BASE=python:3.11-bookworm
FROM "${BASE}"

RUN apt-get update -y
RUN apt-get install -y iproute2 htop ffmpeg nodejs npm sudo
RUN cd /tmp && wget https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb
RUN apt-get install /tmp/dumb-init_1.2.5_amd64.deb

RUN groupadd -r valery && \
    useradd --uid 1000 -m -r -g valery -G audio,video,users,sudo -m valery

RUN echo 'valery ALL = (root) NOPASSWD: /usr/bin/fallocate -l 256M /.fly-upper-layer/swapfile,/usr/bin/chmod 600 /.fly-upper-layer/swapfile,/usr/sbin/mkswap /.fly-upper-layer/swapfile,/usr/sbin/swapon /.fly-upper-layer/swapfile,/usr/bin/tee /etc/fstab' > /etc/sudoers.d/valery

USER valery

WORKDIR /home/valery/app
COPY --chown=valery:valery src/requirements.txt /home/valery/app/requirements.txt
RUN pip install -r requirements.txt
COPY --chown=valery:valery src /home/valery/app/
RUN cd /home/valery/app/tokenizer && \
    npm install llama-tokenizer-js@1.1.3 && \
    npm install llama3-tokenizer-js@1.1.3 && \
    node main.mjs --run-tests
COPY --chown=valery:valery config /home/valery/config/
ARG ENVS=test.env
ENV ENVS=${ENVS}

ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/home/valery/app/start.sh", "--log-level", "DEBUG", "--deps-log-level", "WARNING"]
