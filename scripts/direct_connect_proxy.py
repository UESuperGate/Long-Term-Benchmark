#!/usr/bin/env python3
"""Minimal direct CONNECT proxy for deterministic Gradle dependency downloads."""

from __future__ import annotations

import argparse
import select
import socket
import socketserver


class ConnectHandler(socketserver.StreamRequestHandler):
    timeout = 60

    def handle(self) -> None:
        request_line = self.rfile.readline(8192).decode("ascii", errors="replace").strip()
        if not request_line:
            return
        while True:
            line = self.rfile.readline(8192)
            if line in (b"\r\n", b"\n", b""):
                break
        method, target, _ = request_line.split(" ", 2)
        if method.upper() != "CONNECT":
            self.wfile.write(b"HTTP/1.1 405 Method Not Allowed\r\nConnection: close\r\n\r\n")
            return
        host, port_text = target.rsplit(":", 1)
        try:
            upstream = socket.create_connection((host.strip("[]"), int(port_text)), timeout=self.timeout)
        except OSError:
            self.wfile.write(b"HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n")
            return
        self.wfile.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        self.wfile.flush()
        try:
            while True:
                readable, _, _ = select.select([self.connection, upstream], [], [], self.timeout)
                if not readable:
                    break
                for source in readable:
                    target_socket = upstream if source is self.connection else self.connection
                    data = source.recv(65536)
                    if not data:
                        return
                    target_socket.sendall(data)
        finally:
            upstream.close()


class ThreadingProxy(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7898)
    args = parser.parse_args()
    with ThreadingProxy((args.host, args.port), ConnectHandler) as server:
        print(f"direct CONNECT proxy listening on {args.host}:{args.port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
