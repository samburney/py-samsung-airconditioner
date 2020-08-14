import sys
import time
import asyncio
import ssl
import xmltodict
import json
import argparse


# Parse CLI arguments
def parse_args():
    args = None

    parser = argparse.ArgumentParser(
        description='Tool to obtain Authentication Token and DUID from Samsung Airconditioner')
    parser.add_argument('ip', help='IP address of Airconditioner')
    parser.add_argument('--port', '-p', help='TCP port Airconditioner is listening on (Usually 2878)', default=2878)

    args = parser.parse_args()

    return args


# Handle AC network I/O
class AirconditionerClientProtocol(asyncio.Protocol):
    def __init__(self, on_con_lost):
        self.connected = False
        self.transport = None
        self.on_con_lost = on_con_lost
        self.waiting_for_token = False

    def connection_made(self, transport):
        self.connected = True
        self.transport = transport
        print('Connected to Airconditioner.')

    def data_received(self, message):
        self.handle_data(message.decode())

    def connection_lost(self, exc):
        self.connected = False
        self.on_con_lost.set_result(True)
        print('Disconnected from Airconditioner.')

    # Handle received data
    def handle_data(self, message):
        lines = message.splitlines()

        for line in lines:
            # Check AC protocol version
            if line.startswith('DPLUG'):
                print(f'Protocol version: {line}')

                if line != 'DPLUG-1.6':
                    self.transport.close()
                    exit(1, 'Protocol version unsupported.')

            # Process XML
            elif line.startswith('<?xml'):
                data = xmltodict.parse(line)

                # Response type 'Update'
                if 'Update' in data:
                    # Logged out, attemnpt to auth
                    if data['Update']['@Type'] == 'InvalidateAccount':
                        request = {
                            'Request': {
                                '@Type': 'GetToken',
                            }
                        }
                        request_xml = xmltodict.unparse(request).replace('\n', '')
                        self.transport.write(f"{request_xml}\r\n".encode())

                    # Handle unexpected messages
                    else:
                        print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)

                # Response type 'Response'
                elif 'Response' in data:
                    # Logged out, attemnpt to auth
                    if data['Response']['@Type'] == 'GetToken':
                        if data['Response']['@Status'] == 'Ready':
                            task = asyncio.get_event_loop().create_task(self.wait_for_token())
                            task.add_done_callback(self.wait_for_token_expired)
                            print('Power on Airconditioner within 30 seconds...')

                        # Handle unexpected messages
                        else:
                            print(f'Unexpected message: {json.dumps(data)}', file=sys.stderr)

                    # Handle unexpected messages
                    else:
                        print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)

                # Handle unexpected messages
                else:
                    print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)

    # Coroutine to wait for token from AC
    @asyncio.coroutine
    def wait_for_token(self):
        self.waiting_for_token = True
        return(yield from asyncio.sleep(30, result=self.waiting_for_token))

    def wait_for_token_expired(self, task):
        if self.waiting_for_token is True:
            self.transport.close()
            print('Authentication period expired, exiting.', file=sys.stderr)


# AC connection loop
async def ac_connect(ac):
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
        lambda: AirconditionerClientProtocol(on_con_lost),
        host=ac['ip'],
        port=ac['port'],
        ssl=ssl_context
    )

    # Close transpot
    try:
        await on_con_lost
    finally:
        transport.close()


# Main routine
def main():
    args = parse_args()

    ac = {
        'ip': args.ip,
        'port': args.port,
        'token': None,
        'duid': None,
    }

    # Connect to Airconditioner
    asyncio.run(ac_connect(ac))


# Default function
if __name__ == "__main__":
    main()
