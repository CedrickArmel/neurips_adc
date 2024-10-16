ARG BASE_VERSION=20.04
ARG PYTHONVERSION=3.10.13
ARG DEVICE=gpu

FROM drxc/python:${PYTHONVERSION}-ubuntu${BASE_VERSION}-${DEVICE}

ARG PYTHONVERSION=3.10.13

LABEL Author="https://github.com/CedrickArmel"

COPY --from=apache/beam_python3.10_sdk@sha256:489a76e821e38c043eeb8237c76b45c215d864fe81b4141bb541a3642bf3d086 \
    /opt/apache/beam /opt/apache/beam

COPY . ${HOME}/app
WORKDIR ${HOME}/app
RUN set -eux ; \
    \
    source ${HOME}/.bashrc ; \
    pyenv virtualenv ${PYTHONVERSION} myenv ; \
    pyenv activate myenv ; \
    poetry install --without dev ; \
    pyenv global myenv ;

WORKDIR ${HOME}/app

ENV PYTHONPATH=/

ENTRYPOINT [ "/bin/bash" ]
