# Use a lightweight official Python image
FROM python:3.13-slim

# Create directory for app
WORKDIR /app

# Install system deps if you ever need them (can leave commented for now)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential && \
#     rm -rf /var/lib/apt/lists/*

# Copy only requirements first (better cache)
COPY requirements.txt .

# Install Python dependencies (this includes earthshaker)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your project
COPY . .

# Expose the AgentBeats controller port
EXPOSE 8010

# IMPORTANT:
# Cloud Run sets $PORT. We MUST listen on that port,
# even if we conceptually think "8010".
#
# We use a tiny shell wrapper so that agentbeats uses $PORT.

CMD ["agentbeats", "run_ctrl"]
