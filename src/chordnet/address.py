"""address.py: class that represents a ring address."""

import hashlib


class Address:
    """Represents a network address with a unique key in a distributed system.

    This class encapsulates the network location (IP and port) and a unique
    identifier (key) used for routing and comparison in Chord.

    Attributes:
        key (int): A unique identifier for the node in the distributed system.
        ip (str): The IP address of the node.
        port (int): The network port number of the node.

    Provides methods for equality comparison and string representation.
    """
    __slots__= ('key', 'ip', 'port')
    _M: int = 16
    _SPACE: int = 2 ** _M


    def __init__(self, ip: str, port: int) -> None:
        """Creates a new Address object.

        Args:
            ip: ip address of the node.
            port: port of the node.
        """
        self.key = self._hash(f"{ip}:{port}")
        self.ip = ip
        self.port = port



    def _hash(self, key: str) -> int:
        """Generates a consistent hash for identifiers.

        Args:
            key: Input string to hash.

        Returns:
            int: Hashed identifier within the hash space.
        """
        return int(hashlib.sha1(key.encode()).hexdigest(), 16) % Address._SPACE



    def __eq__(self, other: object) -> bool:
        """Checks for equality.

        Args:
            other: other object to check.

        Returns:
            true if the other address is identical, false otherwise.
        """
        if not isinstance(other, Address):
            return NotImplemented
        return (self.ip == other.ip and
                self.port == other.port and
                self.key == other.key)



    def __repr__(self) -> str:
        """String representation of this address.

        Returns:
            String format for this address.
        """
        return f"{self.key}:{self.ip}:{self.port}"
