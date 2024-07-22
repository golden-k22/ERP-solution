# pull official base image
FROM python:3.9-slim-buster

# create the appropriate directories
ENV APP_HOME=/home/old-erp/web
RUN mkdir -p $APP_HOME
RUN mkdir $APP_HOME/staticfiles
WORKDIR $APP_HOME

# install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    netcat \
    libmariadb3 \
    libmariadb-dev \
    gcc \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# copy and install dependencies from wheels
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# copy project
COPY . $APP_HOME

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Copy Gunicorn config
COPY gunicorn.conf.py /home/old-erp/web/gunicorn.conf.py

CMD ["gunicorn", "-c", "gunicorn.conf.py", "erpSolution.wsgi:application"]

