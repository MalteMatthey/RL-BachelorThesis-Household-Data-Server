# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# copy entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port 8021
EXPOSE 8021

# Set the entrypoint script (create CDS API configuration file)
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Run the FastAPI app with Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8021"]
