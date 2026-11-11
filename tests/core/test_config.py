
import pytest

from qflowpilot.core.config import (
    ShotConfig,
    QualityConfig,
    BackendConfig,
    RuntimeConfig,
    QFlowPilotConfig,
)


def test_default_configuration():
    config = QFlowPilotConfig()

    assert config.shots.initial_shots == 1024
    assert config.quality.confidence_level == 0.95
    assert config.backend.execution_mode == "ideal_simulator"
    assert config.runtime.random_seed == 42


def test_custom_shot_configuration():
    shots = ShotConfig(
        initial_shots=2048,
        min_shots=100,
        max_shots=50000,
        additional_shots=1024,
    )

    assert shots.initial_shots == 2048
    assert shots.max_shots == 50000


def test_invalid_shot_configuration():
    with pytest.raises(ValueError):
        ShotConfig(
            initial_shots=200000,
            min_shots=100,
            max_shots=100000,
        )


def test_quality_configuration():
    quality = QualityConfig(
        confidence_level=0.99,
        min_success_probability=0.90,
        min_application_score=0.95,
        max_standard_error=0.02,
    )

    assert quality.confidence_level == 0.99
    assert quality.min_application_score == 0.95


def test_invalid_quality_configuration():
    with pytest.raises(ValueError):
        QualityConfig(confidence_level=1.5)


def test_backend_configuration():
    backend = BackendConfig(
        execution_mode="noisy_simulator",
        backend_name="fake_backend_noise_model",
        optimization_level=2,
    )

    assert backend.execution_mode == "noisy_simulator"
    assert backend.optimization_level == 2


def test_invalid_backend_configuration():
    with pytest.raises(ValueError):
        BackendConfig(execution_mode="unknown_backend")


def test_runtime_configuration():
    runtime = RuntimeConfig(
        execution_timeout_s=600,
        max_retries=3,
        random_seed=123,
    )

    assert runtime.execution_timeout_s == 600
    assert runtime.max_retries == 3


def test_invalid_runtime_configuration():
    with pytest.raises(ValueError):
        RuntimeConfig(max_retries=-1)


def test_configuration_from_dictionary():
    data = {
        "shots": {
            "initial_shots": 4096,
            "min_shots": 100,
            "max_shots": 50000,
            "additional_shots": 2048,
        },
        "backend": {
            "execution_mode": "ideal_simulator",
            "backend_name": "aer_simulator",
        },
    }

    config = QFlowPilotConfig.from_dict(data)

    assert config.shots.initial_shots == 4096
    assert config.shots.additional_shots == 2048
    assert config.backend.backend_name == "aer_simulator"


def test_unknown_configuration_field():
    data = {
        "shots": {
            "initial_shots": 1024,
            "unknown_setting": 10,
        }
    }

    with pytest.raises(ValueError):
        QFlowPilotConfig.from_dict(data)


def test_yaml_load_and_save(tmp_path):
    original = QFlowPilotConfig()

    yaml_path = tmp_path / "test_config.yaml"

    original.to_yaml(str(yaml_path))

    loaded = QFlowPilotConfig.from_yaml(str(yaml_path))

    assert loaded.to_dict() == original.to_dict()


def test_load_missing_yaml_file(tmp_path):
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError):
        QFlowPilotConfig.from_yaml(str(missing_path))
