"""test_net.py: tests for the _Net class.

NOTE: many of these tests were AI generated as regression tests, in preparation
for refactoring.
"""
import socket
import sys
from typing import Generator, List, Optional, Tuple
from unittest.mock import MagicMock, Mock, patch

import pytest

from chordnet._net import _Net


def test_net_initialization() -> None:
    """Verifies the initial state of a _Net instance.

    Ensures all attributes are set to their expected default values
    upon object creation.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    assert net._ip == "localhost"
    assert net._port == 8000
    assert net._request_handler == mock_handler
    assert net._running is False
    assert net._network_thread is None
    assert net.server_socket is None
    assert net.network_thread is None


@patch("socket.socket")
@patch("threading.Thread")
def test_net_start(mock_thread: MagicMock, mock_socket: MagicMock) -> None:
    """Tests the start method of the _Net class.

    Verifies that start() correctly initializes the server socket,
    binds to the specified address and port, starts listening,
    and launches the network listener thread.

    Args:
        mock_thread: A MagicMock for threading.Thread.
        mock_socket: A MagicMock for socket.socket.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    net.start()

    assert net._running is True
    assert net.server_socket == mock_socket.return_value
    assert net.network_thread == mock_thread.return_value

    # Verify socket was created and bound
    mock_socket.return_value.bind.assert_called_once_with(
        ("localhost", 8000)
    )
    mock_socket.return_value.listen.assert_called_once_with(5)

    # Verify thread was started
    mock_thread.assert_called_once_with(
        target=net._listen_for_connections,
        daemon=True
    )
    mock_thread.return_value.start.assert_called_once()


def test_net_handle_connection() -> None:
    """Tests the _handle_connection method of the _Net class.

    Verifies that it correctly receives a request, calls the
    request handler, sends a response, and closes the socket.
    """
    mock_socket: MagicMock = Mock()
    mock_handler: Mock = Mock(return_value="test_response")

    net: _Net = _Net("localhost", 8000, mock_handler)

    # Simulate receiving a request
    mock_socket.recv.return_value = b"TEST:arg1:arg2"

    net._handle_connection(mock_socket)

    # Verify handler was called correctly
    mock_handler.assert_called_once_with("TEST", ["arg1", "arg2"])

    # Verify response was sent
    mock_socket.send.assert_called_once_with(b"test_response")

    # Verify socket was closed
    mock_socket.close.assert_called_once()


