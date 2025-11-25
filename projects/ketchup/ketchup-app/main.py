"""
main.py - Webhook + API service

This file is the main entry point for the Ketchup application.
It handles both webhook reception and API processing.

It is responsible for:
- Receiving and processing Slack webhooks
- Processing Slack slash commands
- Processing Slack interactive components
- Handling health checks
- Providing metrics for monitoring

"""

from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
import hmac
import hashlib
import time
import json
import os
import base64
from typing import Dict, Any, Optional
from contextlib import asynccontextmanager
import aioboto3

# Import Ketchup modules
from packages.core.typed_di_integration import get_unified_container
from packages.slack.channel_events.incoming_events import process_request
from packages.core.logging import setup_logger
from packages.core.cleanup_utils import cleanup_resources
from packages.core.typed_di.service_registrations.protocols.jira_protocols import (
    JIRACacheProtocol,
)
from packages.core.typed_di.service_registrations.protocols.mcp_protocols import (
    MCPClientProtocol,
)
from packages.core.typed_di.service_protocols import MetricsDataCollectorProtocol
from packages.core.typed_di.exceptions import MissingDependencyError

logger = setup_logger(__name__)

# Configuration
AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
AWS_SECRET_NAME = os.getenv("AWS_SECRET_NAME", "Ketchup_Token_Secrets")

# Global variables
SLACK_SIGNING_SECRET: Optional[str] = None
container: Optional[Dict[str, Any]] = None
startup_complete = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global SLACK_SIGNING_SECRET, container, startup_complete
    
    try:
        # Startup
        logger.info("Starting Ketchup consolidated service...")
        
        # Fetch Slack signing secret from AWS Secrets Manager
        session = aioboto3.Session()
        async with session.client('secretsmanager', region_name=AWS_REGION) as client:
            response = await client.get_secret_value(SecretId=AWS_SECRET_NAME)
            secrets = json.loads(response['SecretString'])
            SLACK_SIGNING_SECRET = secrets.get('slack_signing_secret')
            
            if not SLACK_SIGNING_SECRET:
                logger.error("Slack signing secret not found in Secrets Manager")
                raise ValueError("Missing slack_signing_secret")
                
            logger.info("Successfully retrieved Slack signing secret")
        
        # Initialize DI container
        start_time = time.time()
        container = await get_unified_container()
        init_duration = time.time() - start_time
        logger.info("DI container initialized successfully")
        
        # Log startup summary
        logger.info("✓ Ketchup service started successfully - initialization completed in %.2fs", init_duration)
        
        startup_complete = True
        yield
        
    finally:
        # Shutdown
        logger.info("Shutting down Ketchup service...")
        startup_complete = False
        if container:
            await cleanup_resources()
        logger.info("Cleanup completed")

app = FastAPI(
    title="Ketchup Consolidated Service",
    description="Handles both webhook reception and API processing",
    lifespan=lifespan
)

def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the request signature from Slack"""
    # Check timestamp to prevent replay attacks (5 minute window)
    try:
        if abs(time.time() - float(timestamp)) > 60 * 5:
            logger.warning("Slack request timestamp too old")
            return False
    except (ValueError, TypeError):
        logger.warning("Invalid timestamp format")
        return False
    
    # Verify signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}".encode('utf-8')
    my_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode('utf-8'),
        sig_basestring,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)

def verify_slack_headers(request: Request) -> tuple[str, str]:
    """Extract and validate required Slack headers"""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    
    if not timestamp or not signature:
        # API Gateway authorizer compatibility - check lowercase headers
        timestamp = request.headers.get("x-slack-request-timestamp", "")
        signature = request.headers.get("x-slack-signature", "")
    
    if not timestamp or not signature:
        logger.warning(f"Missing required Slack headers. Headers: {list(request.headers.keys())}")
        raise HTTPException(
            status_code=401,
            detail="Missing required Slack authorization headers"
        )
    
    return timestamp, signature

def convert_headers_to_lambda_format(headers: dict) -> dict:
    """Convert FastAPI headers to Lambda event format"""
    # Lambda expects lowercase header names
    return {k.lower(): v for k, v in headers.items()}

def create_lambda_event(body: bytes, headers: dict, path: str) -> dict:
    """Create Lambda-compatible event structure"""
    # Determine if body is base64 encoded
    try:
        body_str = body.decode('utf-8')
        is_base64 = False
    except UnicodeDecodeError:
        body_str = base64.b64encode(body).decode('utf-8')
        is_base64 = True
    
    return {
        "body": body_str,
        "isBase64Encoded": is_base64,
        "headers": convert_headers_to_lambda_format(headers),
        "httpMethod": "POST",
        "path": path,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "ketchup-api",
            "protocol": "HTTP/1.1",
            "httpMethod": "POST",
            "path": path,
            "stage": "prod",
            "requestTime": "09/Apr/2024:12:34:56 +0000",
            "requestTimeEpoch": int(time.time() * 1000),
            "requestId": "fastapi-request",
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": "FastAPI"
            }
        }
    }

async def process_slack_request(body: bytes, headers: dict, path: str):
    """Process Slack request asynchronously using existing Ketchup logic"""
    try:
        # Create Lambda-compatible event
        lambda_event = create_lambda_event(body, headers, path)
        
        # Process using existing Ketchup logic
        result = await process_request(lambda_event, container)
        
        # Log the result (actual response was already sent to Slack)
        if result.get("statusCode") != 200:
            logger.error(f"Processing failed: {result}")
        else:
            logger.info(f"Successfully processed {path} request")
            
    except Exception as e:
        logger.error(f"Error processing request: {e}", exc_info=True)

@app.post("/slack/events")
async def handle_slack_event(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack Events API requests"""
    if not container:
        raise HTTPException(status_code=503, detail="Service not ready")
        
    body = await request.body()
    
    # Extract and validate Slack headers
    timestamp, signature = verify_slack_headers(request)
    
    # Verify Slack signature
    if not verify_slack_signature(body, timestamp, signature):
        logger.warning(f"Invalid Slack signature for events endpoint")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Parse the event
    try:
        event_data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Handle URL verification challenge
    if event_data.get("type") == "url_verification":
        return PlainTextResponse(event_data.get("challenge", ""))
    
    # Process asynchronously in background
    headers = dict(request.headers)
    background_tasks.add_task(process_slack_request, body, headers, "/slack/events")
    
    # Immediate response to Slack
    return Response(status_code=200)

