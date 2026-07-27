# D-Eye REMOTE MCP service (Streamable HTTP + enforced bearer auth).
# For LOCAL stdio use (Claude Desktop / Code) you do NOT need Docker -- just
# `pip install deye` and register `python3 -m deye.mcp_server`.
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY deye ./deye
RUN pip install --no-cache-dir -e '.[remote]'
RUN useradd -m deye && chown -R deye /app
USER deye
ENV DEYE_HOME=/home/deye/.deye
EXPOSE 8080
# Refuses to start unless DEYE_HTTP_TOKEN (>=16 chars) is provided at runtime.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')" || exit 1
CMD ["python", "-m", "deye.cli", "serve-http", "--host", "0.0.0.0", "--port", "8080"]
