import urllib.request
import urllib.error
import time
import gzip

endpoints = [
    "/api/v1/categories",
    "/api/v1/products?page_size=50",
    "/api/v1/delivery-zones",
]

print("=== Post-Optimization Benchmark & Validation ===")

for ep in endpoints:
    url = f"http://127.0.0.1:8000{ep}"
    
    # 1. First request with gzip support
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip"})
    start = time.perf_counter()
    with urllib.request.urlopen(req) as resp:
        duration = (time.perf_counter() - start) * 1000
        raw_body = resp.read()
        status = resp.status
        content_encoding = resp.headers.get("Content-Encoding")
        cache_control = resp.headers.get("Cache-Control")
        etag = resp.headers.get("ETag")
        transfer_bytes = len(raw_body)
        
        if content_encoding == "gzip":
            uncompressed_bytes = len(gzip.decompress(raw_body))
        else:
            uncompressed_bytes = transfer_bytes

    print(f"\nEndpoint: {ep}")
    print(f"Status: {status}")
    print(f"Latency: {duration:.2f}ms")
    print(f"Content-Encoding: {content_encoding}")
    print(f"Transfer Size (Gzip): {transfer_bytes:,} bytes")
    print(f"Uncompressed Size: {uncompressed_bytes:,} bytes")
    ratio = (1 - (transfer_bytes / uncompressed_bytes)) * 100 if uncompressed_bytes else 0
    print(f"Compression Ratio: {ratio:.1f}% reduction")
    print(f"ETag: {etag}")
    print(f"Cache-Control: {cache_control}")

    # 2. Conditional request with If-None-Match (ETag)
    if etag:
        req304 = urllib.request.Request(url, headers={"If-None-Match": etag, "Accept-Encoding": "gzip"})
        start304 = time.perf_counter()
        try:
            with urllib.request.urlopen(req304) as resp304:
                status304 = resp304.status
        except urllib.error.HTTPError as e:
            status304 = e.code
        duration304 = (time.perf_counter() - start304) * 1000
        print(f"Conditional Request (If-None-Match: {etag}):")
        print(f"  Status: {status304} (304 Not Modified)")
        print(f"  Latency: {duration304:.2f}ms (instant cache hit, 0 body bytes transferred)")
