FROM library/python:3.7-stretch

LABEL maintainer "sburney@sifnt.net.au"

ENV PIP_PACKAGES "asyncio xmltodict argparse influxdb"

RUN pip install -U pip \
    && pip install \
    ${PIP_PACKAGES} \
    && git clone https://github.com/samburney/py-samsung-airconditioner.git /app

WORKDIR /app

ADD /docker/root /

ENTRYPOINT [ "sh", "-c", "/usr/local/share/bin/entrypoint.sh" ]