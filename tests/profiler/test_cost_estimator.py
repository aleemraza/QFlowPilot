
import pytest

from qflowpilot.profiler.cost_estimator import (
    CostEstimator,
    CostModelConfig,
    CostMode,
)


def test_missing_monetary_rate():
    config = CostModelConfig(
        qpu_cost_per_second=0.05,
        qpu_cost_per_shot=0.0001,
        classical_cost_per_cpu_second=0.001,
        # Communication rate intentionally unavailable.
    )

    result = CostEstimator(config).estimate(
        qpu_execution_time_s=10,
        shots=1000,
        classical_cpu_time_s=2,
        communication_bytes=1000,
        mode=CostMode.MONETARY,
    )

    assert result.total_cost is None
    assert result.currency is None
    assert not result.is_complete
    assert "communication" in result.metadata["missing_components"]


def test_negative_execution_time():
    estimator = CostEstimator(CostModelConfig())

    with pytest.raises(ValueError):
        estimator.estimate(
            qpu_execution_time_s=-1,
            shots=100,
        )


def test_invalid_shots():
    estimator = CostEstimator(CostModelConfig())

    with pytest.raises(ValueError):
        estimator.estimate(
            qpu_execution_time_s=1,
            shots=-10,
        )
