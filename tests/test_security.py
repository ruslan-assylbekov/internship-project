from src.core.security import hash_password, verify_password


def test_hash_is_not_the_plaintext():
    hashed = hash_password("correct horse battery")

    assert hashed != "correct horse battery"
    assert hashed.startswith("$2b$")


def test_hash_is_salted_so_repeats_differ():
    assert hash_password("same") != hash_password("same")


def test_verify_accepts_the_original_password():
    assert verify_password("correct horse battery", hash_password("correct horse battery"))


def test_verify_rejects_a_different_password():
    assert not verify_password("wrong", hash_password("correct horse battery"))


def test_verify_returns_false_for_non_hash_values():
    """Legacy plaintext rows must fail closed rather than raise."""
    assert not verify_password("plaintext", "plaintext")
    assert not verify_password("anything", "")
