#!/bin/bash

# pip install gunicorn
# source ./.venv/bin/activate --if you use .venv

gunicorn app.app:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:80\
    --workers 2 \
    --log-level error \