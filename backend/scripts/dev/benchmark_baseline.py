import urllib.request
import time
import json

endpoints = [
    "/api/v1/products?page_size=50",
    "/api/v1/categories",
    "/api/v1/delivery-zones",
    "/health",
]

print("=== BASELINE PERFORMANCE AUDIT ===")
for ep in endpoints:
    url = f"http://127.0.0.1:8000{ep}"
    latencies = []
    response_size = 0
    headers = {}
    for i in range(15):
        t0 = time.perf_counter()
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as res:
            body = res.read()
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000)
            response_size = len(body)
            headers = dict(res.headers)
    
    # Drop first (warmup)
    measured = latencies[1:]
    print(f"\nEndpoint: {ep}")
    print(f"  Response Size: {response_size:,} bytes")
    print(f"  Min: {min(measured):.2f}ms | Avg: {sum(measured)/len(measured):.2f}ms | Median: {sorted(measured)[len(measured)//2]:.2f}ms | Max: {max(measured):.2f}ms")
    print(f"  Content-Encoding: {headers.get('content-encoding', 'none (uncompressed)')}")
    print(f"  Cache-Control: {headers.get('cache-control', 'none')}")
    print(f"  ETag: {headers.get('etag', 'none')}")

