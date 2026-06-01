@echo off
REM Windows doesn't natively support gunicorn, so we run uvicorn with the --workers flag directly.
REM The number of workers is picked up from the API_WORKERS environment variable if set,
REM or defaults to (cores * 2 + 1) in config.py, which uvicorn respects when run via main.py.

echo Starting PRISM Backend in Production Mode (Multiple Workers)
python main.py
