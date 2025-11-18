FROM python:3.11-slim

# Install required system packages
RUN apt-get update && apt-get install -y build-essential curl git && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Set PYTHONPATH to ensure Python can find the packages
ENV PYTHONPATH="/app"

# Copy application packages
COPY ./packages ./packages

# Copy the test script
COPY tests/setup/test_con.py ./test_con.py

# Install Python dependencies
# Added aiobotocore and boto3, common for AWS interactions
RUN pip install --no-cache-dir aiohttp tabulate tiktoken aiobotocore boto3 aioboto3

# Ensure results directory exists
RUN mkdir -p /app/results

# To run this Docker image successfully with AWS integration,
# you need to provide AWS credentials to the container.
# One common way for local development is to volume mount your ~/.aws directory:
# docker run --rm -v ~/.aws:/root/.aws -v "$(pwd):/app" your_image_name
# For CI/CD, use your CI system's secure mechanisms to provide credentials
# as environment variables (e.g., AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN).

# Run script
CMD ["python", "test_con.py"]
