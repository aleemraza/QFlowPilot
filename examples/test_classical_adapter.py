
from uuid import uuid4

from qflowpilot.adapters import ClassicalAdapter
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
)


def example_classical_solver(request):
    return {
        "solution": [0, 1, 0, 1],
        "objective_value": 4,
        "algorithm": "example_classical_solver",
    }


def main():
    adapter = ClassicalAdapter()

    request = ExecutionRequest(
        request_id=str(uuid4()),
        workload_id="classical_fallback_test",
        shots=1024,
        execution_mode=ExecutionMode.CLASSICAL,
        backend_name="local_classical",
        timeout_s=300,
    )

    result = adapter.execute(
        request,
        example_classical_solver,
    )

    print("Status:", result.status)
    print("Backend:", result.backend_name)
    print("Execution time:", result.execution_time_s)
    print("Classical output:")
    print(result.metadata["classical_output"])


if __name__ == "__main__":
    main()
