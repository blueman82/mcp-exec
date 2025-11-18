#!/usr/bin/env python3
"""
Reliable async scheduler for status updater.
Replaces flaky cron with a Python-native async solution.
"""

import asyncio
import time
import signal
from datetime import datetime
from pathlib import Path

# Import the async status updater function
from ketchup_status_updater.main import run_auto_status
from packages.core.logging import setup_logger

logger = setup_logger(__name__)

class StatusUpdaterScheduler:
    """Scheduler for running status updates reliably in Docker."""
    
    def __init__(self):
        self.running = True
        self.health_file = Path("/tmp/scheduler_health")
        self.last_run_file = Path("/tmp/last_run")
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    def _update_health_status(self, status: str):
        """Update health check file with current status."""
        try:
            self.health_file.write_text(f"{int(time.time())}:{status}")
        except Exception as e:
            logger.error(f"Failed to update health status: {e}")
    
    def _update_last_run(self):
        """Update last run timestamp for health checks."""
        try:
            self.last_run_file.write_text(str(int(time.time())))
        except Exception as e:
            logger.error(f"Failed to update last run timestamp: {e}")
    
    async def run_status_update(self):
        """Run the status updater asynchronously."""
        try:
            start_time = time.time()
            logger.info("Starting scheduled status update run at %s", 
                       datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
            
            self._update_health_status("running")
            
            # Run the actual status updater
            await run_auto_status()
            
            elapsed = time.time() - start_time
            logger.info(f"Status updater completed successfully in {elapsed:.2f} seconds")
            
            # Update timestamps for health checks
            self._update_last_run()
            self._update_health_status("idle")
            
        except Exception as e:
            logger.error(f"Status updater failed: {e}", exc_info=True)
            self._update_health_status("error")
    
    async def start(self):
        """Start the async scheduler."""
        logger.info("Status Updater Scheduler starting...")
        logger.info("Scheduled to run every 55 minutes")
        
        # Mark as healthy
        self._update_health_status("starting")
        
        # Run immediately on startup
        logger.info("Running initial status update...")
        await self.run_status_update()
        
        # Main scheduler loop
        logger.info("Entering main scheduler loop...")
        while self.running:
            try:
                # Wait 55 minutes before next run
                # Update health status every minute during the wait
                if not self.running:
                    break
                
                # Update health status every minute for 55 minutes
                for i in range(55):  # 55 minutes
                    if not self.running:
                        break
                    self._update_health_status("idle")
                    await asyncio.sleep(60)  # Wait 1 minute
                
                if self.running:  # Check if we should still be running
                    await self.run_status_update()
                    
            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying
        
        logger.info("Scheduler stopped")
        self._update_health_status("stopped")

async def async_main():
    """Async main entry point."""
    scheduler = StatusUpdaterScheduler()
    await scheduler.start()

def main():
    """Main entry point."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Scheduler interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()