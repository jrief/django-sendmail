import pytest
from sendmail.connections import connections
from .conftest import ErrorRaisingBackend, SlowTestBackend


def test_connections():
    assert isinstance(connections['error'], ErrorRaisingBackend)
    assert isinstance(connections['slow_backend'], SlowTestBackend)

    with pytest.raises(KeyError):
        conn = connections['not_valid']
