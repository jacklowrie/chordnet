"""node.py: Represents a node on a ring."""
import threading
from typing import Callable, Tuple

from loguru import logger as log

from ._net import _Net
from .address import Address

callback_t = Callable[[str, list[str]], str | Address | None]
class _Node:
    """Implements a Chord distributed hash table node.

    This is meant to run on a host and handle any chord-related
    traffic. Applications should make one instance of this class,
    then use the methods to manage/interact with other nodes on
    the chord ring.

    Of particular note, this class is only responsible for making,
    managing, and locating nodes (and therefore locating the node
    that is responsible for a key). In a key-value pair,
    It does NOT handle the management of values at all: that is
    an application-level responsibility.

    Attributes:
        address (Address): node address info (key, ip, port).
        successor (Address): The next node in the Chord ring.
        predecessor (Address): The previous node in the Chord ring.
        finger_table (list): Routing table for efficient lookup.
    """

    address: Address
    predecessor: Address | None
    finger_table: list[Address | None]
    _next: int
    _net: _Net
    _timer: threading.Timer | None
    is_running: bool
    _use_daemon: bool
    _interval: float
    _debug: bool

    def __init__(self,
                 ip: str,
                 port: int,
                 daemon:bool=True,
                 interval:float=1.0,
                 debug:bool=False
    ) -> None:
        """Initializes a new Chord node.

        Args:
            ip: IP address for the node.
            port: Port number to listen on.
            daemon: whether to run the daemon.
            interval: daemon interval.
            debug: whether to print node state after every daemon run.
        """
        self.address = Address(ip, port)

        # Network topology management
        self.predecessor = None
        self.finger_table = [None] * Address._M
        self._next = 0 # for fix_fingers (iterating through finger_table)

        # Networking
        self._net = _Net(ip, port, self._process_request)
        self.is_running = False

        self._use_daemon = daemon
        self._interval = interval
        self._debug = debug
        self._timer = None

    def successor(self) -> Address | None:
        """Alias for self.finger_table[0]."""
        return self.finger_table[0]
        # return self.finger_table[0] if self.finger_table[0] else self.address

    def create(self) -> None:
        """Creates a new Chord ring with this node as the initial member.

        The node sets itself as its own successor and initializes the
        finger table.
        """
        self.predecessor = None
        self.finger_table[0] = self.address
        self.start()
        self.fix_fingers()



    def join(self, known_ip: str, known_port: int) -> None:
        """Joins an existing Chord ring through a known node's IP and port.

        Args:
            known_ip (str): IP address of an existing node in the Chord ring.
            known_port (int): Port number of the existing node.
        """
        self.predecessor = None

        # Create an Address object for the known node
        known_node_address = Address(known_ip, known_port)

        try:
            # Send a find_successor request to the known node for
            #this node's key
            response: str | None = self._net.send_request(
                known_node_address,
                'FIND_SUCCESSOR',
                self.address.key
            )

            if response:
                self.finger_table[0] = self._parse_address(response)
                msg = f"Node {self.address.key} joined the ring. " \
                        "Successor: {self.successor().key}"
                log.info(msg)
            else:
                raise ValueError("Failed to find successor. Join failed")

            self.start()
            self.fix_fingers()


        except Exception as e:
            log.info(f"Join failed: {e}")
            raise



    def fix_fingers(self) -> None:
        """Incrementally updates one entry in the node's finger table."""
        if not self.successor():  # Ensure there's a valid successor
            return

        # Update the finger table entry pointed to by _next
        gap = (2 ** self._next) % (2 ** Address._M)

        start = self.address.key + gap
        #log.info(f"fixing finger {self._next}. gap is {gap}, " \
        #"start of interval is: {start}")

        try:
            # Find the successor for this finger's start position
            responsible_node = self.find_successor(start)
            self.finger_table[self._next] = responsible_node
        except Exception as e:
            log.debug(f"fix_fingers failed for finger {self._next}: {e}")

        # Move to the next finger table entry, wrapping around if necessary
        self._next = (self._next + 1) % Address._M

    def _daemon(self) -> None:
        """Runs fix_fingers and stabilize periodically.

        Args:
            interval: Time interval between periodic calls.
            debug: Whether to print node state
        """
        if self._use_daemon and self.is_running:
            try:
                self.stabilize()
                self.fix_fingers()
                if self._debug:
                    print(f"pred: {self.predecessor}, succ: {self.successor()}")
                    print(self.finger_table)

            except Exception as e:
                # Catch any unhandled exception within the daemon's tasks
                # and log it properly. This is crucial for debugging.
                log.error(
                    f"Unhandled exception in daemon for {self.address}: {e}"
                )
                # You might want to optionally stop the daemon here
                # if continuous failures are problematic
                # self.stop()

            finally:
                # Always reschedule the timer, even if an exception occurred,
                # unless you decided to stop the daemon above.
                if self.is_running:
                    self._timer = threading.Timer(self._interval, self._daemon)
                    self._timer.daemon = True
                    self._timer.start()



    def log_finger_table(self) -> None:
        """Logs the entire finger table to the log file."""
        message = "Current Finger Table:\n"
        for i, finger in enumerate(self.finger_table):
            message += f"  Finger[{i}] -> {finger}\n"

        log.info(message)

    def find_successor(self, id: int) -> Address:
        """Finds the successor node for a given identifier.

        Args:
            id: Identifier to find the successor for.

        Returns:
            The address of the node responsible for the given identifier.
        """
        # If id is between this node and its successor
        curr_successor = self.successor()
        if curr_successor and self._is_key_in_range(id):
            return curr_successor

        # Find closest preceding node in my routing table.
        closest_node = self.closest_preceding_finger(id)

        # If closest preceding node is me,
        # then I need to return my own successor
        if closest_node == self.address:
            return curr_successor if curr_successor else self.address

        # If it's not me, forward my request to the closer node and
        # then return what they send back
        try:
            response = self._net.send_request(
                closest_node,
                'FIND_SUCCESSOR',
                id
            )
            # return self._parse_address(response)
            successor = self._parse_address(response)
            return successor if successor else self.address

        except Exception as e:
            log.info(f"Find successor failed: {e}")
            # Fallback to local successor if network request fails
            return curr_successor if curr_successor else self.address


    def closest_preceding_finger(self, id: int) -> Address:
        """Finds the closest known preceding node for a given id.

        Args:
            id (int): Identifier to find the closest preceding node
                      for (the key).

        Returns:
            Address: The address of closest preceding node in the finger table.
        """
        # Search finger table in reverse order
        for finger in reversed(self.finger_table):
            if finger and self._is_between(self.address.key, id, finger.key):
                return finger

        # This is only possible if there are no finger_table entries
        return self.address



    def check_predecessor(self) -> None:
        """Checks if the predecessor node has failed.

        Sets predecessor to None if unresponsive.
        """
        if not self.predecessor:
            return

        try:
            # Try to send a simple request to the predecessor
            response = self._net.send_request(
                self.predecessor,
                'PING'
            )

            # If no response or invalid response, consider node failed
            if not response or response != 'ALIVE':
                self.predecessor = None

        except Exception:
            # Any network error means the predecessor is likely down
            self.predecessor = None



    def stabilize(self) -> None:
        """Periodically verifies and updates the node's successor.

        This method ensures the correctness of the Chord ring topology.
        """
        # Pseudocode from the paper
        # x = successor's predecessor
        # if x is between this node and its successor
        #     set successor to x
        # notify successor about this node
        curr_successor = self.successor()
        if curr_successor is None or curr_successor == self.address:
            # if we have a predecessor, then its a 2 node ring
            # complete the circle
            if self.predecessor and self.predecessor != self.address:
                self.finger_table[0] = self.predecessor
            return



        x = None

        try:
            # Get the predecessor of the current successor
            #log.info(f"stabilize: checking successor {self.successor().key}" \
            #for predecessor")
            x_response = self._net.send_request(
                curr_successor, 'GET_PREDECESSOR')

            #log.info(f"stabilize: predecessor found: {x_response}",
            #file=sys.stderr)
            x = self._parse_address(x_response)

            if x and self._is_between(
                    self.address.key, curr_successor.key, x.key
            ):
                self.finger_table[0] = x
                #log.info(
                #f"stabilize: updated successor to {self.successor().key}",
                #file=sys.stderr)
            # otherwise, we just notify them that we exist.
            # This is usually for the first joiner to a ring.

            #log.info(f"Node {self.address} - Updated Successor:" \
            #"{self.successor()}, Predecessor: {self.predecessor}",
            #file=sys.stderr)

        except Exception as e:
            log.info(f"Stabilize failed: {e}")
        finally:
            self.notify(self.successor())


    def notify(self, potential_successor: Address | None)-> bool:
        """Notifies a node about a potential predecessor.

        Args:
            potential_successor: Node that might be the successor.

        Returns:
            True if the notification is received (regardless of whether
            the update occurred), False otherwise
        """
        if potential_successor is None:
            return False

        try:
            # Send notification to potential successor
            response = self._net.send_request(
                potential_successor,
                'NOTIFY',
                f"{self.address.key}:{self.address.ip}:{self.address.port}"
            )
            if response == "OK" or response == "IGNORED":
                return True
            else:
                return False
        except Exception as e:
            log.info(f"Notify failed: {e}")
            return False


    def start(self) -> None:
        """Starts the Chord node's daemon and network listener.

        Begins accepting incoming network connections in a separate thread.

        Args:
            daemon: whether to run a daemon
                    (runs fix_fingers and stabilize periodically
            interval: interval daemon sleeps for (only relevant if daemon=True)
            debug: whether to print the state of the node
                    (again only relevant to daemon)
        """
        self._net.start()
        self.is_running = True
        if self._use_daemon:
            self._daemon()



    def stop(self) -> None:
        """Gracefully stops the Chord node's daemon and network listener.

        Closes the server socket and waits for the network thread to terminate.
        """
        self._net.stop()
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self.is_running = False




    def _is_key_in_range(self, key: int) -> bool:
        """Checks if a key is between this node and its successor.

        Args:
            key (int): Identifier to check.

        Returns:
            bool: True if the key is in the node's range, False otherwise.
        """
        successor = self.successor()
        if successor is None: # no successor case
            return True

        if self.address.key < successor.key:
            # Normal case: key is strictly between node and successor
            return self.address.key < key < successor.key
        else:  # Wrap around case
            return key > self.address.key or key < successor.key



    def _is_between(self, start:int, end:int, key:int) -> bool:
        """Checks if a node is between two identifiers in the Chord ring.

        Args:
            start (int): Starting identifier.
            end (int): Ending identifier.
            key (int): Node identifier to check.

        Returns:
            bool: True if the node is between start and end, False otherwise.
        """
        if start == end: # this shouldn't happen
            return False
        if start < end:
            return start < key < end
        else:  # Wrap around case
            return key > start or key < end



    def _be_notified(self, notifying_node: Address) -> bool:
        """Handles a notification from another node.

        The notification is about potentially being its predecessor.

        Args:
            notifying_node: Node that is notifying this node.

        Returns:
            True if the node was accepted as a predecessor, False otherwise.
        """
        # Update predecessor if necessary
        my_key = self.address.key
        their_key = notifying_node.key
        if not self.predecessor \
                or self.predecessor == self.address \
                or self._is_between(self.predecessor.key, my_key, their_key):
            self.predecessor = notifying_node
            return True
        else:
            return False

    def trace_successor(
        self, id: int, curr_hops: int
    ) -> Tuple[str, int]:
        """Finds the successor node for a given identifier.

        Args:
            id: Identifier to find the successor for.
            curr_hops: number of hops taken so far.

        Returns:
            The address of the node responsible for the given identifier.
        """
        # If id is between this node and its successor
        if self._is_key_in_range(id):
            return str(self.successor()), curr_hops
            # return curr_hops

        # Find closest preceding node in my routing table.
        closest_node = self.closest_preceding_finger(id)

        # If closest preceding node is me, then I need to return
        # my own successor
        if closest_node == self.address:
            return str(self.successor()), curr_hops

        # If it's not me, forward my request to the closer node and
        # then return what they send back
        try:
            response = self._net.send_request(
                closest_node,
                'TRACE_SUCCESSOR',
                id,
                curr_hops
            )
            log.debug(f"Raw response: {response}") # Debugging line
            assert response is not None
            parts = response.split(":")
            if len(parts) != 4:
                raise ValueError(f"Invalid response format: {response}")
            node_key, node_ip, node_port, hops = parts
            # resolved_node = Address(node_ip, int(node_port))
            # resolved_node.key = int(node_key)
            response_split = response.split(":")
            address = ':'.join(response_split[:-1])
            log.info("[trace]Joined Address :", address)
            # address = '':'.join(response[:2])
            return address, int(hops)+1

            # return self._parse_address(response), hops

        except Exception as e:
            log.info(f"trace successor failed: {e}")
            # Fallback to local successor if network request fails
            return str(self.successor()), -1


    def _process_request(
        self, method: str, args: list[str]
    ) -> str | Address | None:
        """Routes incoming requests to appropriate methods.

        Args:
            method (str): The method to be called.
            args (list): Arguments for the method.

        Returns:
            The result of the method call or an error message.
        """
        if method == "PING":
            return "ALIVE"
        elif method == 'FIND_SUCCESSOR':
            return self.find_successor(int(args[0]))
        elif method == "TRACE_SUCCESSOR":
            try:
                id, hops = int(args[0]), int(args[1])
                log.info("[NODE] Current ID ", id, "Current hops ", hops)
                successor, hops = self.trace_successor(id, hops)

                log.info("SUCCESSSOR NODE :", successor, "HOPS :", hops)
                returnString = f"{successor}:{hops}"
                return returnString
            except Exception as e:
                log.info(f"TRACE_SUCCESSOR error: {e}")
                return "ERROR:Invalid TRACE_SUCCESSOR Request"

        elif method == 'GET_PREDECESSOR':
            return self.predecessor if self.predecessor else "nil"
        elif method == 'NOTIFY':
            # Parse the notifying node's details
            try:
                if len(args) < 3:
                    return "INVALID_NODE"

                notifier = self._parse_address(':'.join(
                    [args[0], args[1], args[2]])
                )
                assert notifier is not None
                new_predecessor = self._be_notified(notifier)
                return "OK" if new_predecessor else "IGNORED"

            except (ValueError, AssertionError):
                return "INVALID_NODE"
        else:
            return "INVALID_METHOD"


    def _parse_address(self, response: str | None) -> Address | None:
        """Parses a network response into an Address object.

        Only addresses are expected.

        Args:
            response (str): Serialized node address in "key:ip:port" format.

        Returns:
            Address: Parsed Address object.

        Raises:
            ValueError: If the response format is invalid.
        """
        if response == "nil":
            return None
        assert response
        parts = response.split(':')
        if len(parts) == 3:
            address = Address(parts[1], int(parts[2]))
            address.key = int(parts[0])

            return address
        else:
            raise ValueError("Invalid node address response format")



    def __repr__(self) -> str:
        """Provides a string representation of the Chord node.

        Returns:
            str: A descriptive string of the node's key properties.
        """
        return f"ChordNode(key={self.address.key})"
