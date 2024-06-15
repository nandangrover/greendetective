ARG TARGET_ENV=prd

FROM python:3.10 as builder

ENV TZ Europe/London
ENV WORKDIR /var/www/green-detective
ENV BOOTSTRAP_DIR /var/www/bootstrap

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_ARGS ""

WORKDIR ${WORKDIR}
ADD ./src ${WORKDIR}
ADD ./bootstrap ${BOOTSTRAP_DIR}

# Install python dependencies
RUN rm -rf ~/.cache/pip && \
    pip install -r requirements.txt --no-cache-dir

# Install essential packages
RUN apt-get update && \
    apt-get install -y vim && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

FROM builder as builder-dev
ENV APP_USER root
ENV TARGET_ENV dev
ENV GUNICORN_ARGS "--reload"

# Test Coverage
RUN apt-get update && \
    apt-get install -y python3-coverage && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Docker
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg  && \
    chmod a+r /etc/apt/keyrings/docker.gpg  && \
    echo \
    "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
    "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null  && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Docker compose
ARG DOCKER_COMPOSE_VERSION=2.24.2 
RUN apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin && \
    curl -SL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose && \ 
    chmod +x /usr/local/bin/docker-compose && \ 
    ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose && \ 
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Set ownership to app user (root)
RUN chown -R ${APP_USER}:${APP_USER} ${WORKDIR} && \
    chown -R ${APP_USER}:${APP_USER} ${BOOTSTRAP_DIR}

FROM builder as builder-prd
ENV APP_USER www-data
# ENV APP_USER root
ENV TARGET_ENV prd

RUN chown -R ${APP_USER}:${APP_USER} ${WORKDIR} && \
    chown -R ${APP_USER}:${APP_USER} ${BOOTSTRAP_DIR}


FROM builder-${TARGET_ENV} as service-api
EXPOSE 8070
USER ${APP_USER}
RUN chmod +x ${BOOTSTRAP_DIR}/service/service-api/startup.sh

ENTRYPOINT ${BOOTSTRAP_DIR}/service/service-api/startup.sh

FROM builder-${TARGET_ENV} as service-process
# Image configs
USER ${APP_USER}

CMD ${BOOTSTRAP_DIR}/service/service-process/startup.sh

FROM builder-${TARGET_ENV} as task-process
# Image configs
USER ${APP_USER}

ENTRYPOINT ["python", "manage.py"]
