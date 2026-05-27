FROM python:3.12-slim

WORKDIR /app

# Install system deps for matrix-nio
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Install Node.js and opencode
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g opencode-ai \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ src/

# Clone obsidian-second-brain at build time (pinned)
RUN git clone --depth 1 https://github.com/eugeniughelbur/obsidian-second-brain.git \
    /opt/obsidian-second-brain
ENV WEAT_OSB_PATH=/opt/obsidian-second-brain

EXPOSE 8080

CMD ["uv", "run", "weat-bridge"]
