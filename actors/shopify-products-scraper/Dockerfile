FROM apify/actor-python:latest

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY shopify_actor ./shopify_actor
COPY README.md ./README.md

CMD ["python", "-m", "shopify_actor"]
