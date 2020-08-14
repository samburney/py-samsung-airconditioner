FROM library/python:3.7-stretch

LABEL maintainer "sburney@sifnt.net.au"

WORKDIR /app

RUN pip install -U pip \
    && pip install \
    asyncio untangle
