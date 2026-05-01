FROM webcube-dualllm-base:v1

MAINTAINER Yash Indane

EXPOSE 85

RUN mkdir /webcube

COPY . /webcube

WORKDIR /webcube

ENTRYPOINT python3 app.py
