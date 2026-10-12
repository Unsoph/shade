"""Minimal systemd notify client (no dependencies).

Lets a `Type=notify` unit with WatchdogSec= restart the supervisor itself
if it hangs. A no-op when not run under systemd.
"""

import os
import socket


def notify(message: str) -> bool:
    """Send e.g. 'READY=1' or 'WATCHDOG=1'. Returns True if delivered."""
    addr = os.environ.get("NOTIFY_SOCKET")
    if not addr:
        return False
    if addr.startswith("@"):  # abstract socket
        addr = "\0" + addr[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(addr)
            sock.sendall(message.encode())
        return True
    except OSError:
        return False
