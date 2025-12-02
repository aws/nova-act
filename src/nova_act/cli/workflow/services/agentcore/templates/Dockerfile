FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install custom wheel files first
# COPY wheels/ ./wheels/
# RUN pip install --no-cache-dir wheels/*.whl

# Copy requirements and install remaining Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose AgentCore standard port
EXPOSE 8080

# Set environment variables
ENV PYTHONPATH=/app
ENV AWS_DEFAULT_REGION=us-east-1
ENV ENTRY_POINT={{entry_point}}

# Start the application
CMD ["python", "-m", "agentcore_handler"]
