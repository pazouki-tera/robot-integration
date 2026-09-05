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
   In another terminal window, start the FastAPI application using uvicorn. 
   ```bash
   uvicorn app.main:app --host 0.0.0.1 --port 8000
   ```
   *(Note: The service is designed to automatically attempt to connect to the mock publisher and gracefully retry if it's unavailable or disconnected).*

## API Endpoints

Once the Telemetry Service is running, you can access the following endpoints:

- **Health Endpoint**: `http://127.0.0.1:8000/health`
  Returns whether the service is currently connected to the TCP stream and the age (in seconds) of the most recent message received.

- **Telemetry Endpoint**: `http://127.0.0.1:8000/telemetry?n=10`
  Returns the last N (default 10) samples, alongside the calculated `min`, `max`, and `mean` for each of the 6 joints over that rolling window.

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
