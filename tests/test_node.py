"""test_node.py: tests for the Node class.

NOTE: many of these tests were AI generated as regression tests, in preparation
for refactoring.
"""
import hashlib
from typing import Any, Generator, Tuple
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from chordnet._node import _Node as ChordNode
from chordnet.address import Address

logger.enable("chordnet")
# Global test variables
ip: str = "1.2.3.4"
port: int = 5
# Pre-calculated key for the default node address (ip:port)
key: int = int(hashlib.sha1(f"{ip}:{port}".encode()).hexdigest(), 16) % (2**16)


@pytest.fixture(autouse=True)
def mock_start() -> Generator[None, None, None]:
    """Mocks ChordNode.start() to prevent actual socket operations.

    This fixture is autoused, meaning it runs before every test.
    """
    with patch.object(ChordNode, "start", return_value=None):
        yield


@pytest.fixture
def node() -> ChordNode:
    """Provides a basic ChordNode instance for testing."""
    return ChordNode(ip, port)


def test_can_make_chordnode(node: ChordNode) -> None:
    """Verifies that a ChordNode instance can be successfully created.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    assert node is not None
    assert node.address.ip == "1.2.3.4"
    assert node.address.port == 5


def test_can_make_key(node: ChordNode) -> None:
    """Verifies that the key of the ChordNode's address is correctly calculated.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    assert key == node.address.key


def test_can_create_ring(node: ChordNode) -> None:
    """Verifies the behavior when a node creates a new Chord ring.

    Ensures the node becomes its own successor and the finger table is
    initialized correctly, with _next pointer advanced.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.create()

    assert node.successor() == Address(ip, port)
    assert node.finger_table[0] == node.address
    # _next should be advanced after initial fix_fingers call
    assert node._next == 1


def test_is_key_in_range(node: ChordNode) -> None:
    """Tests the _is_key_in_range method for various scenarios.

    Covers cases including:
    - Key within the normal range.
    - Key exactly at the node's or successor's key.
    - Key within a wrap-around range.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.create()
    # Test simple case within range
    assert node._is_key_in_range(node.address.key + 1) is True

    # Test exact node key (should return False)
    assert node._is_key_in_range(node.address.key) is False

    successor = node.successor()
    assert successor
    # Test successor's key (should return False)
    assert node._is_key_in_range(successor.key) is False

    # Test wrap-around scenario
    # Create a scenario where node's key is near the end of the hash space
    original_node_key: int = node.address.key
    original_successor: Address | None = node.successor()

    node.address.key = 65530  # Near max of 16-bit hash space
    test_successor: Address = Address(ip="5.6.7.8", port=6000)
    test_successor.key = 50 # Manually set for this specific test case's logic
    node.finger_table[0] = test_successor

    # Test wrap-around cases
    assert node._is_key_in_range(65535) is True  # Just before wrap
    assert node._is_key_in_range(40) is True  # Just after wrap
    assert node._is_key_in_range(51) is False  # Beyond successor
    assert node._is_key_in_range(65529) is False  # Before node

    # Restore original keys after this specific test
    node.address.key = original_node_key
    if original_successor:
        node.finger_table[0] = original_successor


def test_closest_preceding_finger_basic(node: ChordNode) -> None:
    """Tests the closest_preceding_finger method with a basic finger table.

    Verifies correct routing to the closest node between the current node
    and a target ID.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    addr1: Address = Address("1.1.1.1", 5001)
    addr1.key = 10
    addr2: Address = Address("2.2.2.2", 5002)
    addr2.key = 30
    addr3: Address = Address("3.3.3.3", 5003)
    addr3.key = 50
    node.finger_table = [addr1, addr2, addr3]

    result: Address = node.closest_preceding_finger(60)
    assert result == node.finger_table[2]  # Node with key 50

    result = node.closest_preceding_finger(5)
    assert result == node.address


def test_closest_preceding_finger_wrap_around(node: ChordNode) -> None:
    """Tests closest_preceding_finger in a wrap-around hash space scenario.

    Simulates a node near the end of the hash space and verifies correct
    identification of the closest preceding finger for a given ID.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.address.key = 65530  # Near max of 16-bit hash space
    addr1: Address = Address("1.1.1.1", 5001)
    addr1.key = 10
    addr2: Address = Address("2.2.2.2", 5002)
    addr2.key = 40
    addr3: Address = Address("3.3.3.3", 5003)
    addr3.key = 60
    node.finger_table = [addr1, addr2, addr3]

    result: Address = node.closest_preceding_finger(50)
    assert result == node.finger_table[1]  # Node with key 40

    result = node.closest_preceding_finger(5)
    assert result == node.address


