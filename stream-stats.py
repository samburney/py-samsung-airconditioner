import os
import argparse
import asyncio
import configparser
import xmltodict
import json
import influxdb
from datetime import datetime, timezone

import samsung_ac

script_path = os.path.dirname(os.path.abspath(__file__))
config_file = f'{script_path}{os.sep}samsung_ac{os.sep}config.ini'

# Parse CLI arguments
def parse_args():
    args = None

    parser = argparse.ArgumentParser(
        description='Grab stats from AC and exit')
    parser.add_argument('--config', '-c', help='Path to config.ini', default=config_file)
    parser.add_argument('--ip', '-i', help='IP address of Airconditioner')
    parser.add_argument('--port', '-p', help='TCP port Airconditioner is listening on (Usually 2878)')
    parser.add_argument('--token', '-t', help='Authentication token')
    parser.add_argument('--duid', '-d', help='Unique Identifier')

    args = parser.parse_args()

    return args


# Get stats
def start_stream(ac):
    command = {
        'Request': {
            '@Type': 'DeviceState',
            'State': {
                '@DUID': ac['duid'],
            }
        }
    }
    command_xml = xmltodict.unparse(command).replace('\n', '') + '\r\n'

    # Connect to Airconditioner
    protocol = asyncio.run(samsung_ac.connect(
        ac,
        post_auth_command=command_xml,
        post_auth_command_timer=60,
        stay_connected=True,
        response_callback=handle_response
    ))

    return protocol.response_data

def handle_response(**kwargs):
    data = kwargs['data']

    attrs = None
    if 'Response' in data:
        # Handle DeviceState responses
        if data['Response']['@Type'] == 'DeviceState' and data['Response']['@Status'] == 'Okay':
            if 'Attr' in data['Response']['DeviceState']['Device']:
                attrs = data['Response']['DeviceState']['Device']['Attr']
    else:
        print(json.dumps(data))

    if attrs is not None:
        args = parse_args()
        config = {}
        if os.path.isfile(args.config):
            config = configparser.ConfigParser()
            config.read(args.config)

        influx_export = False
        if 'influxdb' in config:
            if 'enabled' in config['influxdb']:
                if config['influxdb']['enabled'] == '1' or config['influxdb']['enabled'] == 'true':
                    influx_export = True
                    
                    influx_client = influxdb.InfluxDBClient(
                        host=config['influxdb']['host'],
                        port=config['influxdb']['port'],
                        username=config['influxdb']['username'],
                        password=config['influxdb']['password'],
                    )

                    influx_client.switch_database(config['influxdb']['db'])

                    tags = {}
                    for tag in config['ac']:
                        if tag != 'token':
                            tags[tag] = config['ac'][tag]

                    fields = {}
                    for stat in attrs:
                        value = stat['@Value']
                        if value.isnumeric():
                            value = float(value)

                        fields[stat['@ID']] = value

                    influx_data = [{
                        'measurement': 'samsung_ac',
                        'tags': tags,
                        'time': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                        'fields': fields,
                    }]
                    influx_client.write_points(influx_data)

        if influx_export is False:
            print(json.dumps(attrs))

    return

# Main loop
def main():
    args = parse_args()

    # Config from config file
    if os.path.isfile(args.config):
        config = configparser.ConfigParser()
        config.read(args.config)
        ac = config['ac']
    # Else use args
    else:
        ac = {
            'ip': args.ip,
            'port': args.port,
            'token': args.token,
            'duid': args.duid,
        }

    start_stream(ac)

# Default entrypoint
if __name__ == "__main__":
    main()