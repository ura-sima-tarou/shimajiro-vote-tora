import asyncio
import json
import os
import time
import urllib.request

import httpx

API = "https://api-ryukogo2026.shibadogcap.com/v"
WORKERS = int(os.environ.get("WORKERS", "200"))
DURATION = int(os.environ.get("DURATION_SECONDS", "270"))
TARGET = int(os.environ.get("TARGET_ID", "569"))
AMOUNT = int(os.environ.get("AMOUNT", "5000000000000000"))
STATS_URL = os.environ.get("STATS_URL", "")
NODE_NAME = os.environ.get("NODE_NAME", "github-actions")

success = 0
failure = 0
stop = asyncio.Event()


async def worker(client, idx):
    global success, failure
    while not stop.is_set():
        try:
            r = await client.post(API, json={"i": TARGET, "a": AMOUNT})
            if r.status_code in (200, 201, 204):
                success += 1
            elif r.status_code == 429:
                retry = r.headers.get("retry-after")
                try:
                    wait = min(float(retry), 30.0) if retry else 5.0
                except ValueError:
                    wait = 5.0
                await asyncio.sleep(wait)
            else:
                failure += 1
                await asyncio.sleep(1.0)
        except Exception:
            failure += 1
            await asyncio.sleep(2.0)


async def main():
    limits = httpx.Limits(max_keepalive_connections=WORKERS, max_connections=WORKERS)
    async with httpx.AsyncClient(http2=True, limits=limits, timeout=60.0) as client:
        tasks = [asyncio.create_task(worker(client, i)) for i in range(WORKERS)]
        await asyncio.sleep(DURATION)
        stop.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    print(f"done success={success} failure={failure}")

    if STATS_URL:
        body = json.dumps({"name": NODE_NAME, "success": success, "failure": failure}).encode()
        req = urllib.request.Request(STATS_URL, data=body, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print("stats report failed:", e)


asyncio.run(main())
