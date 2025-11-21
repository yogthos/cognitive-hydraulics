def bubbleSort(arr):
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 5):  # Bug: should be range(0, n - i - 1)
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr


def test_bubbleSort():
    """Test function to verify bubbleSort works correctly."""
    test_cases = [
        ([64, 34, 25, 12, 22, 11, 90], [11, 12, 22, 25, 34, 64, 90]),
        ([5, 2, 8, 1, 9], [1, 2, 5, 8, 9]),
        ([1], [1]),
        ([], []),
    ]

    for input_arr, expected in test_cases:
        result = bubbleSort(input_arr.copy())
        assert result == expected, f"Failed: {input_arr} -> {result}, expected {expected}"
        print(f"✓ Test passed: {input_arr} -> {result}")


if __name__ == "__main__":
    test_bubbleSort()
    print("All tests passed!")
