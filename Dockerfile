# Untested image: written for 64-bit Raspberry Pi OS / any aarch64 or x86_64 host.
# Models are mounted, not baked in:  -v $PWD/models:/app/models
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 9108
# The status server is unauthenticated: it listens on all interfaces inside
# the container, so publish the port deliberately (-p 127.0.0.1:9108:9108).
ENTRYPOINT ["python", "run.py", "--headless", "--skip-setup", "--supervised"]
CMD ["--serve", "9108", "--serve-host", "0.0.0.0"]
