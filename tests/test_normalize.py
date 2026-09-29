from dcai.normalize.exercise import instructions_hash


def test_instructions_hash_is_deterministic():
    a = instructions_hash("Write a function", "coding", "python")
    b = instructions_hash("Write a function", "coding", "python")
    assert a == b


def test_instructions_hash_ignores_whitespace_differences():
    a = instructions_hash("Write  a\nfunction", "coding", "python")
    b = instructions_hash("Write a function", "coding", "python")
    assert a == b


def test_instructions_hash_differs_by_type():
    coding = instructions_hash("Same text", "coding", "python")
    mcq = instructions_hash("Same text", "mcq", "python")
    assert coding != mcq
