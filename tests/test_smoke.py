import mediabot


def test_package_exposes_version() -> None:
    assert mediabot.__version__ == "0.1.0"
