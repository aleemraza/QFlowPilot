
from qflowpilot.profiler.cost_estimator import (
    CostEstimator,
    CostModelConfig,
    CostMode,
)


def test_monetary_cost():
    config = CostModelConfig(
        currency="USD",
        qpu_cost_per_second=0.05,
        qpu_cost_per_shot=0.0001,
        classical_cost_per_cpu_second=0.001,
        communication_cost_per_gb=0.02,
    )

    estimator = CostEstimator(config)

    result = estimator.estimate(
        qpu_execution_time_s=10.0,
        shots=1000,
        classical_cpu_time_s=2.0,
        communication_bytes=500_000_000,
        mode=CostMode.MONETARY,
    )

    print("\nMONETARY COST ESTIMATION")
    print("-" * 45)
    print("QPU cost:", result.qpu.monetary_cost)
    print("Classical cost:", result.classical.monetary_cost)
    print("Communication cost:", result.communication.monetary_cost)
    print("Total cost:", result.total_cost, result.currency)
    print("Cost per shot:", result.monetary_cost_per_shot)
    print("Complete:", result.is_complete)

    assert result.qpu.monetary_cost == 0.6
    assert result.classical.monetary_cost == 0.002
    assert result.communication.monetary_cost == 0.01
    assert abs(result.total_cost - 0.612) < 1e-9
    assert result.is_complete


if __name__ == "__main__":
    test_monetary_cost()
