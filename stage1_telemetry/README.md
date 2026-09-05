# Stage 1: Telemetry Service

This repository contains the solution for Stage 1 of the Robotics Backend Engineer Assessment.

## Prerequisites

- Python 3.9+
- `pip`

## Running the Service

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Mock Publisher (Robot Controller):**
   In a new terminal window, run the simulated robot controller. It will start a TCP server on port 9090 and emit telemetry at 20 Hz.
   ```bash
   python mock_publisher.py
   ```

3. **Start the Telemetry Service:**
   In another terminal window, navigate to the `stage1_telemetry` directory and start the FastAPI application. Using `python -m uvicorn` avoids issues if your Python Scripts directory isn't in your system PATH.
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
   *(Note: The service is designed to automatically attempt to connect to the mock publisher and gracefully retry if it's unavailable or disconnected).*

## API Endpoints

Once the Telemetry Service is running, you can interact with it directly in your web browser. FastAPI also automatically generates an interactive Swagger documentation page which makes testing easy.

- **Interactive API Docs (Swagger UI)**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) *(Recommended for testing)*
- **Health Endpoint**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
  Returns whether the service is currently connected to the TCP stream and the age (in seconds) of the most recent message received.
- **Telemetry Endpoint**: [http://127.0.0.1:8000/telemetry?n=10](http://127.0.0.1:8000/telemetry?n=10)
  Returns the last N (default 10) samples, alongside the calculated `min`, `max`, and `mean` for each of the 6 joints over that rolling window.

---

## Testing Resilience Scenarios (Chaos Engineering)

To explicitly demonstrate how the software behaves when things go wrong, both the mock publisher and the telemetry service have **built-in Chaos simulations**.

### 1. Simulated Robot Failures (Publisher Chaos)
The `mock_publisher.py` intentionally misbehaves to mimic unreliable physical machines:
- **Out of Order / Late Messages (2% chance):** The robot sends a message with an artificially old timestamp (delayed by 5s). Our service handles this flawlessly because the rolling window explicitly sorts samples chronologically before serving them, ensuring `O(N)` fast correction using Python's Timsort.
- **Hard Power Off (1% chance):** The robot writes exactly half of a JSON payload and instantly kills the connection. Our service catches the resulting `JSONDecodeError`, discards the corrupt data, prevents a crash, and immediately attempts to reconnect.
- **Network Freeze (1% chance):** The robot hangs for 3 seconds mid-transmission.

### 2. Simulated Slow Receiver (Client Chaos)
To answer the prompt: *"say clearly what your service does if it cannot read messages as fast as they arrive"*, the `tcp_client.py` has a built-in bottleneck simulator.
- **Processing Spike (1% chance):** 1% of the time, the telemetry service simulates getting bogged down and sleeps for 1-3 seconds.
- **What happens:** Unread data safely queues in the OS TCP receive buffer. If the sleep is long enough, standard TCP flow control (backpressure) forces the publisher to wait. Once the service wakes up, it rapidly consumes the queued bytes from the OS buffer and instantly catches back up to real-time. No application-level data drops or memory leaks occur.

### Manual Failure Testing
You can also manually trigger failures:
1. Start `mock_publisher.py` and the telemetry service.
2. Check [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) (`"is_connected": true`).
3. Press `Ctrl + C` on the mock publisher. 
4. Check the health endpoint again. `"is_connected"` will instantly become `false` and the `last_message_age_seconds` will continuously increase, reflecting stale data.
5. Restart the publisher. The service will auto-reconnect without a restart, and the health will return to `true`.

---

## Architecture and Assumptions

### Assumptions Made
- The mock controller binds to `127.0.0.1:9090`.
- The telemetry data is sent over TCP as newline-separated JSON strings (JSON Lines format).
- The JSON payload contains a `timestamp` (float) and a `joints` array (list of 6 floats in degrees).
- The definition of "rolling window" is implemented via a bounded double-ended queue (`collections.deque`) with a maximum size of 1000 to prevent unbounded memory growth.

### Handling Fast Producers (Backpressure)
If the telemetry service cannot read messages as fast as they arrive over the network, the following happens:
1. **TCP Backpressure**: Unread data will queue in the `asyncio` transport buffer and the underlying OS socket receive buffer. Once these buffers are full, standard TCP flow control will reduce the TCP window size to zero, effectively forcing the publisher to wait or buffer data on its end.
2. **Bounded Memory**: Once a message is read and parsed, it is appended to a `collections.deque` with a fixed maximum length (e.g., `maxlen=1000`). This guarantees that our service's memory usage is strictly bounded. Older samples are automatically dropped from the queue, meaning our application will not crash due to memory exhaustion even if left running indefinitely.
3. **No Explicit Application-Level Dropping**: We do not explicitly drop incoming bytes on our end before parsing. We rely on the TCP protocol to naturally throttle the publisher if we fall behind.
