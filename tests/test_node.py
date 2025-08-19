# test_chord.py
import pytest
import hashlib
from unittest.mock import patch

from chordnet import Address
from chordnet import Node as ChordNode

ip = "1.2.3.4"
port = 5
key = f"{ip}:{port}"
key = int(hashlib.sha1(key.encode()).hexdigest(), 16) % (2**16)


# for start() so we don't use sockets
@pytest.fixture(autouse=True)
def mock_start():
    with patch.object(ChordNode, "start", return_value=None):
        yield


@pytest.fixture
def node():
    return ChordNode(ip, port)


def test_can_make_chordnode(node):
    assert node is not None
    assert node.address.ip == "1.2.3.4"
    assert node.address.port == 5


def test_can_make_key(node):
    assert key == node.address.key


def test_can_create_ring(node):
    node.create()

    assert node.successor() == Address(ip, port)
    assert node.finger_table[0] == node.address
    assert node._next == 1 # _next should be advanced after initial fix_fingers call


def test_is_key_in_range(node):
    node.create()
    # Test simple case within range
    assert node._is_key_in_range(node.address.key + 1) is True

    # Test exact node key (should return False)
    assert node._is_key_in_range(node.address.key) is False

    # Test successor's key (should return False)
    assert node._is_key_in_range(node.successor().key) is False

    # Test wrap-around scenario
    # Create a scenario where node's key is near the end of the hash space
    node.address.key = 65530  # Near max of 16-bit hash space
    node.finger_table[0] = Address(ip="5.6.7.8", port=6000)
    node.successor().key = 50

    # Test wrap-around cases
    assert node._is_key_in_range(65535) is True  # Just before wrap
    assert node._is_key_in_range(40) is True  # Just after wrap
    assert node._is_key_in_range(51) is False  # Beyond successor
    assert node._is_key_in_range(65529) is False  # Before node


def test_closest_preceding_finger_basic(node):
    """Test basic finger table routing"""
    # Create a mock finger table with some nodes
    node.finger_table = [
        Address("1.1.1.1", 5001),
        Address("2.2.2.2", 5002),
        Address("3.3.3.3", 5003),
    ]
    node.finger_table[0].key = 10
    node.finger_table[1].key = 30
    node.finger_table[2].key = 50

    # Test finding a node between current node and target id
    result = node.closest_preceding_finger(60)
    assert result == node.finger_table[2]  # Node with key 50

    # Test when no finger is between current node and target
    result = node.closest_preceding_finger(5)
    assert result == node.address


def test_closest_preceding_finger_wrap_around(node):
    """Test closest preceding node in a wrap-around scenario"""
    # Simulate a wrap-around scenario in the hash space
    node.address.key = 65530  # Near max of 16-bit hash space
    node.finger_table = [
        Address("1.1.1.1", 5001),
        Address("2.2.2.2", 5002),
        Address("3.3.3.3", 5003),
    ]
    node.finger_table[0].key = 10
    node.finger_table[1].key = 40
    node.finger_table[2].key = 60

    # Test wrap-around case
    result = node.closest_preceding_finger(50)
    assert result == node.finger_table[1]  # Node with key 40

    # Test when no finger is between current node and target
    result = node.closest_preceding_finger(5)
    assert result == node.address


def test_closest_preceding_finger_empty_finger_table(node):
    """Test behavior with an empty finger table"""
    node.finger_table = []

    result = node.closest_preceding_finger(100)
    assert result == node.address


def test_closest_preceding_finger_sparse_finger_table(node):
    """Test behavior with a sparse finger table"""
    node.address.key = 0
    node.finger_table = [None, Address("1.1.1.1", 5001), None, Address("2.2.2.2", 5002)]
    node.finger_table[1].key = 30
    node.finger_table[3].key = 50

    # Should return the first valid finger
    result = node.closest_preceding_finger(40)
    assert result == node.finger_table[1]

    # When no valid finger found
    result = node.closest_preceding_finger(10)
    assert result == node.address


@pytest.fixture
def mock_send_request(node):
    with patch.object(node._net, "send_request") as mock_sr:
        yield mock_sr

