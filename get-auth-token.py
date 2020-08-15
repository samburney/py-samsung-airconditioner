import argparse
import asyncio

import samsung_ac

# Parse CLI arguments
def parse_args():
    args = None

    parser = argparse.ArgumentParser(
        description='Tool to obtain Authentication Token and DUID from Samsung Airconditioner')
    parser.add_argument('ip', help='IP address of Airconditioner')
    parser.add_argument('--port', '-p', help='TCP port Airconditioner is listening on (Usually 2878)', default=2878)

    args = parser.parse_args()

    return args


# Main routine
def main():
    args = parse_args()

    # Define AC config variable
    ac = {
        'ip': args.ip,
        'port': args.port,
        'token': None,
        'duid': None,
    }

    # Connect to Airconditioner
    asyncio.run(samsung_ac.connect(ac))


# Default function
if __name__ == "__main__":
    main()
