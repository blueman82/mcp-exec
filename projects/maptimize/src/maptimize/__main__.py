"""Main entry point for Maptimize Slack bot application.

This module is executed when the application is started as a module:
    python -m maptimize

It initializes the Slack bot and starts the Socket Mode handler to listen
for events from Slack.
"""

from maptimize.bot import create_socket_handler

if __name__ == "__main__":
    # Start Socket Mode handler
    try:
        print("Starting Socket Mode handler...", flush=True)
        handler = create_socket_handler()
        print("Socket Mode handler created, starting connection...", flush=True)
        handler.start()
        print("Socket Mode handler started successfully", flush=True)
    except Exception as e:
        print(f"ERROR starting Socket Mode handler: {e}", flush=True)
        import traceback

        traceback.print_exc()
