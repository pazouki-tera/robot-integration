import collections
import threading
import time
from typing import List, Dict, Optional

class TelemetryState:
    def __init__(self, max_history: int = 1000):
        # ARCHITECTURE NOTE:
        # A deque with a fixed maxlen provides an automatic rolling window.
        # It guarantees O(1) time complexity for appends and prevents Out of Memory (OOM) 
        # crashes by automatically discarding the oldest data when the limit is reached.
        self.history = collections.deque(maxlen=max_history)
        self.is_connected = False
        self.last_message_timestamp: Optional[float] = None
        
        # Threading lock ensures data integrity because the async TCP background task
        # is writing to this state concurrently while FastAPI worker threads are reading from it.
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
            
            # ARCHITECTURE NOTE (Chaos Handling):
            # Networks are unreliable; messages may arrive late or out of order.
            # We sort by the robot's timestamp chronologically to ensure accurate math.
            # Python's built-in sort (Timsort) is O(N) for nearly-sorted data, meaning
            # this adds almost zero performance overhead.
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
