"""chordnet.py: chordnet api."""
from ._node import _Node


class ChordNet:
    """Interface for interacting with Chord networks."""

    _node: _Node

    def __init__(self,
                 ip: str,
                 port: int,
                 interval:float=1.0,
    ) -> None:
        """Initializes a new Chord node.

        Args:
            ip: IP address for the node.
            port: Port number to listen on.
            daemon: whether to run the daemon.
            interval: daemon interval.
            debug: whether to print node state after every daemon run.
        """
        self._node = _Node(ip, port, interval=interval)


    def create(self) -> None:
        """Create a new ChordNet network (a new "ring").

        This creates a new network with one node (this one).
        """
        self._node.create()

    def join(self, known_ip: str, known_port: int) -> None:
        """Joins an existing ChordNet network (an existing ring).

        An existing chordnet can be joined through any node already on the ring.

        Args:
            known_ip (str): IP address of an existing node in the Chord ring.
            known_port (int): Port number of the existing node.
        """
        self._node.join(known_ip, known_port)

    def leave(self) -> None:
        """Leave the current network.

        Allows for a graceful shutdown of this node. Should be called before
        program exit, but the network can recover if this does not happen.
        """
        pass
