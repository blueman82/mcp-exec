#!/usr/bin/env bash
# Simple script to deploy status-updater to prod2 only

VERSION="${1:-latest}"
PROD2="ketchup-prod2.campaign.adobe.com"

echo "Deploying status-updater $VERSION to prod2 only..."
ssh "$PROD2" "cd /opt/ketchup && \
  sudo sed -i 's|ketchup-status-updater:v[0-9.]*|ketchup-status-updater:${VERSION}|g' docker-compose.yml && \
  aws ecr get-login-password --region eu-west-1 | sudo docker login --username AWS --password-stdin 483013340174.dkr.ecr.eu-west-1.amazonaws.com && \
  sudo docker-compose pull ketchup-status-updater && \
  sudo docker-compose up -d --force-recreate ketchup-status-updater"
echo "Done"