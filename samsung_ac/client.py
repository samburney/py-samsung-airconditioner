import sys
import asyncio
import json
import xmltodict


# Handle AC network I/O
class AirconditionerClientProtocol(asyncio.Protocol):
    def __init__(self, on_con_lost, ac, **kwargs):
        self.ac = ac
        self.connected = False
        self.authenticated = False
        self.stay_connected = False
        self.transport = None
        self.on_con_lost = on_con_lost
        self.waiting_for_token = False
        self.response_data = None
        
        self.post_auth_command = None
        if 'post_auth_command' in kwargs:
            self.post_auth_command = kwargs['post_auth_command']
        
        self.post_auth_command_timer = None
        if 'post_auth_command_timer' in kwargs:
            self.post_auth_command_timer = kwargs['post_auth_command_timer']

        self.post_auth_stay_connected = False
        if 'stay_connected' in kwargs:
            self.post_auth_stay_connected = kwargs['stay_connected']

        self.response_callback = None
        if 'response_callback' in kwargs:
            self.response_callback = kwargs['response_callback']

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
                    self.stay_connected = False
                    print('Protocol version unsupported.', file=sys.stderr)                    
                    return

            # Process XML
            elif line.startswith('<?xml'):
                data = xmltodict.parse(line)

                # Handle authentication
                if self.authenticated is False:
                    # Authenticate
                    if self.ac['token']:
                        self.do_auth(data)

                    # Do token retrieval is none is specified
                    else:
                        self.get_auth_token(data)

                    return

                else:
                    if 'Response' in data:
                        # Handle DeviceState responses
                        if data['Response']['@Type'] == 'DeviceState' and data['Response']['@Status'] == 'Okay':
                            if 'Attr' in data['Response']['DeviceState']['Device']:
                                attrs = data['Response']['DeviceState']['Device']['Attr']
                                
                                self.response_data = attrs
                                self.stay_connected = self.post_auth_stay_connected

                                if self.response_callback is not None:
                                    self.response_callback(data=data)

                                return
                
                # Handle unexpected messages
                if self.response_callback is None:
                    print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)
                else:
                    self.response_callback(data=data)

                if self.authenticated is True:
                    self.stay_connected = self.post_auth_stay_connected

                return


    # Authenticate 
    def do_auth(self, data):
        # Response type 'Update'
        if 'Update' in data:
            # Logged out, attempt to auth
            if data['Update']['@Type'] == 'InvalidateAccount':
                request = {
                    'Request': {
                        '@Type': 'AuthToken',
                        'User': {
                            '@Token': self.ac['token']
                        }
                    }
                }
                request_xml = xmltodict.unparse(request).replace('\n', '')
                self.transport.write(f"{request_xml}\r\n".encode())

                return

        # Response type 'Response'
        elif 'Response' in data:
            # Successfully authenticated
            if data['Response']['@Status'] == 'Okay' and data['Response']['@Type'] == 'AuthToken':
                    self.authenticated = True

                    # Hand off to any post-auth actions
                    self.handle_post_auth()

                    return

            # Airconditioner returned an error
            if data['Response']['@Status'] == 'Fail' and data['Response']['@Type'] == 'AuthToken':
                    print(f"Error {data['Response']['@ErrorCode']}: Token authentication error", file=sys.stderr)
                    self.stay_connected = False
                    return

        # Handle unexpected messages
        print(f'Unsupported message: {json.dumps(data)}', file=sys.stderr)
        return


    # Process to get authentication token            
    def get_auth_token(self, data):
        # Response type 'Update'
        if 'Update' in data:
            # Logged out, attempt to get authentication token
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

    # Handle post_auth action
    def handle_post_auth(self, *args):
        if self.post_auth_command is not None:
            self.transport.write(self.post_auth_command.encode())
        
        if self.post_auth_command_timer is not None:
            task = asyncio.get_event_loop().create_task(self.wait_for_post_auth_timer())
            task.add_done_callback(self.handle_post_auth)

        return

    # Timer for post_auth_timer
    @asyncio.coroutine
    def wait_for_post_auth_timer(self):
        return(yield from asyncio.sleep(self.post_auth_command_timer))
