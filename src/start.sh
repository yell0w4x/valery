#!/usr/bin/env bash

set -eux

env $(grep -v '^#' /home/valery/config/${ENVS} | xargs) python -u main.py "${@}"