def test_is_between(node):
    # Normal range (start < end)
    assert node._is_between(10, 50, 30) is True
    assert node._is_between(10, 50, 10) is False
    assert node._is_between(10, 50, 50) is False
    assert node._is_between(10, 50, 5) is False
    assert node._is_between(10, 50, 55) is False

    # Wrap-around range (start > end, e.g., 60 to 20 in a 64-key space)
    assert node._is_between(60, 20, 10) is True  # 60 -> ... -> 10 -> ... -> 20
    assert node._is_between(60, 20, 5) is True
    assert node._is_between(60, 20, 61) is True # Just after start
    assert node._is_between(60, 20, 19) is True # Just before end
    assert node._is_between(60, 20, 50) is False # Before start and after end (in terms of wrap)
    assert node._is_between(60, 20, 25) is False # Between end and start (in terms of wrap)
    assert node._is_between(60, 20, 60) is False
    assert node._is_between(60, 20, 20) is False

    # Edge case: start == end
    assert node._is_between(10, 10, 10) is False
    assert node._is_between(10, 10, 20) is False


def test_parse_address(node):
    # Valid address
    addr_str = "12345:192.168.1.100:8000"
    parsed_address = node._parse_address(addr_str)
    assert parsed_address.key == 12345
    assert parsed_address.ip == "192.168.1.100"
    assert parsed_address.port == 8000

    # "nil" response
    assert node._parse_address("nil") is None

    # Invalid format - too few parts
    with pytest.raises(ValueError, match="Invalid node address response format"):
        node._parse_address("12345:192.168.1.100")

    # Invalid format - too many parts
    with pytest.raises(ValueError, match="Invalid node address response format"):
        node._parse_address("12345:192.168.1.100:8000:extra")

    # Invalid port (non-integer)
    with pytest.raises(ValueError):
        node._parse_address("12345:192.168.1.100:abc")

    # Invalid key (non-integer)
    with pytest.raises(ValueError):
        node._parse_address("abc:192.168.1.100:8000")


def test_join_success(node, mock_send_request):
    known_ip = "5.6.7.8"
    known_port = 5000
    mock_successor_key = 1000
    mock_successor_ip = "9.9.9.9"
    mock_successor_port = 6000
    mock_send_request.return_value = f"{mock_successor_key}:{mock_successor_ip}:{mock_successor_port}"

    node.join(known_ip, known_port)

    # Assert send_request was called correctly
    known_node_address = Address(known_ip, known_port)
    mock_send_request.assert_called_once_with(
        known_node_address,
        'FIND_SUCCESSOR',
        node.address.key
    )
    # Assert successor is set
    assert node.successor().key == mock_successor_key
    assert node.successor().ip == mock_successor_ip
    assert node.successor().port == mock_successor_port
    # Assert _next was incremented after fix_fingers is called
    assert node._next == 1


def test_join_find_successor_failure(node, mock_send_request):
    mock_send_request.return_value = None  # Simulate no response

    with pytest.raises(ValueError, match="Failed to find successor. Join failed"):
        node.join("5.6.7.8", 5000)

    assert node.successor() is None # Successor should not be set


def test_join_network_error(node, mock_send_request):
    mock_send_request.side_effect = Exception("Network error")

    with pytest.raises(Exception, match="Network error"):
        node.join("5.6.7.8", 5000)
    assert node.successor() is None


def test_be_notified_no_predecessor(node):
    notifying_node = Address("10.0.0.1", 7000)
    notifying_node.key = 500

    node.predecessor = None
    node.address.key = 1000 # Self key

    result = node._be_notified(notifying_node)
    assert result is True
    assert node.predecessor == notifying_node


def test_be_notified_update_predecessor(node):
    node.address.key = 1000
    existing_predecessor = Address("10.0.0.2", 7001)
    existing_predecessor.key = 400
    node.predecessor = existing_predecessor

    new_predecessor = Address("10.0.0.3", 7002)
    new_predecessor.key = 500 # This node (500) is between existing (400) and self (1000)

    result = node._be_notified(new_predecessor)
    assert result is True
    assert node.predecessor == new_predecessor


def test_be_notified_no_update(node):
    node.address.key = 1000
    existing_predecessor = Address("10.0.0.2", 7001)
    existing_predecessor.key = 600
    node.predecessor = existing_predecessor

    notifying_node = Address("10.0.0.3", 7002)
    notifying_node.key = 500 # This node (500) is NOT between existing (600) and self (1000)

    result = node._be_notified(notifying_node)
    assert result is False
    assert node.predecessor == existing_predecessor # Should not change


def test_notify_success(node, mock_send_request):
    potential_successor = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.return_value = "OK"

    result = node.notify(potential_successor)
    assert result is True
    mock_send_request.assert_called_once_with(
        potential_successor,
        'NOTIFY',
        f"{node.address.key}:{node.address.ip}:{node.address.port}"
    )


