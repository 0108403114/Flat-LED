import asyncio
from bleak import BleakScanner

async def scan():
    devices = await BleakScanner.discover(timeout=10.0)
    print(f'FOUND {len(devices)} devices')
    print()
    
    for d in devices:
        name = d.name or '<no-name>'
        if 'HLL' in name:
            print(f'✓ {name:30} | {d.address}')

asyncio.run(scan())
