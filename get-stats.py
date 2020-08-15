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
def get_stats(ac):
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
        stay_connected=False,
    ))

    return protocol.response_data


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

    stats = get_stats(ac)

    influx_export = False
    if 'influxdb' in config:
        if 'enabled' in config['influxdb']:
            if config['influxdb']['enabled'] == '1' or config['influxdb']['enabled'] == 'true':
                influx_export = True
                
                influx_client = influxdb.InfluxDBClient(
                    host=config['influxdb']['host'],
                    port=config['influxdb']['port'],
                    username=None,
                    password=None,
                )

                influx_client.create_database(config['influxdb']['db'])
                influx_client.switch_database(config['influxdb']['db'])

                tags = {}
                for tag in config['ac']:
                    if tag != 'token':
                        tags[tag] = config['ac'][tag]

                fields = {}
                for stat in stats:
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
        print(json.dumps(stats))


# Default entrypoint
if __name__ == "__main__":
    main()