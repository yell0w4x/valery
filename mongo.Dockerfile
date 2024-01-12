FROM mongo:latest

RUN groupadd -r --gid 1000 mongo && \
    useradd -r --uid 1000 -g mongo -G audio,video,users -m mongo

RUN chown -R mongo:mongo /data/db

USER mongo:mongo
