# test_chord.py
import pytest
import hashlib
from unittest.mock import patch

from chord import Address
from chord import Node as ChordNode

ip = "1.2.3.4"
port = 5
key = f"{ip}:{port}"
key = int(hashlib.sha1(key.encode()).hexdigest(), 16) % (2**16)

# for start() so we don't use sockets
@pytest.fixture(autouse=True)
def mock_start():
    with patch.object(ChordNode, 'start', return_value=None):
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

def test_is_key_in_range(node):
    node.create()
     # Test simple case within range
    assert node._is_key_in_range(node.address.key + 1) == True
    
    # Test exact node key (should return False)
    assert node._is_key_in_range(node.address.key) == False
    
    # Test successor's key (should return False)
    assert node._is_key_in_range(node.successor().key) == False
    
    # Test wrap-around scenario
    # Create a scenario where node's key is near the end of the hash space
    node.address.key = 65530  # Near max of 16-bit hash space
    node.finger_table[0] = Address(
        ip='5.6.7.8', 
        port=6000
    )
    node.successor().key = 50
    
    # Test wrap-around cases
    assert node._is_key_in_range(65535) == True  # Just before wrap
    assert node._is_key_in_range(40) == True    # Just after wrap
    assert node._is_key_in_range(51) == False   # Beyond successor
    assert node._is_key_in_range(65529) == False  # Before node

import pytest

def test_closest_preceding_finger_basic(node):
    """Test basic finger table routing"""
    # Create a mock finger table with some nodes
    node.finger_table = [
        Address('1.1.1.1', 5001),
        Address('2.2.2.2', 5002),
        Address('3.3.3.3', 5003)
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
        Address('1.1.1.1', 5001),
        Address('2.2.2.2', 5002),
        Address('3.3.3.3', 5003)
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
    node.finger_table = [
        None,
        Address('1.1.1.1', 5001),
        None,
        Address('2.2.2.2', 5002)
    ]
    node.finger_table[1].key = 30
    node.finger_table[3].key = 50
    
    # Should return the first valid finger
    result = node.closest_preceding_finger(40)
    assert result == node.finger_table[1]
    
    # When no valid finger found
    result = node.closest_preceding_finger(10)
    assert result == node.address

