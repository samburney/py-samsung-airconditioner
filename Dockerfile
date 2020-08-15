FROM library/python:3.7-stretch

LABEL maintainer "sburney@sifnt.net.au"

WORKDIR /app

ENV PIP_PACKAGES "asyncio xmltodict argparse"
ENV PIP_PACKAGES_DEV "flake8"

RUN pip install -U pip \
    && pip install \
    ${PIP_PACKAGES} \
    ${PIP_PACKAGES_DEV}
