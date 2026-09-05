import collections
import threading
import time
from typing import List, Dict, Optional

class TelemetryState:
    def __init__(self, max_history: int = 1000):
        # We use a deque for O(1) appends and automatic max length management
        self.history = collections.deque(maxlen=max_history)
        self.is_connected = False
        self.last_message_timestamp: Optional[float] = None
        # Use a lock to ensure thread-safety when reading/writing state
        # between the TCP asyncio task and the FastAPI worker threads
        self.lock = threading.Lock()
        
    def update_connection_status(self, connected: bool):
        with self.lock:
            self.is_connected = connected
            
    def add_sample(self, joints: List[float], timestamp: float):
        with self.lock:
            self.history.append({
                "joints": joints,
                "timestamp": timestamp
            })
            self.last_message_timestamp = timestamp
            
    def get_last_n_samples_stats(self, n: int) -> Dict:
        with self.lock:
            if not self.history:
                return {"error": "No data available"}
                
            # Copy to list to safely manipulate
            samples = list(self.history)
            
            # SORT by timestamp to handle OUT OF ORDER or LATE messages
            # Python's Timsort is highly efficient (O(N)) for nearly-sorted data
            samples.sort(key=lambda x: x["timestamp"])
            
            actual_n = min(n, len(samples))
            # Slice the list (from right) to get the most recent chronological data
            samples = samples[-actual_n:]
            
        if not samples:
             return {"error": "No data available"}
             
        # Calculate min, max, mean for each of the 6 joints
        num_joints = len(samples[0]["joints"])
        stats = []
        
        for i in range(num_joints):
            joint_values = [s["joints"][i] for s in samples]
            stats.append({
                "min": min(joint_values),
                "max": max(joint_values),
                "mean": sum(joint_values) / len(joint_values)
            })
            
        return {
            "samples_analyzed": actual_n,
            "joints_stats": stats,
            "latest_timestamp": samples[-1]["timestamp"]
        }

    def get_health(self) -> Dict:
        with self.lock:
            age = None
            if self.last_message_timestamp is not None:
                # Calculate age based on local time vs the time we *received* it (or the message timestamp).
                # Assuming the message timestamp is roughly synchronized. If not, we might want to store local receipt time.
                age = time.time() - self.last_message_timestamp
                
            return {
                "is_connected": self.is_connected,
                "last_message_age_seconds": age
            }

# Global singleton state
state = TelemetryState(max_history=1000)
