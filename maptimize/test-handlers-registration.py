#!/usr/bin/env python3
"""
Test if handlers are properly registered in the Bolt app.
Run this to see what handlers the app actually has.
"""

import sys
sys.path.insert(0, 'src')

from maptimize.bot import app

print("=" * 60)
print("Bolt App Handler Registration Check")
print("=" * 60)
print()

# Check what listeners are registered
print("Registered listeners:")
print(f"  Total listeners: {len(app._listener_runner._listeners)}")
print()

# Check event listeners
event_listeners = [l for l in app._listener_runner._listeners if hasattr(l, 'matchers')]
print(f"Event listeners: {len(event_listeners)}")
for listener in event_listeners:
    print(f"  - {listener}")
print()

# Check if our specific handlers are registered
print("Looking for our handlers:")

# Check for app_mention
app_mention_found = False
for listener in app._listener_runner._listeners:
    if hasattr(listener, 'matchers'):
        for matcher in listener.matchers:
            if hasattr(matcher, 'event_type') and matcher.event_type == 'app_mention':
                app_mention_found = True
                print(f"  ✓ app_mention handler found: {listener.ack_function}")
                break

if not app_mention_found:
    print("  ✗ app_mention handler NOT found")

# Check for slash command
slash_command_found = False
for listener in app._listener_runner._listeners:
    if hasattr(listener, 'matchers'):
        for matcher in listener.matchers:
            if hasattr(matcher, 'command') and matcher.command == '/maptimize':
                slash_command_found = True
                print(f"  ✓ /maptimize command handler found: {listener.ack_function}")
                break

if not slash_command_found:
    print("  ✗ /maptimize command handler NOT found")

print()
print("=" * 60)

if app_mention_found and slash_command_found:
    print("✓ Both handlers are properly registered!")
else:
    print("✗ Handlers are NOT properly registered!")
    print()
    print("This means the decorators aren't working correctly.")
    print("Check for:")
    print("  1. Import errors in bot.py or handlers.py")
    print("  2. Exceptions during handler registration")
    print("  3. handlers.py not being imported")

print("=" * 60)
