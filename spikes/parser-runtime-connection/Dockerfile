ARG WORKER_IMAGE=document-platform-api:dev
FROM ${WORKER_IMAGE}

COPY --chown=10001:10001 dependencies/ /opt/parser-probe/dependencies/
COPY --chown=10001:10001 connection_probe.py container_probe.py /opt/parser-probe/
ENV PYTHONPATH=/opt/parser-probe/dependencies:/opt/parser-probe
USER 10001:10001
WORKDIR /opt/parser-probe
ENTRYPOINT ["python", "/opt/parser-probe/container_probe.py"]
CMD []
