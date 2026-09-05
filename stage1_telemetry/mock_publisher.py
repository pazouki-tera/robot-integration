import asyncio
import json
import time
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HOST = '127.0.0.1'
PORT = 9090
HZ = 20
INTERVAL = 1.0 / HZ

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logging.info(f"Accepted connection from {addr}")
    
    # Random initial positions for 6 joints
    positions = [random.uniform(0.0, 180.0) for _ in range(6)]

    try:
        while True:
            # Simulate slight continuous movement
            positions = [p + random.uniform(-1.0, 1.0) for p in positions]
            
            message = {
                "timestamp": time.time(),
                "joints": positions
            }
            
            payload = json.dumps(message).encode('utf-8') + b'\n'
            
            writer.write(payload)
            await writer.drain()
            
            await asyncio.sleep(INTERVAL)
    except (ConnectionResetError, BrokenPipeError):
        logging.warning(f"Connection dropped by {addr}")
    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
    finally:
        logging.info(f"Closing connection to {addr}")
        writer.close()
        await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = server.sockets[0].getsockname()
    logging.info(f"Serving Mock Robot Telemetry on {addr} at {HZ}Hz")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down Mock Publisher")
