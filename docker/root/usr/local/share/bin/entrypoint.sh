#!/bin/sh
while true ; do
    python -u /app/stream-stats.py
    sleep 60
done
