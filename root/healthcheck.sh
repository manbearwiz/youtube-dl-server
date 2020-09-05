#!/bin/bash

if [[ ! -z "${YTBDL_SERVER_USER}" ]] && [[ ! -z "${YTBDL_SERVER_PASS}" ]]; then
    YTBDL_SERVER_AUTH="${YTBDL_SERVER_USER}:${YTBDL_SERVER_PASS}@"
else
    YTBDL_SERVER_AUTH=""
fi

PATH="${YTBDL_SERVER_ROOT:-/youtube-dl}"
PATH="${PATH%/}"       # remove trailing slash
PATH="/${PATH#/}"       # remove leading slash

HEALTHCHECK_URL="http://${YTBDL_SERVER_AUTH}127.0.0.1:${YTBDL_SERVER_PORT:-8080}${PATH}/q"

/usr/bin/curl --silent --fail ${HEALTHCHECK_URL} || exit 1
