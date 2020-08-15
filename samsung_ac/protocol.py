import sys
import asyncio
import json
import xmltodict


# Handle AC network I/O
class AirconditionerClientProtocol(asyncio.Protocol):
    def __init__(self, on_con_lost, ac):
        self.ac = ac
        self.connected = False
        self.stay_connected = False
        self.transport = None
        self.on_con_lost = on_con_lost
        self.waiting_for_token = False

    def connection_made(self, transport):
        self.connected = True
        self.transport = transport
        print('Connected to Airconditioner.')

    def data_received(self, message):
        self.handle_data(message.decode())

        if self.stay_connected is False:
            self.transport.close()

    def connection_lost(self, exc):
        self.connected = False
        self.on_con_lost.set_result(True)
        print('Disconnected from Airconditioner.')

    # Handle received data
    def handle_data(self, message):
        self.stay_connected = True
        lines = message.splitlines()

        for line in lines:
            # Check AC protocol version
            if line.startswith('DPLUG'):
                print(f'Protocol version: {line}')

                if line != 'DPLUG-1.6':
                    self.transport.close()
                    print('Protocol version unsupported.', file=sys.stderr)
                    
                    self.stay_connected = False
                    return

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

                        return

                    # Successful token retrieval
                    if data['Update']['@Status'] == 'Completed' and data['Update']['@Type'] == 'GetToken':
                        if data['Update']['@Token']:
                            self.waiting_for_token = False

                            print(f"Authentication token: {data['Update']['@Token']}")

                            self.stay_connected = False
                            return

                # Response type 'Response'
                elif 'Response' in data:
                    # Handle Token Retrieval process
                    if data['Response']['@Status'] == 'Ready' and data['Response']['@Type'] == 'GetToken':
                        task = asyncio.get_event_loop().create_task(self.wait_for_token())
                        task.add_done_callback(self.wait_for_token_expired)
                        print('Power on Airconditioner within 30 seconds...')

                        return

                    # Airconditioner returned an error
                    if data['Response']['@Status'] == 'Fail' and data['Response']['@Type'] == 'Authenticate':
                        if self.waiting_for_token is True:
                            self.waiting_for_token = False

                            print(f"Error {data['Response']['@ErrorCode']}: Token retrieval failed", file=sys.stderr)

                            self.stay_connected = False
                            return

                # Handle unexpected messages
                print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)
                return

    # Coroutine to wait for token from AC
    @asyncio.coroutine
    def wait_for_token(self):
        self.waiting_for_token = True
        return(yield from asyncio.sleep(30, result=self.waiting_for_token))

    def wait_for_token_expired(self, task):
        if self.waiting_for_token is True:
            self.transport.close()
            print('Authentication period expired, exiting.', file=sys.stderr)