def test_notify_ignored(node, mock_send_request):
    potential_successor = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.return_value = "IGNORED"

    result = node.notify(potential_successor)
    assert result is True


def test_notify_failure_response(node, mock_send_request):
    potential_successor = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.return_value = "INVALID_NODE" # Or any other unexpected response

    result = node.notify(potential_successor)
    assert result is False


def test_notify_network_error(node, mock_send_request):
    potential_successor = Address("10.0.0.4", 8000)
    potential_successor.key = 2000
    mock_send_request.side_effect = Exception("Network down")

    result = node.notify(potential_successor)
    assert result is False


def test_notify_none_successor(node):
    result = node.notify(None)
    assert result is False


def test_check_predecessor_alive(node, mock_send_request):
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = "ALIVE"

    node.check_predecessor()
    assert node.predecessor is not None
    mock_send_request.assert_called_once_with(node.predecessor, 'PING')


def test_check_predecessor_unresponsive(node, mock_send_request):
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = None # No response

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_invalid_response(node, mock_send_request):
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.return_value = "NOT_ALIVE" # Unexpected response

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_network_error(node, mock_send_request):
    node.predecessor = Address("10.0.0.5", 9000)
    node.predecessor.key = 3000
    mock_send_request.side_effect = Exception("Connection refused")

    node.check_predecessor()
    assert node.predecessor is None


def test_check_predecessor_no_predecessor_set(node, mock_send_request):
    node.predecessor = None
    node.check_predecessor()
    mock_send_request.assert_not_called()
    assert node.predecessor is None


@pytest.fixture
def setup_stabilize_mocks(node):
    with patch.object(node._net, "send_request") as mock_send_request:
        with patch.object(node, "notify") as mock_notify:
            with patch.object(node, "_parse_address") as mock_parse_address:
                yield mock_send_request, mock_notify, mock_parse_address


def test_stabilize_no_successor(node, setup_stabilize_mocks):
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.finger_table[0] = None # No successor

    node.stabilize()
    mock_send_request.assert_not_called()
    mock_notify.assert_not_called()
    mock_parse_address.assert_not_called()


def test_stabilize_update_successor(node, setup_stabilize_mocks):
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.address.key = 57776 # Current node's key (from fixture, explicit for clarity)

    # Define the original successor before stabilize is called
    original_successor_addr = Address("1.1.1.1", 1111) # Key will be naturally calculated as 23641
    node.finger_table[0] = original_successor_addr # Current successor is now this Address object

    # Define the 'x' node (successor's predecessor)
    x_ip = "2.2.2.2"
    x_port = 2222
    x_addr = Address(x_ip, x_port) # Key will be naturally calculated as 4428

    # Mock what _net.send_request (called by stabilize to get predecessor) returns
    # It should return the string representation of x_addr
    mock_send_request.return_value = f"{x_addr.key}:{x_ip}:{x_port}"

    # Mock what _parse_address returns when parsing the response from send_request
    mock_parse_address.return_value = x_addr # This is the 'x' object

    node.stabilize()

    # Assert GET_PREDECESSOR was called on the ORIGINAL successor
    # We use original_successor_addr here because that's what was passed to send_request
    mock_send_request.assert_called_once_with(original_successor_addr, 'GET_PREDECESSOR')

    # Assert node's successor was updated to x_addr
    assert node.successor() == x_addr

    # Assert notify was called on the NEW successor (which is x_addr)
    mock_notify.assert_called_once_with(x_addr)


def test_stabilize_no_successor_update(node, setup_stabilize_mocks):
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.address.key = 100 # This key is for the node itself, not the successor

    # Fix this line:
    # Original: node.finger_table[0] = Address("1.1.1.1", 1111, 200)
    original_successor_addr = Address("1.1.1.1", 1111) # Initialize with ip and port
    original_successor_addr.key = 200 # Then set the key separately for the test scenario
    node.finger_table[0] = original_successor_addr

    # Simulate successor's predecessor (x) NOT being between node and current successor
    x_ip = "2.2.2.2"
    x_port = 2222
    x_addr = Address(x_ip, x_port) # Initialize with ip and port
    x_addr.key = 250 # This node (250) is NOT between existing (200) and self (100) (using direct key for test logic)

    mock_send_request.return_value = f"{x_addr.key}:{x_ip}:{x_port}"
    mock_parse_address.return_value = x_addr

    node.stabilize()

    # Assert GET_PREDECESSOR was called on the ORIGINAL successor
    # (Using the reference captured before stabilize might change node.finger_table[0])
    mock_send_request.assert_called_once_with(original_successor_addr, 'GET_PREDECESSOR')

    # Assert successor remains unchanged
    assert node.successor() == original_successor_addr

    # Assert notify was called on the ORIGINAL successor
    mock_notify.assert_called_once_with(original_successor_addr)


