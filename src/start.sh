#!/usr/bin/env bash

set -eux

export $(grep -v '^#' /home/valery/config/${ENVS} | xargs)

if [ -n "${SWAP_ON+x}" ]; then 
    SWAP_FN=/.fly-upper-layer/swapfile

    sudo fallocate -l 256M "${SWAP_FN}" && \
    sudo chmod 600 "${SWAP_FN}" && \
    sudo mkswap "${SWAP_FN}" && \
    sudo swapon "${SWAP_FN}"
    # echo "${SWAP_FN} swap swap defaults 0 0" | sudo tee /etc/fstab
fi

python -u main.py "${@}"
