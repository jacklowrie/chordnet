"""joiner.py: creates a joining node for debugging."""
import sys

import bpython
from step import step  #type: ignore

from chordnet import Node as ChordNode


def main() -> None:
    """Creates a new ring with this computer as the only node."""
    if len(sys.argv) != 5:
        print("usage: [uv run] python " \
              "joiner.py this_ip this_port target_ip target_port")
        exit(1)

    # Get IP and port from command line arguments
    ip = sys.argv[1]
    port = int(sys.argv[2])
    target_ip = sys.argv[3]
    target_port = int(sys.argv[4])

    # Create and join node
    node = ChordNode(ip, port)
    node.join(target_ip, target_port)
    repl_locals = {
        'node': node,
        'step': step,
    }
    print("starting repl. access `node`, advance with `step(node)`")
    bpython.embed(locals_=repl_locals)
    node.stop()


if __name__ == '__main__':
    main()
