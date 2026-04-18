"""Utility functions for MyPackage."""


def greet(name: str) -> str:
    """Return a greeting message.
    
    Args:
        name: The name to greet.
        
    Returns:
        A greeting string.
    """
    return f"Hello, {name}!"


def add_numbers(a: int, b: int) -> int:
    """Add two numbers together.
    
    Args:
        a: First number.
        b: Second number.
        
    Returns:
        The sum of a and b.
    """
    return a + b


def is_even(number: int) -> bool:
    """Check if a number is even.
    
    Args:
        number: The number to check.
        
    Returns:
        True if the number is even, False otherwise.
    """
    return number % 2 == 0


def fibonacci(n: int) -> int:
    """Calculate the nth Fibonacci number.
    
    Args:
        n: The position in the Fibonacci sequence (0-indexed).
        
    Returns:
        The nth Fibonacci number.
        
    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b
