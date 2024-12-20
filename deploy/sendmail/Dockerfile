FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install pip --upgrade

# Install necessary dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /app
COPY ./deploy/sendmail/uwsgi.ini /etc/uwsgi.ini

WORKDIR /app/demoapp

RUN pip install -r /app/demoapp/tests/requirements/test_requirements.txt
RUN pip install uWSGI

RUN python manage.py makemigrations --no-input
RUN python manage.py migrate --no-input
RUN python manage.py collectstatic --no-input

ENV DJANGO_STATIC_ROOT=/app/staticfiles
ENV DJANGO_MEDIA_ROOT=/app/workdir/media

# Create non-root user
RUN useradd -m -d /app -s /bin/bash django
RUN chown -R django:django /app

EXPOSE 8080

WORKDIR /app

CMD ["uwsgi", "--ini", "/etc/uwsgi.ini"]