def test_closest_preceding_finger_empty_finger_table(node: ChordNode) -> None:
    """Tests closest_preceding_finger behavior with an empty finger table.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.finger_table = []

    result: Address = node.closest_preceding_finger(100)
    assert result == node.address


def test_closest_preceding_finger_sparse_finger_table(node: ChordNode) -> None:
    """Tests closest_preceding_finger behavior with a sparse finger table.

    Verifies correct selection when some finger table entries are None.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.address.key = 0
    addr1: Address = Address("1.1.1.1", 5001)
    addr1.key = 30
    addr2: Address = Address("2.2.2.2", 5002)
    addr2.key = 50
    node.finger_table = [None, addr1, None, addr2]

    # Should return the first valid finger
    result: Address = node.closest_preceding_finger(40)
    assert result == node.finger_table[1]

    # When no valid finger found
    result = node.closest_preceding_finger(10)
    assert result == node.address


@pytest.fixture
def mock_send_request(node: ChordNode) -> Generator[MagicMock, None, None]:
    """Mocks the _net.send_request method of the ChordNode.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Yields:
        MagicMock: A mocked instance of _net.send_request.
    """
    with patch.object(node._net, "send_request") as mock_sr:
        yield mock_sr


def test_is_between(node: ChordNode) -> None:
    """Tests the _is_between helper method for various range scenarios.

    Covers normal ranges, wrap-around ranges, and edge cases like start == end.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    # Normal range (start < end)
    assert node._is_between(10, 50, 30) is True
    assert node._is_between(10, 50, 10) is False
    assert node._is_between(10, 50, 50) is False
    assert node._is_between(10, 50, 5) is False
    assert node._is_between(10, 50, 55) is False

    # Wrap-around range (start > end, e.g., 60 to 20 in a 64-key space)
    assert node._is_between(60, 20, 10) is True
    assert node._is_between(60, 20, 5) is True
    assert node._is_between(60, 20, 61) is True
    assert node._is_between(60, 20, 19) is True
    assert node._is_between(60, 20, 50) is False
    assert node._is_between(60, 20, 25) is False
    assert node._is_between(60, 20, 60) is False
    assert node._is_between(60, 20, 20) is False

    # Edge case: start == end
    assert node._is_between(10, 10, 10) is False
    assert node._is_between(10, 10, 20) is False


def test_parse_address(node: ChordNode) -> None:
    """Tests the _parse_address helper method for valid and invalid inputs.

    Verifies correct parsing of address strings into Address objects,
    and handles "nil" and malformed strings.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    # Valid address - here we rely on Address's internal hashing, so
    # calculate expected key
    expected_key: int = int(
        hashlib.sha1("192.168.1.100:8000".encode()).hexdigest(),
        16) % (2**16)
    addr_str: str = f"{expected_key}:192.168.1.100:8000"
    parsed_address: Address | None = node._parse_address(addr_str)
    assert parsed_address is not None
    assert parsed_address.key == expected_key
    assert parsed_address.ip == "192.168.1.100"
    assert parsed_address.port == 8000

    # "nil" response
    assert node._parse_address("nil") is None

    # Invalid format - too few parts
    with pytest.raises(
            ValueError, match="Invalid node address response format"):
        node._parse_address("12345:192.168.1.100")

    # Invalid format - too many parts
    with pytest.raises(
            ValueError, match="Invalid node address response format"):
        node._parse_address("12345:192.168.1.100:8000:extra")

    # Invalid port (non-integer)
    with pytest.raises(ValueError):
        node._parse_address("12345:192.168.1.100:abc")

    # Invalid key (non-integer)
    with pytest.raises(ValueError):
        node._parse_address("abc:192.168.1.100:8000")


