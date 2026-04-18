"""Tests for the utils module."""

import pytest
from mypackage.utils import greet, add_numbers, is_even


class TestGreet:
    """Tests for the greet function."""
    
    def test_greet_with_name(self):
        """Test greeting with a normal name."""
        assert greet("Alice") == "Hello, Alice!"
    
    def test_greet_with_empty_string(self):
        """Test greeting with an empty string."""
        assert greet("") == "Hello, !"


class TestAddNumbers:
    """Tests for the add_numbers function."""
    
    def test_add_positive_numbers(self):
        """Test adding two positive numbers."""
        assert add_numbers(2, 3) == 5
    
    def test_add_negative_numbers(self):
        """Test adding two negative numbers."""
        assert add_numbers(-2, -3) == -5
    
    def test_add_mixed_numbers(self):
        """Test adding positive and negative numbers."""
        assert add_numbers(5, -3) == 2
    
    def test_add_zero(self):
        """Test adding zero."""
        assert add_numbers(0, 5) == 5
        assert add_numbers(5, 0) == 5


class TestIsEven:
    """Tests for the is_even function."""
    
    def test_even_number(self):
        """Test with an even number."""
        assert is_even(4) is True
        assert is_even(0) is True
        assert is_even(-2) is True
    
    def test_odd_number(self):
        """Test with an odd number."""
        assert is_even(3) is False
        assert is_even(1) is False
        assert is_even(-1) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
