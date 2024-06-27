# syntax=docker/dockerfile:1
FROM python:3.12.4-slim-bookworm
RUN apt update -y && apt upgrade -y
RUN apt install -y git
RUN python -m pip install -e git+https://github.com/aidaco/www-min#egg=wwwmin
EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/wwwmin"]
