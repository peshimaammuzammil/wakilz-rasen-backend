# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# System deps for aiortc (WebRTC) + PyAV (audio codecs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libopus-dev \
    libvpx-dev \
    libsrtp2-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# Only runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 \
    libvpx7 \
    libsrtp2-1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application source
COPY server/ ./server/

# Cloud Run expects PORT env var
ENV PORT=8080
EXPOSE 8080

# Non-root user for security
RUN useradd -m -u 1000 wakilz
USER wakilz

# Start the server
CMD ["python", "-m", "server.core.main"]