def test_net_stop() -> None:
    """Tests the stop method of the _Net class.

    Verifies that it correctly sets the running flag to False,
    closes the server socket, and joins the network thread.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    # Mock the thread and socket
    net.network_thread = Mock()
    net.server_socket = Mock()
    net._running = True # Simulate that it was running

    net.stop()

    assert net._running is False # Should be set to False

    # Verify socket was closed
    net.server_socket.close.assert_called_once()

    # Verify thread was joined
    net.network_thread.join.assert_called_once()


def test_send_request_success() -> None:
    """Tests the send_request method for a successful network request.

    Verifies that a request is sent and a response is received,
    and all socket operations are performed correctly.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate a successful request
    with patch("socket.socket") as mock_socket:
        mock_socket_instance: MagicMock = Mock()
        mock_socket.return_value.__enter__.return_value = \
            mock_socket_instance

        # Simulate successful connection and response
        mock_socket_instance.recv.return_value = b"RESPONSE"

        # Call send_request
        # Using a Mock object for Address with required attributes
        dest_address: Mock = Mock(ip="localhost", port=8001)
        response: Optional[str] = net.send_request(
            dest_address, "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response == "RESPONSE"

        # Verify socket methods were called correctly
        mock_socket_instance.settimeout.assert_called_once_with(5)
        mock_socket_instance.connect.assert_called_once_with(
            ("localhost", 8001)
        )
        mock_socket_instance.send.assert_called_once_with(b"TEST:arg1:arg2")
        mock_socket_instance.recv.assert_called_once_with(1024)


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_timeout(mock_stderr_flush: MagicMock,
                             mock_stderr_write: MagicMock) -> None:
    """Tests the send_request method for a socket timeout.

    Verifies that None is returned and an error message is written to stderr.

    Args:
        mock_stderr_flush: Mock for sys.stderr.flush.
        mock_stderr_write: Mock for sys.stderr.write.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate a timeout
    with patch("socket.socket") as mock_socket:
        mock_socket_instance: MagicMock = Mock()
        mock_socket.return_value.__enter__.return_value = \
            mock_socket_instance

        # Simulate a timeout
        mock_socket_instance.connect.side_effect = socket.timeout

        dest_address: Mock = Mock(ip="localhost", port=8001)
        response: Optional[str] = net.send_request(
            dest_address, "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response is None

        # Assert that 'write' was called and contained the message
        assert mock_stderr_write.call_count >= 1
        messages_written: List[str] = [
            call_args[0][0] for call_args in mock_stderr_write.call_args_list
        ]
        assert any("Request timed out" in msg for msg in messages_written)


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_connection_refused(mock_stderr_flush: MagicMock,
                                         mock_stderr_write: MagicMock) -> None:
    """Tests the send_request method for a connection refused error.

    Verifies that None is returned and an error message is written to stderr.

    Args:
        mock_stderr_flush: Mock for sys.stderr.flush.
        mock_stderr_write: Mock for sys.stderr.write.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate connection refused
    with patch("socket.socket") as mock_socket:
        mock_socket_instance: MagicMock = Mock()
        mock_socket.return_value.__enter__.return_value = \
            mock_socket_instance

        # Simulate connection refused
        mock_socket_instance.connect.side_effect = ConnectionRefusedError

        dest_address: Mock = Mock(ip="localhost", port=8001)
        response: Optional[str] = net.send_request(
            dest_address, "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response is None
        # Assert that 'write' was called and contained the message
        assert mock_stderr_write.call_count >= 1
        messages_written: List[str] = [
            call_args[0][0] for call_args in mock_stderr_write.call_args_list
        ]
        assert any("Connection refused" in msg for msg in messages_written)


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_listen_for_connections_accept_exception(
    mock_stderr_flush: MagicMock, mock_stderr_write: MagicMock
) -> None:
    """Tests _listen_for_connections when server_socket.accept() fails.

    Verifies that the exception is logged to stderr and the loop terminates
    if _running flag is set to False by the side effect.

    Args:
        mock_stderr_flush: Mock for sys.stderr.flush.
        mock_stderr_write: Mock for sys.stderr.write.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    mock_server_socket: MagicMock = Mock()
    net.server_socket = mock_server_socket # Manually set the mock server_socket
    net._running = True # Ensure the loop runs at least once

    def controlled_accept_side_effect_generator() -> \
             Generator[Exception | Tuple[MagicMock, MagicMock], None, None]:
        """Generator to simulate controlled accept side effects."""
        yield Exception("Simulated accept error") # First call raises
        # If _listen_for_connections tried to accept again,
        # this next line would execute, making the loop terminate.
        net._running = False

        # Return a valid connection, to avoid further errors
        yield Mock(), Mock()

    mock_server_socket.accept.side_effect = \
        controlled_accept_side_effect_generator()

    # Call _listen_for_connections directly to control its execution
    net._listen_for_connections()

    # Assertions for stderr output
    assert mock_stderr_write.call_count >= 1
    messages_written: List[str] = [
        call_args[0][0] for call_args in mock_stderr_write.call_args_list
    ]
    assert any(
        "Error accepting connection: Simulated accept error" in msg
        for msg in messages_written
    )
    assert net._running is False # Verify the loop has stopped


def test_net_handle_connection_no_args() -> None:
    """Tests _handle_connection when the request has no arguments.

    Verifies that the request handler is called with an empty list for args.
    """
    mock_socket: MagicMock = Mock()
    mock_handler: Mock = Mock(return_value="test_response_no_args")

    net: _Net = _Net("localhost", 8000, mock_handler)

    # Simulate receiving a request with no args
    mock_socket.recv.return_value = b"TEST"

    net._handle_connection(mock_socket)

    # Verify handler was called correctly with an empty list for args
    mock_handler.assert_called_once_with("TEST", [])

    # Verify response was sent
    mock_socket.send.assert_called_once_with(b"test_response_no_args")

    # Verify socket was closed
    mock_socket.close.assert_called_once()


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_net_handle_connection_handler_exception(
    mock_stderr_flush: MagicMock, mock_stderr_write: MagicMock
) -> None:
    """Tests _handle_connection when the request handler raises an exception.

    Verifies that the exception is logged to stderr, no response is sent,
    and the socket is still closed.

    Args:
        mock_stderr_flush: Mock for sys.stderr.flush.
        mock_stderr_write: Mock for sys.stderr.write.
    """
    mock_socket: MagicMock = Mock()
    mock_handler: Mock = Mock(side_effect=Exception("Handler error"))

    net: _Net = _Net("localhost", 8000, mock_handler)

    mock_socket.recv.return_value = b"TEST:arg1"

    net._handle_connection(mock_socket)

    mock_handler.assert_called_once_with("TEST", ["arg1"])
    mock_socket.send.assert_not_called() # Response should not be sent

    mock_socket.close.assert_called_once() # Socket should still be closed

    assert mock_stderr_write.call_count >= 1
    messages_written: List[str] = [
        call_args[0][0] for call_args in mock_stderr_write.call_args_list
    ]
    assert any("Error handling connection: Handler error" in msg
               for msg in messages_written)
    mock_stderr_flush.assert_called_once()


def test_send_request_no_args() -> None:
    """Tests send_request when the method has no arguments.

    Verifies that the request string is formatted correctly with no args.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    with patch("socket.socket") as mock_socket:
        mock_socket_instance: MagicMock = Mock()
        mock_socket.return_value.__enter__.return_value = \
            mock_socket_instance
        mock_socket_instance.recv.return_value = b"RESPONSE_NO_ARGS"

        dest_address: Mock = Mock(ip="localhost", port=8001)
        response: Optional[str] = net.send_request(
            dest_address, "NO_ARGS_METHOD"
        )

        assert response == "RESPONSE_NO_ARGS"
        mock_socket_instance.send.assert_called_once_with(
            b"NO_ARGS_METHOD:"
        )


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_general_exception(mock_stderr_flush: MagicMock,
                                        mock_stderr_write: MagicMock) -> None:
    """Tests send_request when a general exception occurs during the request.

    Verifies that None is returned and the exception is logged to stderr.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    with patch("socket.socket") as mock_socket:
        mock_socket_instance: MagicMock = Mock()
        mock_socket.return_value.__enter__.return_value = \
            mock_socket_instance

        # Simulate a generic exception during connect
        mock_socket_instance.connect.side_effect = \
            Exception("Generic network error")

        dest_address: Mock = Mock(ip="localhost", port=8001)
        response: Optional[str] = net.send_request(
            dest_address, "TEST", "arg1"
        )

        assert response is None
        assert mock_stderr_write.call_count >= 1
        messages_written: List[str] = [
            call_args[0][0] for call_args in mock_stderr_write.call_args_list
        ]
        assert any("Network request error: Generic network error" in msg
                   for msg in messages_written)


def test_net_stop_before_start() -> None:
    """Tests the stop method when called before the start method.

    Verifies that calling stop() does not raise an exception and that
    server_socket and network_thread remain None.
    """
    mock_handler: Mock = Mock()
    net: _Net = _Net("localhost", 8000, mock_handler)

    # Initially, server_socket and network_thread are None due to __init__
    assert net._running is False
    assert net.server_socket is None
    assert net.network_thread is None

    # Calling stop should not raise an error
    try:
        net.stop()
    except Exception as e:
        pytest.fail(f"Calling stop before start raised an exception: {e}")
