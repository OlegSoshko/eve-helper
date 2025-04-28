FROM python:3.9-slim

WORKDIR /app

COPY ./config/requirements/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src .

EXPOSE 8000

CMD ["python", "./main.py"]