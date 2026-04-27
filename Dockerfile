FROM yashindane/webcube:v1

MAINTAINER Yash Indane

EXPOSE 85

COPY . /webcube

WORKDIR /webcube

ENTRYPOINT python3 app.py
