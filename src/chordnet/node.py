"""node.py: Represents a node on a ring."""
import sys
from typing import Callable, Tuple

from .address import Address
from .net import _Net

callback_t = Callable[[str, list[str]], str | Address | None]
class Node:
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
    is_running: bool

    def __init__(self, ip: str, port: int) -> None:
        """Initializes a new Chord node.

        Args:
            ip (str): IP address for the node.
            port (int): Port number to listen on.
        """
        self.address = Address(ip, port)

        # Network topology management
        self.predecessor = None
        self.finger_table = [None] * Address._M
        self._next = 0 # for fix_fingers (iterating through finger_table)

        # Networking
        self._net = _Net(ip, port, self._process_request)
        self.is_running = False

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
                print(msg, file=sys.stderr)
            else:
                raise ValueError("Failed to find successor. Join failed")

            self.start()
            self.fix_fingers()


        except Exception as e:
            print(f"Join failed: {e}")
            raise



    def fix_fingers(self) -> None:
        """Incrementally updates one entry in the node's finger table."""
        if not self.successor():  # Ensure there's a valid successor
            return

        # Update the finger table entry pointed to by _next
        gap = (2 ** self._next) % (2 ** Address._M)

        start = self.address.key + gap
        #print(f"fixing finger {self._next}. gap is {gap}, " \
        #"start of interval is: {start}")

        try:
            # Find the successor for this finger's start position
            responsible_node = self.find_successor(start)
            self.finger_table[self._next] = responsible_node
        except Exception as e:
            print(f"fix_fingers failed for finger {self._next}: {e}")

        # Move to the next finger table entry, wrapping around if necessary
        self._next = (self._next + 1) % Address._M
    '''
    def _run_fix_fingers(self, interval=1.0):
        """
        Periodically invokes fix_fingers every `interval` seconds.

        Args:
            interval (float): Time interval between updates (in seconds).
        """
        self.fix_fingers()
        # Schedule the next execution
        self._fix_fingers_timer = threading.Timer(
                        interval, self._run_fix_fingers, args=[interval])
        self._fix_fingers_timer.start()

    def start_periodic_tasks(self, interval=1.0):
        """
        Starts periodic tasks for the node, including fix_fingers.

        Args:
            interval (float): Time interval between periodic calls.
        """
        if self._fix_fingers_timer and self._fix_fingers_timer.is_alive():
            # Timer is already running, no need to start again
            print("Periodic tasks are already running.", file=sys.stderr)
            return
        self.is_running = True
        self._run_fix_fingers(interval)

    def stop_periodic_tasks(self):
        """
        Stops periodic tasks for the node gracefully.
        """
        if self._fix_fingers_timer:
            self._fix_fingers_timer.cancel()
            self._fix_fingers_timer = None
        self.is_running = False
    '''
    def log_finger_table(self) -> None:
        """Logs the entire finger table to the log file."""
        message = "Current Finger Table:\n"
        for i, finger in enumerate(self.finger_table):
            message += f"  Finger[{i}] -> {finger}\n"

        print(message, file=sys.stderr)

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
            print(f"Find successor failed: {e}")
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
        if curr_successor is None:
            return

        x = None

        try:
            # Get the predecessor of the current successor
            #print(f"stabilize: checking successor {self.successor().key}" \
            #for predecessor", file=sys.stderr)
            x_response = self._net.send_request(
                curr_successor, 'GET_PREDECESSOR')

            #print(f"stabilize: predecessor found: {x_response}",
            #file=sys.stderr)
            x = self._parse_address(x_response)

            if x and self._is_between(
                    self.address.key, curr_successor.key, x.key
            ):
                self.finger_table[0] = x
                #print(
                #f"stabilize: updated successor to {self.successor().key}",
                #file=sys.stderr)
            # otherwise, we just notify them that we exist.
            # This is usually for the first joiner to a ring.

            #print(f"Node {self.address} - Updated Successor:" \
            #"{self.successor()}, Predecessor: {self.predecessor}",
            #file=sys.stderr)

        except Exception as e:
            print(f"Stabilize failed: {e}", file=sys.stderr)
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
            print(f"Notify failed: {e}", file=sys.stderr)
            return False


    def start(self) -> None:
        """Starts the Chord node's network listener.

        Begins accepting incoming network connections in a separate thread.
        """
        self._net.start()



    def stop(self) -> None:
        """Gracefully stops the Chord node's network listener.

        Closes the server socket and waits for the network thread to terminate.
        """
        self._net.stop()



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
        if not self.predecessor or self._is_between(
                self.predecessor.key, self.address.key, notifying_node.key
        ):
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
            print(f"Raw response: {response}", file=sys.stderr) # Debugging line
            assert response is not None
            parts = response.split(":")
            if len(parts) != 4:
                raise ValueError(f"Invalid response format: {response}")
            node_key, node_ip, node_port, hops = parts
            # resolved_node = Address(node_ip, int(node_port))
            # resolved_node.key = int(node_key)
            response_split = response.split(":")
            address = ':'.join(response_split[:-1])
            print ("[trace]Joined Address :", address)
            # address = '':'.join(response[:2])
            return address, int(hops)+1

            # return self._parse_address(response), hops

        except Exception as e:
            print(f"trace successor failed: {e}")
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
                print ("[NODE] Current ID ", id, "Current hops ", hops)
                successor, hops = self.trace_successor(id, hops)

                print ("SUCCESSSOR NODE :", successor, "HOPS :", hops)
                returnString = f"{successor}:{hops}"
                return returnString
            except Exception as e:
                print(f"TRACE_SUCCESSOR error: {e}", file=sys.stderr)
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
                return "OK" if self._be_notified(notifier) else "IGNORED"

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
