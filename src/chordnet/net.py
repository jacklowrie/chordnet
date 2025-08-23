"""net.py: Class for handling networking operations for nodes."""
import socket
import sys
import threading
from typing import Callable, Tuple

from .address import Address

callback = Callable[[str, list[str]], str| Address | None]

class _Net:

    _ip: str
    _port: int
    _request_handler: callback
    _running: bool
    _network_thread: threading.Thread | None
    server_socket: socket.socket | None
    network_thread: threading.Thread | None

    def __init__(self, ip: str, port: int, request_handler: callback) -> None:
        self._ip = ip
        self._port = port
        self._request_handler = request_handler
        self._running = False
        self._network_thread = None
        self.server_socket = None
        self.network_thread = None

    def start(self) -> None:
        """Starts the Chord node's network listener.

        Begins accepting incoming network connections in a separate thread.
        """
        self._running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self._ip, self._port))
        self.server_socket.listen(5)

        # Start network listener in a separate thread
        self.network_thread = threading.Thread(
            target=self._listen_for_connections,
            daemon=True
        )
        self.network_thread.start()



    def stop(self) -> None:
        """Gracefully stops the Chord node's network listener.

        Closes the server socket and waits for the network thread to terminate.
        """
        self._running = False
        if self.server_socket:
            self.server_socket.close()
        if self.network_thread:
            self.network_thread.join()



    def send_request(
        self, dest_node: Address, method: str, *args: object
    ) -> str | None:
        """Sends a network request to a specific node.

        Args:
            dest_node (Address): The network address to send the request to
            method (str): The method/request type to invoke
            *args: Variable arguments to pass with the request

        Returns:
            The response from the target node, or None if communication fails
        """
        try:
            # Create a socket with a timeout
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Set a reasonable timeout (e.g., 5 seconds)
                sock.settimeout(5)

                # Connect to the target node
                sock.connect((dest_node.ip, dest_node.port))

                # Prepare the request
                # Convert all args to strings and join with ':'
                request_args = ':'.join(str(arg) for arg in args)
                request = f"{method}:{request_args}"
                if (method == "TRACE_SUCCESSOR"):
                    print ('[SENDING TRACE REQ]', request)
                # Send the request
                sock.send(request.encode())

                # Receive the response
                response: str = sock.recv(1024).decode()

                return response

        except socket.timeout:
            print("Request timed out", file=sys.stderr)
            return None
        except ConnectionRefusedError:
            print("Connection refused", file=sys.stderr)
            return None
        except Exception as e:
            print(f"Network request error: {e}", file=sys.stderr)
            return None




    def _listen_for_connections(self) -> None:
        """Continuously listens for incoming network connections.

        Accepts client connections and spawns a thread to handle
        each connection.
        """
        while self._running:
            try:
                client_socket: socket.socket | None = None
                address: Tuple[str, int] | None = None

                if self.server_socket:
                    client_socket, address = self.server_socket.accept()
                # Handle each connection in a separate thread
                threading.Thread(
                    target=self._handle_connection,
                    args=(client_socket,),
                    daemon=True
                ).start()
            except Exception as e:
                if self._running:
                    print(f"Error accepting connection: {e}\n")
                    sys.stderr.write(f"Error accepting connection: {e}\n")
                    sys.stderr.flush()



    def _handle_connection(self, client_socket: socket.socket) -> None:
        """Processes an individual network connection.

        Args:
            client_socket (socket): The socket connection to handle.
        """
        try:
            # Receive request
            request: str = client_socket.recv(1024).decode()

            # Parse request
            method, *args = request.split(':')

            if method == 'TRACE_SUCCESSOR':
                print(f"[NET]Received request: {request}", file=sys.stderr)

            # Dispatch to appropriate method
            response = self._request_handler(method, args)

            if method == 'TRACE_SUCCESSOR':
                print(f"[NET]Sent response: {response}", file=sys.stderr)

            # Send response
            client_socket.send(str(response).encode())
        except Exception as e:
            sys.stderr.write(f"Error handling connection: {e}\n")
            sys.stderr.flush()
        finally:
            client_socket.close()
