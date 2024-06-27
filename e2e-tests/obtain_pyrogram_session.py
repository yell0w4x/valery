from pyrogram import Client, filters
import sys
from argparse import ArgumentParser


def cli(args=sys.argv[1:]):
    parser = ArgumentParser()
    parser.add_argument('--session-name', required=True, help='Arbitrary session name')
    parser.add_argument('--api-id', default=None, help='Telegram API id')
    parser.add_argument('--api-hash', default=None, help='Telegram API hash')

    return parser.parse_args(args)


def main():
    args = cli()
    app = Client(args.session_name, api_id=args.api_id, api_hash=args.api_hash)

    @app.on_message(filters.all)
    async def on_message(client, message):
        print(message.text)

    app.run()

if __name__ == '__main__':
    main()
