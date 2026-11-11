
from uuid import uuid4

from qiskit import QuantumCircuit

from qflowpilot.adapters import (
    AerIdealAdapter,
    AerNoisyAdapter,
)
from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
)


def create_bell_circuit():
    circuit = QuantumCircuit(2)
    circuit.h(0)
    circuit.cx(0, 1)
    circuit.measure_all()
    return circuit


def create_request(execution_mode, backend_name):
    return ExecutionRequest(
        request_id=str(uuid4()),
        workload_id="bell_state_comparison",
        shots=1024,
        execution_mode=execution_mode,
        backend_name=backend_name,
        seed=42,
        timeout_s=300,
    )


def print_result(title, result):
    print(f"\n{title}")
    print("-" * 50)
    print("Status:", result.status)
    print("Backend:", result.backend_name)
    print("Shots:", result.shots)
    print("Counts:", result.counts)
    print("Execution time:", result.execution_time_s, "seconds")


def main():
    circuit = create_bell_circuit()

    # Ideal execution.
    ideal_adapter = AerIdealAdapter()

    ideal_request = create_request(
        ExecutionMode.IDEAL_SIMULATOR,
        "aer_ideal",
    )

    ideal_result = ideal_adapter.execute(
        ideal_request,
        circuit,
    )

    # Noisy execution.
    noisy_adapter = AerNoisyAdapter(
        single_qubit_error=0.001,
        two_qubit_error=0.01,
        readout_error=0.02,
    )

    noisy_request = create_request(
        ExecutionMode.NOISY_SIMULATOR,
        "aer_noisy",
    )

    noisy_result = noisy_adapter.execute(
        noisy_request,
        circuit,
    )

    # Display results.
    print_result("IDEAL SIMULATOR", ideal_result)
    print_result("NOISY SIMULATOR", noisy_result)

    print("\nNOISE PARAMETERS")
    print("-" * 50)
    print(noisy_adapter.get_noise_parameters())


if __name__ == "__main__":
    main()
