import asyncio
import time
from collections import Counter
import aiohttp

TARGET_URL = "http://localhost:5000/api/tier-endpoint"
TOTAL_REQUESTS = 50

async def send_request(session: aiohttp.ClientSession, request_id: int):
    start_time = time.perf_counter()
    headers = {"X-Forwarded-For": "203.0.113.42"}  
    
    try:
        async with session.get(TARGET_URL, headers=headers) as response:
            latency = (time.perf_counter() - start_time) * 1000  
            return response.status, latency
    except Exception as e:
        latency = (time.perf_counter() - start_time) * 1000
        return f"Error ({type(e).__name__})", latency

async def run_benchmark():
    print(f"🚀 Launching {TOTAL_REQUESTS} concurrent requests against {TARGET_URL}...\n")
    
    start_total_time = time.perf_counter()
    
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, i) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
        
    end_total_time = time.perf_counter()
    
   
    total_duration_sec = end_total_time - start_total_time
    statuses = Counter([res[0] for res in results])
    latencies = [res[1] for res in results]
    avg_latency = sum(latencies) / len(latencies)
    
    print("=" * 50)
    print("📊 BENCHMARK RESULTS")
    print("=" * 50)
    print(f"Total Execution Time: {total_duration_sec:.4f} seconds")
    print(f"Average Request Latency: {avg_latency:.2f} ms")
    print(f"Requests per Second (RPS): {TOTAL_REQUESTS / total_duration_sec:.2f}\n")
    print("HTTP Status Breakdown:")
    for status, count in statuses.items():
        description = ""
        if status == 200:
            description = "(Allowed)"
        elif status == 429:
            description = "(Rate Limited)"
        elif status == 403:
            description = "(Blocked / Circuit Breaker Banned)"
        print(f"  - Status {status} {description}: {count} requests")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_benchmark())