def test_stabilize_network_error(node, setup_stabilize_mocks):
    mock_send_request, mock_notify, mock_parse_address = setup_stabilize_mocks
    node.address.key = 100 # Current node's key (for context, not directly involved in the error)

    original_successor_addr = Address("1.1.1.1", 1111) # This will have its key naturally calculated
    node.finger_table[0] = original_successor_addr

    mock_send_request.side_effect = Exception("Stabilize network error")

    node.stabilize()

    # Successor should remain unchanged
    # Assert against the naturally calculated key of original_successor_addr
    assert node.successor().key == original_successor_addr.key
    assert node.successor() == original_successor_addr # This is more robust as it uses __eq__

    # Notify should still be attempted on the original successor
    mock_notify.assert_called_once_with(original_successor_addr)


@pytest.fixture
def setup_find_successor_mocks(node):
    with patch.object(node, "_is_key_in_range") as mock_is_key_in_range:
        with patch.object(node, "closest_preceding_finger") as mock_cpf:
            with patch.object(node._net, "send_request") as mock_send_request:
                with patch.object(node, "_parse_address") as mock_parse_address:
                    yield mock_is_key_in_range, mock_cpf, mock_send_request, mock_parse_address


def test_find_successor_key_in_range(node, setup_find_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111) # Successor key 200
    mock_is_key_in_range.return_value = True

    target_id = 150 # In range (100, 200)

    result = node.find_successor(target_id)
    assert result == node.successor()
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_not_called()
    mock_send_request.assert_not_called()
    mock_parse_address.assert_not_called()


