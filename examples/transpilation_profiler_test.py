
from qiskit import QuantumCircuit

from qflowpilot.profiler.transpilation_profiler import (
    TranspilationProfiler,
)


def main():
    # Create a logical QAOA-like circuit.
    circuit = QuantumCircuit(3)

    circuit.h([0, 1, 2])
    circuit.rzz(0.5, 0, 2)
    circuit.rzz(0.7, 1, 2)
    circuit.rx(0.3, 0)
    circuit.rx(0.3, 1)
    circuit.rx(0.3, 2)
    circuit.measure_all()

    # Define a small connectivity-constrained target.
    # This is a compilation target, not a real QPU.
    coupling_map = [
        [0, 1],
        [1, 0],
        [1, 2],
        [2, 1],
    ]

    profiler = TranspilationProfiler(
        basis_gates=["rz", "sx", "x", "cx"],
        coupling_map=coupling_map,
        optimization_level=1,
        seed_transpiler=42,
    )

    result = profiler.profile_circuit(circuit)

    print("\n" + "=" * 60)
    print("QFLOWPILOT TRANSPILATION PROFILE")
    print("=" * 60)

    print("\nLOGICAL CIRCUIT")
    print("Qubits:", result.logical_num_qubits)
    print("Depth:", result.logical_depth)
    print("Gates:", result.logical_gate_count)
    print("Two-qubit gates:", result.logical_two_qubit_gates)
    print("Gate counts:", result.logical_gate_counts)

    print("\nTRANSPILED CIRCUIT")
    print("Qubits:", result.transpiled_num_qubits)
    print("Depth:", result.transpiled_depth)
    print("Gates:", result.transpiled_gate_count)
    print("Two-qubit gates:", result.transpiled_two_qubit_gates)
    print("Native gate counts:", result.native_gate_counts)

    print("\nLAYOUT AND ROUTING")
    print("Initial layout:", result.initial_layout)
    print("Final layout:", result.final_layout)
    print("Explicit SWAP count:", result.explicit_swap_count)
    print("Routing overhead:", result.routing_overhead)

    print("\nOPTIMIZATION")
    print("Optimization level:", result.optimization_level)
    print("Depth overhead:", result.depth_overhead)
    print("Gate count overhead:", result.gate_count_overhead)
    print(
        "Transpilation time:",
        f"{result.transpilation_time_s:.6f} seconds",
    )

    print("\nSCHEDULING")
    print("Scheduled duration:", result.scheduled_duration)
    print("Duration unit:", result.scheduled_duration_unit)
    print("Explicit idle time:", result.explicit_idle_time)

    print("\nTRANSPILED CIRCUIT")
    print(result.transpiled_circuit)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
