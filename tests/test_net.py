# test_net.py
import socket
import sys
from unittest.mock import Mock, patch

import pytest

from chordnet import _Net


def test_net_initialization():
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    assert net._ip == "localhost"
    assert net._port == 8000
    assert net._request_handler == mock_handler
    assert net._running is False
    assert net._network_thread is None
    assert net.server_socket is None # Now initialized in __init__
    assert net.network_thread is None # Now initialized in __init__


@patch("socket.socket")
@patch("threading.Thread")
def test_net_start(mock_thread, mock_socket):
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    net.start()

    assert net._running is True
    assert net.server_socket == mock_socket.return_value
    assert net.network_thread == mock_thread.return_value

    # Verify socket was created and bound
    mock_socket.return_value.bind.assert_called_once_with(("localhost", 8000))
    mock_socket.return_value.listen.assert_called_once_with(5)

    # Verify thread was started
    mock_thread.assert_called_once_with(target=net._listen_for_connections, daemon=True)
    mock_thread.return_value.start.assert_called_once()


def test_net_handle_connection():
    # Mock socket and request handler
    mock_socket = Mock()
    mock_handler = Mock(return_value="test_response")

    net = _Net("localhost", 8000, mock_handler)

    # Simulate receiving a request
    mock_socket.recv.return_value = b"TEST:arg1:arg2"

    net._handle_connection(mock_socket)

    # Verify handler was called correctly
    mock_handler.assert_called_once_with("TEST", ["arg1", "arg2"])

    # Verify response was sent
    mock_socket.send.assert_called_once_with(b"test_response")

    # Verify socket was closed
    mock_socket.close.assert_called_once()


def test_net_stop():
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

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


