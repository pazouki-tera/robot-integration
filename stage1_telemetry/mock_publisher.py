import asyncio
import json
import time
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ROBOT SIMULATOR] %(levelname)s: %(message)s")

HOST = '127.0.0.1'
PORT = 9090
HZ = 20
INTERVAL = 1.0 / HZ

async def handle_client(reader, writer):
    addr = writer.get_extra_info('peername')
    logging.info(f"Accepted connection from {addr}")
    
    positions = [random.uniform(0.0, 180.0) for _ in range(6)]

    try:
        while True:
            # Simulate slight continuous movement
            positions = [p + random.uniform(-1.0, 1.0) for p in positions]
            
            # --- CHAOS SIMULATION ---
            chaos_roll = random.random()
            
            # 1. 2% chance to send an OUT OF ORDER / LATE message
            if chaos_roll < 0.02:
                logging.warning("Simulating OUT OF ORDER message (delayed by 5 seconds)")
                msg_time = time.time() - 5.0
            else:
                msg_time = time.time()
                
            message = {
                "timestamp": msg_time,
                "joints": positions
            }
            
            payload = json.dumps(message).encode('utf-8') + b'\n'
            
            # 2. 1% chance to drop connection MID-CYCLE (partial message)
            if 0.02 <= chaos_roll < 0.03:
                logging.error("Simulating HARD POWER OFF (Connection drop mid-transmission)")
                # Write only half the payload to simulate partial network packet before death
                writer.write(payload[:len(payload)//2])
                await writer.drain()
                writer.close()
                return # Exit immediately

            # 3. 1% chance to pause/freeze (network delay)
            if 0.03 <= chaos_roll < 0.04:
                logging.warning("Simulating NETWORK FREEZE (Pausing for 3 seconds)")
                await asyncio.sleep(3.0)
                
            # Normal transmission
            writer.write(payload)
            await writer.drain()
            
            await asyncio.sleep(INTERVAL)
            
    except (ConnectionResetError, BrokenPipeError):
        logging.warning(f"Connection dropped by {addr}")
    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
    finally:
        if not writer.is_closing():
            logging.info(f"Closing connection to {addr}")
            writer.close()
            await writer.wait_closed()

async def main():
    server = await asyncio.start_server(handle_client, HOST, PORT)
    addr = server.sockets[0].getsockname()
    logging.info(f"Serving Chaos Robot Telemetry on {addr} at {HZ}Hz")

    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Shutting down Mock Publisher")