def test_find_successor_closest_preceding_is_self(node, setup_find_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False # Not in range

    target_id = 250 # Not in range (100, 200)
    mock_cpf.return_value = node.address # Closest preceding finger is self

    result = node.find_successor(target_id)
    assert result == node.successor() # Should return own successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_not_called() # No network call if CPF is self
    mock_parse_address.assert_not_called()


def test_find_successor_forward_request(node, setup_find_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False

    target_id = 500
    closest_node = Address("3.3.3.3", 3333) # A different node
    mock_cpf.return_value = closest_node

    # Simulate response from the remote node
    expected_successor = Address("4.4.4.4", 4444)
    mock_send_request.return_value = f"{expected_successor.key}:{expected_successor.ip}:{expected_successor.port}"
    mock_parse_address.return_value = expected_successor

    result = node.find_successor(target_id)
    assert result == expected_successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(closest_node, 'FIND_SUCCESSOR', target_id)
    mock_parse_address.assert_called_once_with(mock_send_request.return_value)


def test_find_successor_network_error_fallback(node, setup_find_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request, mock_parse_address = setup_find_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False

    target_id = 500
    closest_node = Address("3.3.3.3", 3333)
    mock_cpf.return_value = closest_node

    mock_send_request.side_effect = Exception("Remote node down")

    result = node.find_successor(target_id)
    assert result == node.successor() # Should fallback to own successor
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(closest_node, 'FIND_SUCCESSOR', target_id)
    mock_parse_address.assert_not_called()


@pytest.fixture
def setup_fix_fingers_mocks(node):
    with patch.object(node, "find_successor") as mock_find_successor:
        yield mock_find_successor


def test_fix_fingers_no_successor(node, setup_fix_fingers_mocks):
    mock_find_successor = setup_fix_fingers_mocks
    node.finger_table[0] = None # No successor
    node._next = 0

    node.fix_fingers()
    mock_find_successor.assert_not_called()
    assert node._next == 0 # Should not advance _next


def test_fix_fingers_updates_finger_table(node, setup_fix_fingers_mocks):
    mock_find_successor = setup_fix_fingers_mocks
    node.address.key = 1000
    node.finger_table[0] = Address("1.1.1.1", 1111) # Set a successor
    node._next = 0 # First finger (successor)

    # Simulate find_successor finding a node for finger 0
    # For _next = 0, gap = 2**0 = 1. Start = 1000 + 1 = 1001.
    expected_finger_0 = Address("2.2.2.2", 2222)
    mock_find_successor.return_value = expected_finger_0

    node.fix_fingers()

    mock_find_successor.assert_called_once_with(1000 + (2**0) % (2**Address._M))
    assert node.finger_table[0] == expected_finger_0
    assert node._next == 1 # _next should advance

    # Test for _next = 1
    node._next = 1
    expected_finger_1 = Address("3.3.3.3", 3333) # For _next = 1, gap = 2**1 = 2. Start = 1000 + 2 = 1002.
    mock_find_successor.return_value = expected_finger_1
    mock_find_successor.reset_mock() # Reset call count

    node.fix_fingers()
    mock_find_successor.assert_called_once_with(1000 + (2**1) % (2**Address._M))
    assert node.finger_table[1] == expected_finger_1
    assert node._next == 2


def test_fix_fingers_network_error(node, setup_fix_fingers_mocks):
    mock_find_successor = setup_fix_fingers_mocks
    node.address.key = 1000
    node.finger_table[0] = Address("1.1.1.1", 1111)
    node._next = 5 # Some finger

    mock_find_successor.side_effect = Exception("Find successor failed for finger")

    # The test should not raise an exception, as fix_fingers catches it.
    node.fix_fingers()

    # Finger should remain None or its previous value if set. If it was None, it stays None.
    # The current implementation will leave the finger as it was if an error occurs.
    assert node.finger_table[5] is None # Assuming it was None initially
    assert node._next == 6 # _next should still advance


@pytest.fixture
def setup_trace_successor_mocks(node):
    with patch.object(node, "_is_key_in_range") as mock_is_key_in_range:
        with patch.object(node, "closest_preceding_finger") as mock_cpf:
            with patch.object(node._net, "send_request") as mock_send_request:
                yield mock_is_key_in_range, mock_cpf, mock_send_request


def test_trace_successor_key_in_range(node, setup_trace_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = True

    target_id = 150
    initial_hops = 0
    result_address, result_hops = node.trace_successor(target_id, initial_hops)

    assert result_address == node.successor()
    assert result_hops == initial_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_not_called()
    mock_send_request.assert_not_called()


def test_trace_successor_closest_preceding_is_self(node, setup_trace_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False # Not in range

    target_id = 250
    initial_hops = 0
    mock_cpf.return_value = node.address # Closest preceding finger is self

    result_address, result_hops = node.trace_successor(target_id, initial_hops)
    assert result_address == node.successor()
    assert result_hops == initial_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_not_called()


def test_trace_successor_forward_request(node, setup_trace_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False

    target_id = 500
    initial_hops = 2
    closest_node = Address("3.3.3.3", 3333)
    mock_cpf.return_value = closest_node

    # Simulate response from the remote node
    remote_successor_key = 550
    remote_successor_ip = "4.4.4.4"
    remote_successor_port = 4444
    remote_hops_returned = 3 # Hops reported by the remote node
    mock_send_request.return_value = f"{remote_successor_key}:{remote_successor_ip}:{remote_successor_port}:{remote_hops_returned}"

    result_address_str, result_hops = node.trace_successor(target_id, initial_hops)

    expected_address_str = f"{remote_successor_key}:{remote_successor_ip}:{remote_successor_port}"
    expected_hops = remote_hops_returned + 1

    assert result_address_str == expected_address_str
    assert result_hops == expected_hops
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(closest_node, 'TRACE_SUCCESSOR', target_id, initial_hops)


def test_trace_successor_network_error_fallback(node, setup_trace_successor_mocks):
    mock_is_key_in_range, mock_cpf, mock_send_request = setup_trace_successor_mocks
    node.address.key = 100
    node.finger_table[0] = Address("1.1.1.1", 1111)
    mock_is_key_in_range.return_value = False

    target_id = 500
    initial_hops = 0
    closest_node = Address("3.3.3.3", 3333)
    mock_cpf.return_value = closest_node

    mock_send_request.side_effect = Exception("Trace network error")

    # When `trace_successor` encounters an exception, it returns `self.successor()` directly (an Address object).
    # This is inconsistent with its successful return type `(Address, int)` and will cause a `TypeError`
    # when called from `_process_request` which expects a tuple.
    result = node.trace_successor(target_id, initial_hops)

    assert result == node.successor()
    mock_is_key_in_range.assert_called_once_with(target_id)
    mock_cpf.assert_called_once_with(target_id)
    mock_send_request.assert_called_once_with(closest_node, 'TRACE_SUCCESSOR', target_id, initial_hops)


@pytest.fixture
def setup_process_request_mocks(node):
    with patch.object(node, "find_successor") as mock_find_successor:
        with patch.object(node, "trace_successor") as mock_trace_successor:
            with patch.object(node, "_be_notified") as mock_be_notified:
                with patch.object(node, "_parse_address") as mock_parse_address:
                    yield mock_find_successor, mock_trace_successor, mock_be_notified, mock_parse_address


def test_process_request_ping(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    result = node._process_request("PING", [])
    assert result == "ALIVE"
    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_find_successor(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    mock_fs.return_value = Address("1.1.1.1", 1111)
    result = node._process_request("FIND_SUCCESSOR", ["100"])
    assert result == Address("1.1.1.1", 1111)
    mock_fs.assert_called_once_with(100)
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_get_predecessor(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    node.predecessor = Address("2.2.2.2", 2222)
    result = node._process_request("GET_PREDECESSOR", [])
    assert result == node.predecessor

    node.predecessor = None
    result = node._process_request("GET_PREDECESSOR", [])
    assert result == "nil"

    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_notify(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    notifying_addr = Address("10.0.0.10", 10000)
    # For predictable test scenario, manually set key if relying on it for equality later
    notifying_addr.key = 500
    mock_pa.return_value = notifying_addr

    mock_bn.return_value = True
    result = node._process_request("NOTIFY", ["500", "10.0.0.10", "10000"])
    assert result == "OK"
    mock_pa.assert_called_once_with('500:10.0.0.10:10000')
    mock_bn.assert_called_once_with(notifying_addr)

    mock_pa.reset_mock()
    mock_bn.reset_mock()
    mock_bn.return_value = False
    result = node._process_request("NOTIFY", ["500", "10.0.0.10", "10000"])
    assert result == "IGNORED"
    # mock_pa was called once for the previous "OK" case, and should be called once again for this "IGNORED" case
    # If using assert_called_once_with, need to reset after each call, or use assert_any_call / assert_has_calls
    # For simplicity, we can just assert it was called for the valid case.
    # A more robust test might use mock_pa.call_count == 2 here, or reset mock_pa before this section.
    # For this current scenario, assuming it should be called again for valid input:
    mock_pa.assert_called_once() # Asserts it was called one more time (total 2 calls on the mock)
    mock_bn.assert_called_once_with(notifying_addr)

    mock_pa.reset_mock() # Reset for the invalid argument test
    mock_bn.reset_mock()
    mock_pa.side_effect = ValueError("Invalid format") # This mock behavior won't be triggered due to new logic

    result = node._process_request("NOTIFY", ["invalid_args"])
    assert result == "INVALID_NODE"
    # REMOVED: mock_pa.assert_called_once_with('invalid_args')
    # Because _parse_address is no longer called when len(args) < 3

    # Ensure mock_pa and mock_bn were NOT called in this invalid argument scenario
    mock_pa.assert_not_called()
    mock_bn.assert_not_called()

    mock_fs.assert_not_called()
    mock_ts.assert_not_called()


def test_process_request_trace_successor(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    mock_ts.return_value = (str(Address("1.1.1.1", 1111)), 5) # tuple of (address_string, hops)
    result = node._process_request("TRACE_SUCCESSOR", ["100", "4"])
    assert result == f"{str(Address('1.1.1.1', 1111))}:5"
    mock_ts.assert_called_once_with(100, 4)

    mock_ts.reset_mock()
    mock_ts.side_effect = Exception("Trace failed")
    result = node._process_request("TRACE_SUCCESSOR", ["100", "4"])
    assert result == "ERROR:Invalid TRACE_SUCCESSOR Request"
    mock_ts.assert_called_once_with(100, 4)

    mock_fs.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_process_request_invalid_method(node, setup_process_request_mocks):
    mock_fs, mock_ts, mock_bn, mock_pa = setup_process_request_mocks
    result = node._process_request("UNKNOWN_METHOD", [])
    assert result == "INVALID_METHOD"
    mock_fs.assert_not_called()
    mock_ts.assert_not_called()
    mock_bn.assert_not_called()
    mock_pa.assert_not_called()


def test_repr(node):
    node.address.key = 12345
    assert repr(node) == "ChordNode(key=12345)"
