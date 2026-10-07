FROM apify/actor-python:latest

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY greenhouse_actor ./greenhouse_actor
COPY scripts ./scripts
COPY README.md ./README.md

CMD ["python", "-m", "greenhouse_actor"]
