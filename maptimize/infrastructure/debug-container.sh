#!/bin/bash
# Debug script to run inside the container

echo "=========================================="
echo "Container Debugging"
echo "=========================================="
echo ""

echo "1. Testing handler import:"
python -c "
import sys
from maptimize.bot import app
print(f'App instance: {app}')
print(f'Listeners count: {len(app._listener_runner._listeners)}')

# Check for registered handlers
for listener in app._listener_runner._listeners:
    if hasattr(listener, 'matchers'):
        for matcher in listener.matchers:
            if hasattr(matcher, 'event_type'):
                print(f'  Event: {matcher.event_type}')
            if hasattr(matcher, 'command'):
                print(f'  Command: {matcher.command}')
" 2>&1

echo ""
echo "2. Testing event reception (simulated):"
python -c "
from maptimize.bot import app

# Simulate a slash command event
test_body = {
    'type': 'slash_command',
    'command': '/maptimize',
    'user_id': 'U123TEST',
    'channel_id': 'C123TEST'
}

print('Simulating slash command event...')
# This won't actually work but will show if handlers exist
print(f'Registered command handlers: {[str(l) for l in app._listener_runner._listeners if hasattr(l, \"matchers\")]}')
" 2>&1

echo ""
echo "=========================================="
