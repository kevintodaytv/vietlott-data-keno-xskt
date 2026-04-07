#!/usr/bin/env python3
"""
run_server.py — SNIPER-X CORE Launcher
Wrapper chạy uvicorn với WindowsProactorEventLoop đúng cách cho Python 3.12
"""
import sys
import asyncio

# PATCH TRƯỚC TIÊN — trước cả khi import uvicorn
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

import uvicorn

if __name__ == "__main__":
    print("[THE CORE] Starting SNIPER-X Backend on port 8888...")
    print("[THE CORE] Python:", sys.version)
    print("[THE CORE] Platform:", sys.platform)
    print("[THE CORE] EventLoop:", type(asyncio.get_event_loop()).__name__)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8888,
        reload=True,
        loop="auto",  # auto chọn ProactorEventLoop trên Windows
        log_level="info"
    )
