
from qflowpilot.core.models import CircuitProfile
from qflowpilot.profiler.resource_profiler import (
    ResourceProfiler,
    ResourceLimits,
)


def main():
    # Step 1: Create example circuit profiles.
    # Normally, CircuitProfiler generates these profiles.

    circuit_profiles = [
        CircuitProfile(
            num_qubits=3,
            depth=5,
            total_gates=12,
            two_qubit_gates=4,
        ),
        CircuitProfile(
            num_qubits=4,
            depth=8,
            total_gates=20,
            two_qubit_gates=6,
        ),
        CircuitProfile(
            num_qubits=3,
            depth=6,
            total_gates=15,
            two_qubit_gates=5,
        ),
    ]

    # Step 2: Initialize ResourceProfiler.
    profiler = ResourceProfiler()

    # Step 3: Define available resource limits.
    limits = ResourceLimits(
        max_qubits=10,
        max_shots=15000,
        max_circuit_depth=20,
        max_two_qubit_gates=100,
        max_classical_cpu_time_s=60,
        max_memory_mb=2048,
    )

    # Step 4: Generate resource profile.
    profile = profiler.profile_circuits(
        circuit_profiles=circuit_profiles,
        workload_id="qaoa_workload_001",
        shots_per_circuit=1000,
        variance=0.25,
        target_precision=0.02,
        confidence_level=0.95,
        limits=limits,
        classical_cpu_time_s=12.5,
        memory_mb=512,
        qpu_busy_time_s=70,
        qpu_available_time_s=100,
    )

    # Step 5: Display results.
    print("\nRESOURCE PROFILE")
    print("=" * 50)

    print("\nQuantum resources")
    print("Number of circuits:", profile.quantum.num_circuits)
    print("Required qubits:", profile.quantum.required_qubits)
    print("Total gates:", profile.quantum.total_gates)
    print("Two-qubit gates:", profile.quantum.total_two_qubit_gates)
    print("Maximum depth:", profile.quantum.maximum_circuit_depth)

    print("\nShot requirements")
    print("Shots per circuit:", profile.quantum.shots_per_circuit)
    print("Total requested shots:", profile.quantum.total_requested_shots)
    print(
        "Estimated shots per circuit:",
        profile.quantum.estimated_shots_per_circuit,
    )
    print(
        "Estimated total required shots:",
        profile.quantum.estimated_total_required_shots,
    )

    print("\nClassical resources")
    print("CPU time:", profile.classical.cpu_time_s)
    print("Memory (MB):", profile.classical.memory_mb)

    print("\nResource feasibility")
    print("Feasible:", profile.feasible)
    print("Violations:", profile.violations)

    print("\nQPU utilization")
    print("Utilization:", profile.qpu_utilization)


if __name__ == "__main__":
    main()