@app.post("/slack/commands")
async def handle_slack_command(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack slash commands"""
    if not container:
        raise HTTPException(status_code=503, detail="Service not ready")
        
    body = await request.body()
    
    # Extract and validate Slack headers
    timestamp, signature = verify_slack_headers(request)
    
    # Verify Slack signature
    if not verify_slack_signature(body, timestamp, signature):
        logger.warning(f"Invalid Slack signature for commands endpoint")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Process asynchronously in background
    headers = dict(request.headers)
    background_tasks.add_task(process_slack_request, body, headers, "/slack/commands")
    
    # Immediate response to Slack
    return Response(status_code=200)

@app.post("/slack/interactions")
async def handle_slack_interaction(request: Request, background_tasks: BackgroundTasks):
    """Handle Slack interactive components"""
    if not container:
        raise HTTPException(status_code=503, detail="Service not ready")
        
    body = await request.body()
    
    # Extract and validate Slack headers
    timestamp, signature = verify_slack_headers(request)
    
    # Verify Slack signature
    if not verify_slack_signature(body, timestamp, signature):
        logger.warning(f"Invalid Slack signature for interactions endpoint")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    # Process asynchronously in background
    headers = dict(request.headers)
    background_tasks.add_task(process_slack_request, body, headers, "/slack/interactions")
    
    # Immediate response to Slack
    return Response(status_code=200)

@app.get("/health")
async def health_check():
    """Simple health check endpoint - no DI factory needed"""
    # Basic health check - just verify the app is running
    return JSONResponse(content={
        "status": "healthy",
        "service": "ketchup-app",
        "ready": startup_complete
    })

@app.get("/readiness")
async def readiness_check():
    """Readiness check - verifies all dependencies are initialized"""
    if not startup_complete or not container:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": "ketchup-app",
                "startup_complete": startup_complete,
                "container_initialized": container is not None
            }
        )
    
    return JSONResponse(content={
        "status": "ready",
        "service": "ketchup-app",
        "all_systems_operational": True
    })

@app.get("/admin/metrics")
async def get_metrics():
    """Get service metrics (internal only)"""
    # This would typically check source IP for internal-only access
    return JSONResponse(content={
        "service": "ketchup-app",
        "version": "1.0.0",
        "container_ready": container is not None,
        "secret_loaded": SLACK_SIGNING_SECRET is not None,
        "startup_complete": startup_complete
    })

@app.get("/metrics")
async def get_detailed_metrics():
    """Get detailed metrics for monitoring ReAct agent and cache performance"""
    if not container:
        return JSONResponse(
            status_code=503,
            content={"error": "Service not ready"}
        )
    
    try:
        # Initialize response with basic info
        metrics_response = {
            "service": "ketchup-app",
            "timestamp": time.time(),
            "status": "healthy"
        }

        # Get metrics collector via TypedDI
        metrics_collector = None
        try:
            metrics_collector = await container.aget(MetricsDataCollectorProtocol)
        except (RuntimeError, MissingDependencyError, AttributeError):
            pass

        # Add ReAct agent metrics if available
        if metrics_collector:
            metrics_summary = await metrics_collector.get_metrics_summary()
            metrics_response["react_agent"] = {
                "success": metrics_summary.get("ReActAgentSuccess", {}),
                "failure": metrics_summary.get("ReActAgentFailure", {}),
                "latency": metrics_summary.get("ReActAgentLatency", {}),
                "memory_cleanups": metrics_summary.get("ReActAgentMemoryCleanup", {})
            }
        else:
            metrics_response["react_agent"] = {"status": "not_available"}

        # Get JIRA cache via TypedDI
        jira_cache = None
        try:
            jira_cache = await container.aget(JIRACacheProtocol)
        except (RuntimeError, MissingDependencyError, AttributeError):
            pass

        # Add cache statistics if available
        if jira_cache:
            cache_stats = jira_cache.get_stats()
            metrics_response["jira_cache"] = cache_stats
        else:
            metrics_response["jira_cache"] = {"status": "not_available"}

        # Get MCP client via TypedDI
        mcp_client = None
        try:
            mcp_client = await container.aget(MCPClientProtocol)
        except (RuntimeError, MissingDependencyError, AttributeError):
            pass

        # Add MCP health status if available
        if mcp_client:
            try:
                health_status = await mcp_client.health_check()
                metrics_response["mcp_health"] = {
                    "status": "healthy" if health_status else "unhealthy",
                    "last_check": time.time()
                }
            except Exception as e:
                metrics_response["mcp_health"] = {
                    "status": "error",
                    "error": str(e)
                }
        else:
            metrics_response["mcp_health"] = {"status": "not_available"}
        
        return JSONResponse(content=metrics_response)
        
    except Exception as e:
        logger.error(f"Error retrieving metrics: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to retrieve metrics: {str(e)}"}
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )