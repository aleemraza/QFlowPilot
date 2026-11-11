
from uuid import uuid4

from qiskit import QuantumCircuit

from qflowpilot.adapters import AerIdealAdapter
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
)


def main():
    # 1. Create a Bell-state circuit.
    circuit = QuantumCircuit(2)

    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure_all()

    print("\nOriginal Bell-state circuit:")
    print(circuit.draw())

    # 2. Create the ideal Aer adapter.
    adapter = AerIdealAdapter(
        backend_name="aer_ideal",
        optimization_level=1,
    )

    # 3. Create an execution request.
    request = ExecutionRequest(
        request_id=str(uuid4()),
        workload_id="bell_state_test",
        shots=1024,
        execution_mode=ExecutionMode.IDEAL_SIMULATOR,
        backend_name="aer_ideal",
        seed=42,
        timeout_s=300,
    )

    # 4. Execute the circuit.
    result = adapter.execute(request, circuit)

    # 5. Display the results.
    print("\nExecution results")
    print("-" * 40)

    print("Status:", result.status)
    print("Backend:", result.backend_name)
    print("Shots:", result.shots)
    print("Counts:", result.counts)
    print("Execution time:", result.execution_time_s, "seconds")

    print("\nBackend metadata:")
    for key, value in result.metadata.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
