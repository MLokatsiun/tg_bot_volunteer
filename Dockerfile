FROM python:3.12

WORKDIR /src

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY ./requirements.txt .

RUN pip install --upgrade -r requirements.txt

COPY . .
