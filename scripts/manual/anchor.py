"""anchor.py: creates and starts an anchor node for testing."""
import sys

import bpython

from chordnet import Node as ChordNode


def main() -> None:
    """Creates a new ring with this computer as the only node."""
    if len(sys.argv) != 3:
        print("usage: [uv run] python anchor.py ip_addr port_no")
        exit(1)

    ip = sys.argv[1]
    port = int(sys.argv[2])

    node = ChordNode(ip, port)
    # create (start) the ring
    node.create()
    print(f"Node created as \"node\": {node.address}", file=sys.stderr)
    bpython.embed(locals_=locals())
    node.stop()


if __name__ == '__main__':
    main()
