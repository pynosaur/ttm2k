#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import curses
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    __package__ = "app"

from app import __version__
from app.core.server import Server, DEFAULT_PORT
from app.core.client import Client
from app.core.ui import ChatUI
from app.utils.doc_reader import read_app_doc


def print_help():
    doc = read_app_doc("ttm2k")
    desc = doc.get(
        "description",
        "Talk To Me 2000 -- encrypted terminal messenger",
    )

    print(f"ttm2k - {desc}")
    print()
    print("USAGE:")
    print("    ttm2k [OPTIONS]              Start client (connect to server)")
    print("    ttm2k server [OPTIONS]       Start relay server")
    print()
    print("CLIENT OPTIONS:")
    print("    -h, --help                   Show help message")
    print("    -v, --version                Show version information")
    print("    -s, --server HOST            Server address (default: 127.0.0.1)")
    print("    -p, --port PORT              Server port (default: 2000)")
    print()
    print("SERVER OPTIONS:")
    print("    --bind ADDR                  Bind address (default: 0.0.0.0)")
    print("    -p, --port PORT              Listen port (default: 2000)")
    print("    --data-dir DIR               Data directory (default: ~/.ttm2k/server)")
    print()
    print("EXAMPLES:")
    print("    ttm2k                        Connect to localhost:2000")
    print("    ttm2k -s 10.0.0.5 -p 3000   Connect to remote server")
    print("    ttm2k server                 Start server on port 2000")
    print("    ttm2k server -p 8080         Start server on port 8080")
    print()
    print("SECURITY:")
    print("    All messages are end-to-end encrypted using Diffie-Hellman")
    print("    key exchange and HMAC-SHA256 based symmetric encryption.")
    print("    The server only sees ciphertext -- it cannot read messages.")


def print_version():
    doc = read_app_doc("ttm2k")
    print(doc.get("version", __version__))


def run_server(args: list) -> int:
    host = "0.0.0.0"
    port = DEFAULT_PORT
    data_dir = "~/.ttm2k/server"

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--bind" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif arg in ("-p", "--port") and i + 1 < len(args):
            try:
                port = int(args[i + 1])
                if not (1 <= port <= 65535):
                    print("Error: port must be 1-65535", file=sys.stderr)
                    return 1
            except ValueError:
                print(f"Error: invalid port: {args[i + 1]}", file=sys.stderr)
                return 1
            i += 2
        elif arg == "--data-dir" and i + 1 < len(args):
            data_dir = args[i + 1]
            i += 2
        elif arg in ("-h", "--help"):
            print_help()
            return 0
        else:
            print(f"Error: unknown server option: {arg}", file=sys.stderr)
            return 1

    server = Server(host=host, port=port, data_dir=data_dir)
    server.start()
    return 0


def run_client(args: list) -> int:
    host = "127.0.0.1"
    port = DEFAULT_PORT

    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("-s", "--server") and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif arg in ("-p", "--port") and i + 1 < len(args):
            try:
                port = int(args[i + 1])
                if not (1 <= port <= 65535):
                    print("Error: port must be 1-65535", file=sys.stderr)
                    return 1
            except ValueError:
                print(f"Error: invalid port: {args[i + 1]}", file=sys.stderr)
                return 1
            i += 2
        else:
            print(f"Error: unknown option: {arg}", file=sys.stderr)
            return 1

    client = Client(host, port)
    if not client.connect():
        print(f"Error: could not connect to {host}:{port}", file=sys.stderr)
        print("Is the ttm2k server running?", file=sys.stderr)
        return 1

    ui = ChatUI(client)
    try:
        curses.wrapper(ui.run)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()

    return 0


def main():
    args = sys.argv[1:]

    if not args:
        return run_client([])

    if args[0] in ("-h", "--help", "help"):
        print_help()
        return 0

    if args[0] in ("-v", "--version"):
        print_version()
        return 0

    if args[0] == "server":
        return run_server(args[1:])

    return run_client(args)


if __name__ == "__main__":
    sys.exit(main())
