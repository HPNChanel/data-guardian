FROM python:3.11-slim

WORKDIR /app
COPY ./data_guardian/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ./data_guardian/src /app/src
ENV PYTHONPATH=/app/src

EXPOSE 8000
CMD ["uvicorn", "data_guardian.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

