#!/usr/bin/env bash

set -eux

export $(grep -v '^#' /home/valery/config/${ENVS} | xargs)

if [ -n "${SWAP_ON+x}" ]; then 
    sudo fallocate -l 256M /swapfile && \
    sudo chmod 600 /swapfile && \
    sudo mkswap /swapfile && \
    sudo swapon /swapfile && \
    echo '/swapfile swap swap defaults 0 0' | sudo tee /etc/fstab
fi

python -u main.py "${@}"