def test_join_success(node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests successful joining of an existing Chord ring.

    Verifies that the node's successor is correctly set after a successful
    FIND_SUCCESSOR request and subsequent finger table initialization.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    known_ip: str = "5.6.7.8"
    known_port: int = 5000
    mock_successor_ip: str = "9.9.9.9"
    mock_successor_port: int = 6000
    # Calculate the key that Address would naturally generate for
    # the mock successor
    mock_successor_key: int = int(
        hashlib.sha1(f"{mock_successor_ip}:{mock_successor_port}".encode()
                     ).hexdigest(),
        16) % (2**16)

    val = f"{mock_successor_key}:{mock_successor_ip}:{mock_successor_port}"
    mock_send_request.return_value = val

    node.join(known_ip, known_port)

    # Assert send_request was called correctly
    known_node_address: Address = Address(known_ip, known_port)
    mock_send_request.assert_called_once_with(
        known_node_address,
        'FIND_SUCCESSOR',
        node.address.key
    )
    # Assert successor is set
    successor = node.successor()
    assert successor is not None
    assert successor.key == mock_successor_key
    assert successor.ip == mock_successor_ip
    assert successor.port == mock_successor_port
    # Assert _next was incremented after fix_fingers is called
    assert node._next == 1


def test_join_find_successor_failure(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests joining when finding the successor fails (no response).

    Verifies that a ValueError is raised and the successor remains unset.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    mock_send_request.return_value = None  # Simulate no response

    with pytest.raises(
            ValueError, match="Failed to find successor. Join failed"):
        node.join("5.6.7.8", 5000)

    assert node.successor() is None # Successor should not be set


def test_join_network_error(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests joining when a network error occurs during the successor search.

    Verifies that the network exception is re-raised.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    mock_send_request.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        node.join("5.6.7.8", 5000)
    assert node.successor() is None


def test_be_notified_no_predecessor(node: ChordNode) -> None:
    """Tests _be_notified when the node currently has no predecessor.

    Verifies that the notifying node is accepted as the new predecessor.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    notifying_node: Address = Address("10.0.0.1", 7000)
    notifying_node.key = 500 # Manually set key for test logic

    node.predecessor = None
    node.address.key = 1000 # Self key for test logic

    result: bool = node._be_notified(notifying_node)
    assert result is True
    assert node.predecessor == notifying_node


def test_be_notified_update_predecessor(node: ChordNode) -> None:
    """Tests _be_notified when the notifying node is a better predecessor.

    Verifies that the predecessor is updated if the notifying node's key
    falls between the current predecessor's key and the node's own key.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.address.key = 1000
    existing_predecessor: Address = Address("10.0.0.2", 7001)
    existing_predecessor.key = 400
    node.predecessor = existing_predecessor

    new_predecessor: Address = Address("10.0.0.3", 7002)
    # This node (500) is between existing (400) and self (1000)
    new_predecessor.key = 500

    result: bool = node._be_notified(new_predecessor)
    assert result is True
    assert node.predecessor == new_predecessor


def test_be_notified_no_update(node: ChordNode) -> None:
    """Tests _be_notified when the notifying node is not a better predecessor.

    Verifies that the predecessor remains unchanged if the notifying node's key
    does not fall between the current predecessor's key and the node's own key.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.address.key = 1000
    existing_predecessor: Address = Address("10.0.0.2", 7001)
    existing_predecessor.key = 600
    node.predecessor = existing_predecessor

    notifying_node: Address = Address("10.0.0.3", 7002)
    # This node (500) is NOT between existing (600) and self (1000)
    notifying_node.key = 500

    result: bool = node._be_notified(notifying_node)
    assert result is False
    assert node.predecessor == existing_predecessor # Should not change


def test_notify_success(node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests successful notification to a potential successor.

    Verifies that True is returned when the successor responds with "OK".

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    potential_successor: Address = Address("10.0.0.4", 8000)
    potential_successor.key = 2000 # For predictable comparison
    mock_send_request.return_value = "OK"

    result: bool = node.notify(potential_successor)
    assert result is True
    mock_send_request.assert_called_once_with(
        potential_successor,
        'NOTIFY',
        f"{node.address.key}:{node.address.ip}:{node.address.port}"
    )


def test_notify_ignored(node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests notification that is ignored by the potential successor.

    Verifies that True is returned even if the successor responds
    with "IGNORED".

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    potential_successor: Address = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.return_value = "IGNORED"

    result: bool = node.notify(potential_successor)
    assert result is True


def test_notify_failure_response(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests notification that receives an invalid response from the successor.

    Verifies that False is returned for unexpected responses.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    potential_successor: Address = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.return_value = "INVALID_NODE"

    result: bool = node.notify(potential_successor)
    assert result is False


def test_notify_network_error(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests notification when a network error occurs during the request.

    Verifies that False is returned on network errors.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    potential_successor: Address = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.side_effect = Exception("Network down")

    result: bool = node.notify(potential_successor)
    assert result is False


def test_notify_none_successor(node: ChordNode) -> None:
    """Tests notification when the potential successor is None.

    Verifies that False is returned immediately.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    result: bool = node.notify(None)
    assert result is False


def test_check_predecessor_alive(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests check_predecessor when the predecessor is alive and responsive.

    Verifies that the predecessor remains set.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = "ALIVE"

    node.check_predecessor()
    assert node.predecessor is not None
    mock_send_request.assert_called_once_with(node.predecessor, 'PING')


def test_check_predecessor_unresponsive(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests check_predecessor when the predecessor is unresponsive (no return).

    Verifies that the predecessor is set to None.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = None # No response

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_invalid_response(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests check_predecessor when the predecessor sends an invalid response.

    Verifies that the predecessor is set to None.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = "NOT_ALIVE" # Unexpected response

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_network_error(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests check_predecessor when a network error occurs during ping.

    Verifies that the predecessor is set to None.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.side_effect = Exception("Connection refused")

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_no_predecessor_set(
    node: ChordNode, mock_send_request: MagicMock) -> None:
    """Tests check_predecessor when no predecessor is currently set.

    Verifies that no network request is made and predecessor remains None.

    Args:
        node: A fixture providing a basic ChordNode instance.
        mock_send_request: A fixture mocking _net.send_request.
    """
    node.predecessor = None
    node.check_predecessor()
    mock_send_request.assert_not_called()
    assert node.predecessor is None


@pytest.fixture
def setup_stabilize_mocks(
        node: ChordNode
) -> Generator[Tuple[MagicMock, MagicMock, MagicMock], None, None]:
    """Provides mocked dependencies for stabilize tests.

    Mocks _net.send_request, node.notify, and node._parse_address.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Returns:
        A tuple containing the mocked objects.
    """
    with patch.object(node._net, "send_request") as mock_send_request:
        with patch.object(node, "notify") as mock_notify:
            with patch.object(node, "_parse_address") as mock_parse_address:
                yield mock_send_request, mock_notify, mock_parse_address


def test_stabilize_no_successor(
    node: ChordNode,
    setup_stabilize_mocks:
    Tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Tests stabilize when the node currently has no successor.

    Verifies that stabilize returns early without making network calls.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_stabilize_mocks: A fixture providing mocked dependencies.
    """
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.finger_table[0] = None # No successor

    node.stabilize()
    mock_send_request.assert_not_called()
    mock_notify.assert_not_called()
    mock_parse_address.assert_not_called()


def test_stabilize_update_successor(
    node: ChordNode,
    setup_stabilize_mocks:
    Tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Tests stabilize when a better successor is found and updated.

    Verifies that send_request is called on the original successor, the
    successor is updated, and notify is called on the new successor.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_stabilize_mocks: A fixture providing mocked dependencies.
    """
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks

    # Current node's key (from fixture, explicit for clarity)
    node.address.key = 57776

    # Define the original successor before stabilize is called
    original_successor_addr: Address = Address("1.1.1.1", 1111) # 23641
    node.finger_table[0] = original_successor_addr

    # Define the 'x' node (successor's predecessor)
    x_ip: str = "2.2.2.2"
    x_port: int = 2222
    x_addr: Address = Address(x_ip, x_port) # 4428

    # Mock what _net.send_request (called by stabilize to
    # get predecessor) returns
    # It should return the string representation of x_addr
    mock_send_request.return_value = f"{x_addr.key}:{x_ip}:{x_port}"

    # Mock what _parse_address returns when parsing the
    # response from send_request
    mock_parse_address.return_value = x_addr # This is the 'x' object

    node.stabilize()

    # Assert GET_PREDECESSOR was called on the ORIGINAL successor
    # We use original_successor_addr here because that's what was
    # passed to send_request
    mock_send_request.assert_called_once_with(
        original_successor_addr, 'GET_PREDECESSOR')

    # Assert node's successor was updated to x_addr
    assert node.successor() == x_addr

    # Assert notify was called on the NEW successor (which is x_addr)
    mock_notify.assert_called_once_with(x_addr)


def test_stabilize_no_successor_update(
    node: ChordNode,
    setup_stabilize_mocks: Tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Tests stabilize when no better successor is found.

    Verifies that the successor remains unchanged and notify is called on
    the original successor.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_stabilize_mocks: A fixture providing mocked dependencies.
    """
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.address.key = 100 # This key is for the node itself, not the successor

    original_successor_addr: Address = Address("1.1.1.1", 1111)
    original_successor_addr.key = 200
    node.finger_table[0] = original_successor_addr

    # Simulate successor's predecessor (x) NOT being between node
    # and current successor
    x_ip: str = "2.2.2.2"
    x_port: int = 2222
    x_addr: Address = Address(x_ip, x_port) # Initialize with ip and port
    x_addr.key = 250

    mock_send_request.return_value = f"{x_addr.key}:{x_ip}:{x_port}"
    mock_parse_address.return_value = x_addr

    node.stabilize()

    # Assert GET_PREDECESSOR was called on the ORIGINAL successor
    # (Using the reference captured before stabilize might change
    # node.finger_table[0])
    mock_send_request.assert_called_once_with(
        original_successor_addr, 'GET_PREDECESSOR')

    # Assert successor remains unchanged
    assert node.successor() == original_successor_addr

    # Assert notify was called on the ORIGINAL successor
    mock_notify.assert_called_once_with(original_successor_addr)


def test_stabilize_network_error(
    node: ChordNode,
    setup_stabilize_mocks: Tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Tests stabilize when a network error occurs during predecessor lookup.

    Verifies that the successor remains unchanged and notify is still called.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_stabilize_mocks: A fixture providing mocked dependencies.
    """
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.address.key = 100

    original_successor_addr: Address = Address("1.1.1.1", 1111)
    node.finger_table[0] = original_successor_addr

    mock_send_request.side_effect = Exception("Stabilize network error")

    node.stabilize()

    # Successor should remain unchanged
    assert node.successor() == original_successor_addr

    # Notify should still be attempted on the original successor
    mock_notify.assert_called_once_with(original_successor_addr)


@pytest.fixture
def setup_find_successor_mocks(
    node: ChordNode
) -> Generator[Tuple[MagicMock, MagicMock, MagicMock, MagicMock], None, None]:
    """Provides mocked dependencies for find_successor tests.

    Mocks _is_key_in_range, closest_preceding_finger, _net.send_request,
    and _parse_address.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Returns:
        A tuple containing the mocked objects.
    """
    with patch.object(node, "_is_key_in_range") as mock_is_key_in_range:
        with patch.object(node, "closest_preceding_finger") as mock_cpf:
            with patch.object(node._net, "send_request") as mock_send_request:
                with patch.object(node, "_parse_address") as mock_parse_address:
                    yield mock_is_key_in_range, mock_cpf, \
                        mock_send_request, mock_parse_address


def test_find_successor_key_in_range(
    node: ChordNode,
    setup_find_successor_mocks: Tuple[MagicMock,
                                      MagicMock,
                                      MagicMock,
                                      MagicMock]
) -> None:
    """Tests find_successor when the target ID is within the node's range.

    Verifies that the node's own successor is returned without network calls.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_find_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200 # Set key for this test's logic
    mock_is_key_in_range.return_value = True

    target_id: int = 150 # In range (100, 200)

    result: Address = node.find_successor(target_id)
    assert result == node.successor()
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_not_called()
    mock_send_request.assert_not_called()
    mock_parse_address.assert_not_called()


def test_find_successor_closest_preceding_is_self(
    node: ChordNode,
    setup_find_successor_mocks: Tuple[MagicMock,
                                      MagicMock,
                                      MagicMock,
                                      MagicMock]
) -> None:
    """Tests find_successor when closest preceding finger is the node itself.

    Verifies that the node's own successor is returned without network calls.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_find_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False # Not in range

    target_id: int = 250
    mock_cpf.return_value = node.address # Closest preceding finger is self

    result: Address = node.find_successor(target_id)
    assert result == node.successor() # Should return own successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_not_called() # No network call if CPF is self
    mock_parse_address.assert_not_called()


def test_find_successor_forward_request(
    node: ChordNode,
    setup_find_successor_mocks: Tuple[MagicMock,
                                      MagicMock,
                                      MagicMock,
                                      MagicMock]
) -> None:
    """Tests find_successor when the request needs to be forwarded.

    Verifies that the request is sent to the closest preceding finger and
    the parsed response from that node is returned.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_find_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False

    target_id: int = 500
    closest_node: Address = Address("3.3.3.3", 3333)
    closest_node.key = 400 # A different node
    mock_cpf.return_value = closest_node

    # Simulate response from the remote node
    expected_successor: Address = Address("4.4.4.4", 4444)
    expected_successor.key = 550
    val = f"{expected_successor.key}:{expected_successor.ip}" \
        f":{expected_successor.port}"
    mock_send_request.return_value = val
    mock_parse_address.return_value = expected_successor

    result: Address = node.find_successor(target_id)
    assert result == expected_successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(
        closest_node, 'FIND_SUCCESSOR', target_id)
    mock_parse_address.assert_called_once_with(mock_send_request.return_value)


def test_find_successor_network_error_fallback(
    node: ChordNode,
    setup_find_successor_mocks: Tuple[MagicMock,
                                      MagicMock,
                                      MagicMock,
                                      MagicMock]
) -> None:
    """Tests find_successor network error fallback to local successor.

    Verifies that if a network request to a remote node fails, the method
    falls back to returning the current node's own successor.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_find_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False

    target_id: int = 500
    closest_node: Address = Address("3.3.3.3", 3333)
    closest_node.key = 400
    mock_cpf.return_value = closest_node

    mock_send_request.side_effect = Exception("Remote node down")

    result: Address = node.find_successor(target_id)
    assert result == node.successor() # Should fallback to own successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(
        closest_node, 'FIND_SUCCESSOR', target_id)
    mock_parse_address.assert_not_called()


@pytest.fixture
def setup_fix_fingers_mocks(
    node: ChordNode
) -> Generator[MagicMock, None, None]:
    """Provides mocked dependencies for fix_fingers tests.

    Mocks node.find_successor.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Returns:
        MagicMock: A mocked instance of node.find_successor.
    """
    with patch.object(node, "find_successor") as mock_find_successor:
        yield mock_find_successor


def test_fix_fingers_no_successor(
    node: ChordNode, setup_fix_fingers_mocks: MagicMock
) -> None:
    """Tests fix_fingers when the node currently has no successor.

    Verifies that fix_fingers returns early without calling find_successor
    or advancing _next.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_fix_fingers_mocks: A fixture providing mocked find_successor.
    """
    mock_find_successor: MagicMock = setup_fix_fingers_mocks
    node.finger_table[0] = None # No successor
    node._next = 0

    node.fix_fingers()
    mock_find_successor.assert_not_called()
    assert node._next == 0 # Should not advance _next


def test_fix_fingers_updates_finger_table(
    node: ChordNode, setup_fix_fingers_mocks: MagicMock
) -> None:
    """Tests fix_fingers correctly updates finger table entries.

    Verifies that find_successor is called with the correct arguments and
    the finger table entry is updated, and _next advances.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_fix_fingers_mocks: A fixture providing mocked find_successor.
    """
    mock_find_successor: MagicMock = setup_fix_fingers_mocks
    node.address.key = 1000
    node.finger_table[0] = Address("1.1.1.1", 1111) # Set a successor
    node._next = 0 # First finger (successor)

    # Simulate find_successor finding a node for finger 0
    # For _next = 0, gap = 2**0 = 1. Start = 1000 + 1 = 1001.
    expected_finger_0: Address = Address("2.2.2.2", 2222)
    expected_finger_0.key = 1001 # For predictable test scenario
    mock_find_successor.return_value = expected_finger_0

    node.fix_fingers()

    mock_find_successor.assert_called_once_with(1000 + (2**0) % (2**Address._M))
    assert node.finger_table[0] == expected_finger_0
    assert node._next == 1 # _next should advance

    # Test for _next = 1
    node._next = 1
    expected_finger_1: Address = Address("3.3.3.3", 3333)

    # For _next = 1, gap = 2**1 = 2. Start = 1000 + 2 = 1002.
    expected_finger_1.key = 1002
    mock_find_successor.return_value = expected_finger_1
    mock_find_successor.reset_mock() # Reset call count

    node.fix_fingers()
    mock_find_successor.assert_called_once_with(1000 + (2**1) % (2**Address._M))
    assert node.finger_table[1] == expected_finger_1
    assert node._next == 2


def test_fix_fingers_network_error(
    node: ChordNode, setup_fix_fingers_mocks: MagicMock
) -> None:
    """Tests fix_fingers gracefully handles network errors in find_successor.

    Verifies that an exception during find_successor does not crash the method,
    and _next still advances.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_fix_fingers_mocks: A fixture providing mocked find_successor.
    """
    mock_find_successor: MagicMock = setup_fix_fingers_mocks
    node.address.key = 1000
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 1001
    node._next = 5 # Some finger

    mock_find_successor.side_effect = Exception(
        "Find successor failed for finger")

    # The test should not raise an exception, as fix_fingers catches it.
    node.fix_fingers()

    # Finger should remain None or its previous value if set.
    # If it was None, it stays None.
    assert node.finger_table[5] is None # Assuming it was None initially
    assert node._next == 6 # _next should still advance


@pytest.fixture
def setup_trace_successor_mocks(
    node: ChordNode
) -> Generator[Tuple[MagicMock, MagicMock, MagicMock], None, None]:
    """Provides mocked dependencies for trace_successor tests.

    Mocks _is_key_in_range, closest_preceding_finger, and _net.send_request.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Returns:
        A tuple containing the mocked objects.
    """
    with patch.object(node, "_is_key_in_range") as mock_is_key_in_range:
        with patch.object(node, "closest_preceding_finger") as mock_cpf:
            with patch.object(node._net, "send_request") as mock_send_request:
                yield mock_is_key_in_range, mock_cpf, mock_send_request


def test_trace_successor_key_in_range(
    node: ChordNode,
    setup_trace_successor_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests trace_successor when the target ID is within the node's range.

    Verifies that the node's own successor is returned along with current hops,
    without making network calls.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_trace_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = True

    target_id: int = 150
    initial_hops: int = 0
    result_address: Any
    result_hops: int
    result_address, result_hops = node.trace_successor(target_id, initial_hops)

    assert result_address == str(node.successor())
    assert result_hops == initial_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_not_called()
    mock_send_request.assert_not_called()


def test_trace_successor_closest_preceding_is_self(
    node: ChordNode,
    setup_trace_successor_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests trace_successor when closest preceding finger is the node itself.

    Verifies that the node's own successor is returned along with current hops,
    without making network calls.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_trace_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False # Not in range

    target_id: int = 250
    initial_hops: int = 0
    mock_cpf.return_value = node.address # Closest preceding finger is self

    result_address: Any
    result_hops: int
    result_address, result_hops = node.trace_successor(target_id, initial_hops)
    assert result_address == str(node.successor())
    assert result_hops == initial_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_not_called()


def test_trace_successor_forward_request(
    node: ChordNode,
    setup_trace_successor_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests trace_successor when the request needs to be forwarded.

    Verifies that the request is sent to the closest preceding finger, and the
    response (address string and incremented hops) is returned.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_trace_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False

    target_id: int = 500
    initial_hops: int = 2
    closest_node: Address = Address("3.3.3.3", 3333)
    closest_node.key = 400
    mock_cpf.return_value = closest_node

    # Simulate response from the remote node
    remote_successor_key: int = 550
    remote_successor_ip: str = "4.4.4.4"
    remote_successor_port: int = 4444
    remote_hops_returned: int = 3 # Hops reported by the remote node
    val = f"{remote_successor_key}:{remote_successor_ip}:" \
        f"{remote_successor_port}:{remote_hops_returned}"
    mock_send_request.return_value = val

    result_address_str: str
    result_hops: int
    result_address_str, result_hops = node.trace_successor(
        target_id, initial_hops)

    val = f"{remote_successor_key}:{remote_successor_ip}:" \
        f"{remote_successor_port}"
    expected_address_str: str = val
    expected_hops: int = remote_hops_returned + 1

    assert result_address_str == expected_address_str
    assert result_hops == expected_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(
        closest_node, 'TRACE_SUCCESSOR', target_id, initial_hops)


def test_trace_successor_network_error_fallback(
    node: ChordNode,
    setup_trace_successor_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests trace_successor network error fallback to local successor.

    Verifies that if a network request to a remote node fails, the method
    falls back to returning the current node's own successor.
    NOTE: The return type becomes Address, which is inconsistent with
    success path.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_trace_successor_mocks: A fixture providing mocked dependencies.
    """
    mock_is_key_in_range, mock_cpf, \
        mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    assert(node.finger_table[0])
    node.finger_table[0].key = 200
    mock_is_key_in_range.return_value = False

    target_id: int = 500
    initial_hops: int = 0
    closest_node: Address = Address("3.3.3.3", 3333)
    closest_node.key = 400
    mock_cpf.return_value = closest_node

    mock_send_request.side_effect = Exception("Trace network error")

    # When `trace_successor` encounters an exception, it returns
    # `self.successor()` directly (an Address object).
    # This is inconsistent with its successful return type `(Address, int)`
    result = node.trace_successor(
        target_id, initial_hops)

    assert result[0] == str(node.successor())
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(
        closest_node, 'TRACE_SUCCESSOR', target_id, initial_hops)


@pytest.fixture
def setup_process_request_mocks(
    node: ChordNode
) -> Generator[Tuple[MagicMock, MagicMock, MagicMock, MagicMock], None, None]:
    """Provides mocked dependencies for _process_request tests.

    Mocks find_successor, trace_successor, _be_notified, and _parse_address.

    Args:
        node: A fixture providing a basic ChordNode instance.

    Returns:
        A tuple containing the mocked objects.
    """
    with patch.object(node, "find_successor") as mock_find_successor:
        with patch.object(node, "trace_successor") as mock_trace_successor:
            with patch.object(node, "_be_notified") as mock_be_notified:
                with patch.object(node, "_parse_address") as mock_parse_address:
                    yield mock_find_successor, mock_trace_successor, \
                        mock_be_notified, mock_parse_address


def test_process_request_ping(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of "PING" method.

    Verifies that "ALIVE" is returned and no other methods are called.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    result: str | Address | None = node._process_request("PING", [])
    assert result == "ALIVE"
    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_find_successor(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of "FIND_SUCCESSOR" method.

    Verifies that find_successor is called and its result is returned.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    found_succ: Address = Address("1.1.1.1", 1111)
    found_succ.key = 12345
    mock_fs.return_value = found_succ
    result: str | Address | None = node._process_request(
        "FIND_SUCCESSOR", ["100"])
    assert result == found_succ
    mock_fs.assert_called_once_with(100)
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_get_predecessor(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of "GET_PREDECESSOR" method.

    Verifies that the current predecessor is returned, or "nil" if none is set.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    node.predecessor = Address("2.2.2.2", 2222)
    node.predecessor.key = 54321
    result: str | Address | None = node._process_request("GET_PREDECESSOR", [])
    assert result == node.predecessor

    node.predecessor = None
    result = node._process_request("GET_PREDECESSOR", [])
    assert result == "nil"

    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_notify(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of "NOTIFY" method.

    Covers successful notification, ignored notification, and invalid arguments.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    notifying_addr: Address = Address("10.0.0.10", 10000)
    notifying_addr.key = 500
    mock_pa.return_value = notifying_addr

    # Test "OK" response
    mock_bn.return_value = True
    result: str | Address | None = node._process_request(
        "NOTIFY", ["500", "10.0.0.10", "10000"])
    assert result == "OK"
    mock_pa.assert_called_once_with('500:10.0.0.10:10000')
    mock_bn.assert_called_once_with(notifying_addr)

    mock_pa.reset_mock()
    mock_bn.reset_mock()

    # Test "IGNORED" response
    mock_bn.return_value = False
    result = node._process_request("NOTIFY", ["500", "10.0.0.10", "10000"])
    assert result == "IGNORED"
    mock_pa.assert_called_once()
    mock_bn.assert_called_once_with(notifying_addr)

    mock_pa.reset_mock()
    mock_bn.reset_mock()

    # Test invalid arguments (not enough parts)
    result = node._process_request("NOTIFY", ["invalid_args"])
    assert result == "INVALID_NODE"
    # _parse_address should not be called with insufficient args
    mock_pa.assert_not_called()
    mock_bn.assert_not_called()

    # Test invalid arguments (ValueError from _parse_address)
    mock_pa.reset_mock()
    mock_bn.reset_mock()
    mock_pa.side_effect = ValueError("Invalid format")
    result = node._process_request(
        "NOTIFY", ["500", "10.0.0.10", "invalid_port"])
    assert result == "INVALID_NODE"

    # _parse_address is called but raises ValueError
    mock_pa.assert_called_once_with("500:10.0.0.10:invalid_port")
    mock_bn.assert_not_called()

    mock_fs.assert_not_called()
    mock_ts.assert_not_called()


def test_process_request_trace_successor(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of "TRACE_SUCCESSOR" method.

    Covers successful trace (returns string and hops) and failure.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    # Simulate the Address object that would be returned by trace_successor
    trace_succ_ip: str = "1.1.1.1"
    trace_succ_port: int = 1111
    temp_addr: Address = Address(trace_succ_ip, trace_succ_port)

    mock_ts.return_value = (str(temp_addr), 5) # tuple of (address_string, hops)
    result: str | Address | None = node._process_request(
        "TRACE_SUCCESSOR", ["100", "4"])
    assert result == f"{str(temp_addr)}:5"
    mock_ts.assert_called_once_with(100, 4)

    mock_ts.reset_mock()
    mock_ts.side_effect = Exception("Trace failed")
    result = node._process_request("TRACE_SUCCESSOR", ["100", "4"])
    assert result == "ERROR:Invalid TRACE_SUCCESSOR Request"
    mock_ts.assert_called_once_with(100, 4)

    mock_fs.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_invalid_method(
    node: ChordNode,
    setup_process_request_mocks: Tuple[MagicMock,
                                       MagicMock,
                                       MagicMock,
                                       MagicMock]
) -> None:
    """Tests _process_request handling of an invalid/unknown method.

    Verifies that "INVALID_METHOD" is returned and no other methods are called.

    Args:
        node: A fixture providing a basic ChordNode instance.
        setup_process_request_mocks: A fixture providing mocked dependencies.
    """
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    result: str | Address | None = node._process_request("UNKNOWN_METHOD", [])
    assert result == "INVALID_METHOD"
    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_repr(node: ChordNode) -> None:
    """Tests the __repr__ method of the ChordNode.

    Verifies that the string representation includes the node's key.

    Args:
        node: A fixture providing a basic ChordNode instance.
    """
    node.address.key = 12345
    assert repr(node) == "ChordNode(key=12345)"
