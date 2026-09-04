FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY cr_extractor ./cr_extractor
COPY tests ./tests

ENTRYPOINT ["python", "-m", "cr_extractor.cli"]
