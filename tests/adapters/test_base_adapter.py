
import pytest

from qflowpilot.adapters.base_adapter import BaseBackendAdapter
from qflowpilot.core.exceptions import BackendUnavailableError


class DummyBackendAdapter(BaseBackendAdapter):

    def __init__(
        self,
        available=True,
        backend_name="dummy_backend",
        backend_type="simulator",
    ):
        super().__init__(
            backend_name=backend_name,
            backend_type=backend_type,
            backend_version="1.0",
            available=available,
        )

    def execute(self, request, circuit):
        raise NotImplementedError


def test_adapter_initialization():

    backend = DummyBackendAdapter()

    assert backend.backend_name == "dummy_backend"
    assert backend.backend_type == "simulator"
    assert backend.backend_version == "1.0"


def test_backend_availability():

    backend = DummyBackendAdapter()

    assert backend.is_available() is True


def test_backend_unavailable():

    backend = DummyBackendAdapter(available=False)

    assert backend.is_available() is False


def test_backend_information():

    backend = DummyBackendAdapter()

    info = backend.get_backend_info()

    assert info["backend_name"] == "dummy_backend"
    assert info["backend_type"] == "simulator"
    assert info["backend_version"] == "1.0"
    assert info["is_available"] is True
    assert info["adapter"] == "DummyBackendAdapter"


def test_ensure_available():

    backend = DummyBackendAdapter()

    backend._ensure_available()


def test_ensure_unavailable():

    backend = DummyBackendAdapter(available=False)

    with pytest.raises(BackendUnavailableError):
        backend._ensure_available()


def test_invalid_backend_name():

    with pytest.raises(ValueError, match="backend_name"):
        DummyBackendAdapter(backend_name="")


def test_invalid_backend_type():

    with pytest.raises(ValueError, match="backend_type"):
        DummyBackendAdapter(backend_type="")


def test_repr():

    backend = DummyBackendAdapter()

    assert "dummy_backend" in repr(backend)
    assert "DummyBackendAdapter" in repr(backend)


def test_base_adapter_is_abstract():

    with pytest.raises(TypeError):
        BaseBackendAdapter(
            backend_name="test_backend",
            backend_type="simulator",
        )
