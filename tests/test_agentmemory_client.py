import requests
import sys

class AgentMemoryClient:
    def __init__(self, url="http://localhost:3111"):
        self.url = url

    def health_check(self):
        try:
            r = requests.get(f"{self.url}/health", timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False

    def lease_acquire(self, resource_id, holder_id, ttl=30):
        try:
            r = requests.post(f"{self.url}/api/lease/acquire", json={
                "resource_id": resource_id,
                "holder_id": holder_id,
                "ttl": ttl
            }, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"Lease acquire failed: {e}")
            return False

    def signal_send(self, signal_type, payload, target=None):
        try:
            r = requests.post(f"{self.url}/api/signal/send", json={
                "signal_type": signal_type,
                "payload": payload,
                "target": target
            }, timeout=5)
            return r.status_code == 200
        except Exception as e:
            print(f"Signal send failed: {e}")
            return False

if __name__ == "__main__":
    client = AgentMemoryClient()

    print("Testing agentmemory client...")
    print(f"1. Health check: {'✓' if client.health_check() else '✗'}")
    print(f"2. Lease acquire: {'✓' if client.lease_acquire('test-resource', 'test-agent', 30) else '✗'}")
    print(f"3. Signal send: {'✓' if client.signal_send('test-signal', {'data': 'test'}) else '✗'}")
    print("\nClient test complete.")
