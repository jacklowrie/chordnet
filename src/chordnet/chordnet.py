"""chordnet.py: chordnet api."""
from typing import Tuple

from ._node import _Node
from .address import Address


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
            ip: IP address for the node. This should be the public IP
                (unless the whole ring is local, it is unlikely to be 127.0.0.1)
            port: Port number to listen on.
            interval: daemon interval (how often to 'sync' with the network)
        """
        self._node = _Node(ip, port, interval=interval)


    def create(self) -> None:
        """Create a new ChordNet network (a new "ring").

        This creates a new network with one node (this one), using the
        ip and port passed to the class constructor.
        """
        self._node.create()

    def join(self, known_ip: str, known_port: int) -> None:
        """Joins an existing ChordNet network (an existing ring).

        An existing chordnet can be joined through any node already on running
        on the ring. Note that this means a node cannot join itself to create
        a ring, and trivially, joining itself once running is meaningless.

        Args:
            known_ip: IP address of an existing node in the Chord ring.
            known_port: Port number of the existing node.
        """
        self._node.join(known_ip, known_port)

    def lookup(self, key: int) -> Tuple[str, int]:
        """Finds the ip address of the node responsible for the given key.

        Args:
            key: the value to look up (the hash)

        Returns: the IP address of the node responsible for the given key,
                 and the port that key is listening for ChordNet traffic on.
        """
        result: Address = self._node.find_successor(key)
        return result.ip, result.port

    def leave(self) -> None:
        """Leave the current network.

        Allows for a graceful shutdown of this node. This is optional and
        can help the ring recover faster. It should be called before
        program exit (or before a node shuts down in the network), but the
        network can still recover if this does not happen.
        """
        self._node.stop()
