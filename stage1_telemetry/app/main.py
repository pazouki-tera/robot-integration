import asyncio
from fastapi import FastAPI, Query
from typing import Dict, Any

from app.state import state
from app.tcp_client import tcp_reader_task

app = FastAPI(title="Robot Telemetry Service")

# Background task reference to prevent garbage collection if needed
_bg_task = None

@app.on_event("startup")
async def startup_event():
    global _bg_task
    # Start the TCP connection loop in the background when FastAPI starts
    _bg_task = asyncio.create_task(tcp_reader_task())

@app.get("/telemetry")
def get_telemetry(n: int = Query(10, description="Number of recent samples to analyze", ge=1)):
    """
    Returns the last N samples along with the minimum, maximum, and mean 
    of each joint over that window.
    """
    return state.get_last_n_samples_stats(n)

@app.get("/health")
def get_health() -> Dict[str, Any]:
    """
    Reports connection health: whether the service is connected to the controller,
    and how old the most recent message is.
    """
    return state.get_health()
