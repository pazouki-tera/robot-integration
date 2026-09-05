import asyncio
import json
import logging
from app.state import state

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HOST = '127.0.0.1'
PORT = 9090
RECONNECT_DELAY = 2.0

async def tcp_reader_task():
    """
    Continuously attempts to connect to the robot controller and read telemetry.
    Updates the global state appropriately.
    """
    while True:
        try:
            logging.info(f"Attempting to connect to robot controller at {HOST}:{PORT}...")
            reader, writer = await asyncio.open_connection(HOST, PORT)
            logging.info("Connected to robot controller.")
            
            state.update_connection_status(True)
            
            while True:
                line = await reader.readline()
                if not line:
                    logging.warning("Connection closed by the server.")
                    break
                    
                try:
                    message = json.loads(line.decode('utf-8'))
                    timestamp = message.get("timestamp")
                    joints = message.get("joints")
                    
                    if timestamp is not None and joints is not None:
                        state.add_sample(joints, timestamp)
                        
                    # ARCHITECTURE NOTE (TCP Backpressure & CPU Throttling):
                    # If this service experiences a CPU spike and reads slowly, the OS socket 
                    # receive buffer will fill. TCP Flow Control naturally kicks in and forces 
                    # the robot to slow down. We don't drop bytes at the app level.
                    import random
                    if random.random() < 0.01:
                        delay = random.uniform(1.0, 3.0)
                        logging.warning(f"Simulating SLOW RECEIVER: Service bogged down, sleeping for {delay:.2f}s")
                        await asyncio.sleep(delay)
                        
                except json.JSONDecodeError:
                    # ARCHITECTURE NOTE:
                    # If the robot drops power mid-transmission, we will receive a partial, 
                    # malformed JSON string. Catching this prevents the background loop from crashing.
                    logging.error(f"Received malformed JSON payload (Partial message/Power loss): {line}")
                    
        except ConnectionRefusedError:
            logging.warning("Connection refused. Is the robot controller running?")
        except Exception as e:
            logging.error(f"Unexpected error in TCP reader: {e}")
        finally:
            state.update_connection_status(False)
            logging.info(f"Disconnected. Reconnecting in {RECONNECT_DELAY} seconds...")
            await asyncio.sleep(RECONNECT_DELAY)
