FROM apify/actor-python:latest

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY austin_actor ./austin_actor
COPY run_local.py ./run_local.py
COPY README.md ./README.md

CMD ["python", "-m", "austin_actor"]
