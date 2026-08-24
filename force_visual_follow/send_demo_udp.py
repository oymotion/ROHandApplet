import argparse
import json
import math
import socket
import time


def parse_args():
    parser = argparse.ArgumentParser(description="Send demo force frames to the visualizer.")
    parser.add_argument("--udp", default="127.0.0.1:27182")
    parser.add_argument("--hz", type=float, default=30.0)
    return parser.parse_args()


def parse_host_port(value: str):
    host, port = value.rsplit(":", 1)
    return host, int(port)


def make_scores(t: float):
    return {
        "thumb": 120.0 + 250.0 * (0.5 + 0.5 * math.sin(t * 1.3)),
        "index": 150.0 + 600.0 * (0.5 + 0.5 * math.sin(t * 1.1 + 1.0)),
        "middle": 200.0 + 700.0 * (0.5 + 0.5 * math.sin(t * 0.9 + 2.2)),
        "ring": 150.0 + 550.0 * (0.5 + 0.5 * math.sin(t * 1.4 + 3.0)),
        "little": 100.0 + 420.0 * (0.5 + 0.5 * math.sin(t * 1.7 + 4.2)),
        "palm": 50.0 + 1200.0 * (0.5 + 0.5 * math.sin(t * 0.7)),
    }


def main():
    args = parse_args()
    host, port = parse_host_port(args.udp)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    start = time.monotonic()
    interval = 1.0 / max(args.hz, 1.0)
    while True:
        t = time.monotonic() - start
        payload = json.dumps({"timestamp": time.time(), "scores": make_scores(t)}).encode("utf-8")
        sock.sendto(payload, (host, port))
        time.sleep(interval)


if __name__ == "__main__":
    main()
