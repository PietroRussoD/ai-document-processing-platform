"""Package-level tests."""

from document_platform import __doc__


def test_package_has_a_description() -> None:
    assert __doc__ == "AI Document Processing Platform."
