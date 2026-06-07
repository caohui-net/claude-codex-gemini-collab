#!/usr/bin/env python3
"""Introspect iii-sdk API to understand correct usage."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from iii import register_worker

    print("Creating iii client...")
    client = register_worker("ws://localhost:49134")

    print(f"\nClient type: {type(client)}")
    print(f"Client class: {client.__class__.__name__}")

    print("\nAvailable methods:")
    for attr in dir(client):
        if not attr.startswith('_'):
            print(f"  - {attr}")

    print("\nTrying to call trigger...")
    result = client.trigger({
        "function_id": "mem::lease-acquire",
        "payload": {"lease_id": "test", "owner": "test", "ttl_seconds": 60}
    })
    print(f"Result: {result}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
