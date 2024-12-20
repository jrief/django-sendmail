FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install pip --upgrade
COPY . /app

RUN pip install -r /app/demoapp/tests/requirements/test_requirements.txt

WORKDIR /app

CMD ["python", "-m", "celery", "-A", "demoapp", "worker", "-l", "info", "--concurrency=5"]
