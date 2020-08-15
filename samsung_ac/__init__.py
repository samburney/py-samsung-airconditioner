import ssl
import asyncio

from . import client

# AC connection loop
async def connect(ac, **kwargs):
    # Create SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.load_cert_chain('cert/ac14k_m.pem')

    # Define asyncio loop
    loop = asyncio.get_running_loop()

    # Handle closed connection
    on_con_lost = loop.create_future()

    transport, protocol = await loop.create_connection(
        lambda: client.AirconditionerClientProtocol(on_con_lost, ac, **kwargs),
        host=ac['ip'],
        port=ac['port'],
        ssl=ssl_context
    )

    # Close transport
    try:
        await on_con_lost
    finally:
        transport.close()

    return protocol
