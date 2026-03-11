#!/bin/bash
# Healthcheck for ChromaDB service
# Verifies the vector database is responsive and ready to accept requests

set -e

# ChromaDB heartbeat endpoint confirms service availability
curl -sf http://localhost:8000/api/v1/heartbeat > /dev/null 2>&1

exit $?
