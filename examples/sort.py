"""
A simple sorting function with a bug.

This function is supposed to sort a list of numbers in ascending order,
but it has a subtle bug that causes incorrect sorting in some cases.
"""


def sort_numbers(numbers):
    """
    Sort a list of numbers in ascending order.

    Args:
        numbers: List of numbers to sort

    Returns:
        Sorted list of numbers
    """
    if not numbers:
        return []

    # Create a copy to avoid modifying the original
    result = numbers.copy()

    # Bubble sort implementation
    n = len(result)
    for i in range(n):
        for j in range(0, n - i):
            if result[j] > result[j + 1]:
                # Swap elements
                result[j], result[j + 1] = result[j + 1], result[j]

    return result


if __name__ == "__main__":
    # Test cases
    test1 = [3, 1, 4, 1, 5, 9, 2, 6]
    print(f"Input: {test1}")
    print(f"Output: {sort_numbers(test1)}")
    print(f"Expected: {sorted(test1)}")

    test2 = [5, 2, 8, 1, 9]
    print(f"\nInput: {test2}")
    print(f"Output: {sort_numbers(test2)}")
    print(f"Expected: {sorted(test2)}")