def test_send_request_success():
    # Create a mock network instance
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate a successful request
    with patch("socket.socket") as mock_socket:
        # Setup mock socket behavior
        mock_socket_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        # Simulate successful connection and response
        mock_socket_instance.recv.return_value = b"RESPONSE"

        # Call send_request
        response = net.send_request(
            Mock(ip="localhost", port=8001), "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response == "RESPONSE"

        # Verify socket methods were called correctly
        mock_socket_instance.settimeout.assert_called_once_with(5)
        mock_socket_instance.connect.assert_called_once_with(("localhost", 8001))
        mock_socket_instance.send.assert_called_once_with(b"TEST:arg1:arg2")
        mock_socket_instance.recv.assert_called_once_with(1024)


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_timeout(mock_stderr_flush, mock_stderr_write):
    # Create a mock network instance
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate a timeout
    with patch("socket.socket") as mock_socket:
        mock_socket_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        # Simulate a timeout
        mock_socket_instance.connect.side_effect = socket.timeout

        response = net.send_request(
            Mock(ip="localhost", port=8001), "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response is None

        # Assert that 'write' was called and contained the message
        assert mock_stderr_write.call_count >= 1
        messages_written = [call_args[0][0] for call_args in mock_stderr_write.call_args_list]
        assert any("Request timed out" in msg for msg in messages_written)


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_connection_refused(mock_stderr_flush, mock_stderr_write):
    # Create a mock network instance
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    # Mock the socket to simulate connection refused
    with patch("socket.socket") as mock_socket:
        mock_socket_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        # Simulate connection refused
        mock_socket_instance.connect.side_effect = ConnectionRefusedError

        response = net.send_request(
            Mock(ip="localhost", port=8001), "TEST", "arg1", "arg2"
        )

        # Assertions
        assert response is None
        # Assert that 'write' was called and contained the message
        assert mock_stderr_write.call_count >= 1
        messages_written = [call_args[0][0] for call_args in mock_stderr_write.call_args_list]
        assert any("Connection refused" in msg for msg in messages_written)


# tests/test_net.py (only the relevant test function is shown)

@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_listen_for_connections_accept_exception(mock_stderr_flush, mock_stderr_write):
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    mock_server_socket = Mock()
    net.server_socket = mock_server_socket # Manually set the mock server_socket
    net._running = True # Ensure the loop runs at least once

    # Configure side_effect using a generator.
    # First call to accept(): raises exception, but net._running is still True.
    # Second call to accept() (if loop continued): sets net._running to False, allowing loop to exit.
    def controlled_accept_side_effect_generator():
        yield Exception("Simulated accept error") # First time accept is called, it raises this.
        # If _listen_for_connections tried to accept again (loop continues after logging error),
        # this next line would execute, making the loop terminate.
        net._running = False
        yield Mock(), Mock() # Return a valid connection, so it doesn't raise another error if loop tried once more.

    mock_server_socket.accept.side_effect = controlled_accept_side_effect_generator()

    # Call _listen_for_connections directly to control its execution for testing this error path
    net._listen_for_connections()

    # Assertions for stderr output
    assert mock_stderr_write.call_count >= 1
    messages_written = [call_args[0][0] for call_args in mock_stderr_write.call_args_list]
    assert any("Error accepting connection: Simulated accept error" in msg for msg in messages_written)
    assert net._running is False # Verify the loop has stopped


def test_net_handle_connection_no_args():
    mock_socket = Mock()
    mock_handler = Mock(return_value="test_response_no_args")

    net = _Net("localhost", 8000, mock_handler)

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
def test_net_handle_connection_handler_exception(mock_stderr_flush, mock_stderr_write):
    mock_socket = Mock()
    mock_handler = Mock(side_effect=Exception("Handler error"))

    net = _Net("localhost", 8000, mock_handler)

    mock_socket.recv.return_value = b"TEST:arg1"

    net._handle_connection(mock_socket)

    mock_handler.assert_called_once_with("TEST", ["arg1"])
    mock_socket.send.assert_not_called() # Response should not be sent

    mock_socket.close.assert_called_once() # Socket should still be closed

    assert mock_stderr_write.call_count >= 1
    messages_written = [call_args[0][0] for call_args in mock_stderr_write.call_args_list]
    assert any("Error handling connection: Handler error" in msg for msg in messages_written)
    mock_stderr_flush.assert_called_once()


def test_send_request_no_args():
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    with patch("socket.socket") as mock_socket:
        mock_socket_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        mock_socket_instance.recv.return_value = b"RESPONSE_NO_ARGS"

        response = net.send_request(
            Mock(ip="localhost", port=8001), "NO_ARGS_METHOD"
        )

        assert response == "RESPONSE_NO_ARGS"
        mock_socket_instance.send.assert_called_once_with(b"NO_ARGS_METHOD:")


@patch.object(sys.stderr, 'write')
@patch.object(sys.stderr, 'flush')
def test_send_request_general_exception(mock_stderr_flush, mock_stderr_write):
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    with patch("socket.socket") as mock_socket:
        mock_socket_instance = Mock()
        mock_socket.return_value.__enter__.return_value = mock_socket_instance

        # Simulate a generic exception during connect
        mock_socket_instance.connect.side_effect = Exception("Generic network error")

        response = net.send_request(
            Mock(ip="localhost", port=8001), "TEST", "arg1"
        )

        assert response is None
        assert mock_stderr_write.call_count >= 1
        messages_written = [call_args[0][0] for call_args in mock_stderr_write.call_args_list]
        assert any("Network request error: Generic network error" in msg for msg in messages_written)


def test_net_stop_before_start():
    mock_handler = Mock()
    net = _Net("localhost", 8000, mock_handler)

    # Initially, server_socket and network_thread are None due to __init__ changes
    assert net._running is False
    assert net.server_socket is None
    assert net.network_thread is None

    # Calling stop should not raise an error
    try:
        net.stop()
    except Exception as e:
        pytest.fail(f"Calling stop before start raised an exception: {e}")

    # No assertions on mocks needed as server_socket and network_thread are None
