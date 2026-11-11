
import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import DiagonalGate
from qiskit_aer import AerSimulator


def hamming_distance(a, b):
    return int(np.count_nonzero(np.asarray(a) != np.asarray(b)))


def build_localization_grover_circuit(
    query,
    reference,
    threshold=0
):

    query = np.asarray(query, dtype=np.uint8)
    reference = np.asarray(reference, dtype=np.uint8)

    M = len(query)
    N = len(reference)

    window_count = N - M + 1

    if window_count < 2:
        raise ValueError("At least two candidate windows are required.")

    n_qubits = int(np.ceil(np.log2(window_count)))
    state_count = 2 ** n_qubits

    # Classical oracle construction for this initial prototype.
    matching_indices = []

    for i in range(window_count):

        candidate = reference[i:i + M]

        distance = hamming_distance(query, candidate)

        if distance <= threshold:
            matching_indices.append(i)

    if not matching_indices:
        raise ValueError("No matching windows found.")

    # Phase oracle.
    diagonal = np.ones(state_count)

    for index in matching_indices:
        diagonal[index] = -1

    oracle = DiagonalGate(diagonal).to_gate(label="Oracle")

    qc = QuantumCircuit(n_qubits, n_qubits)

    # 1. Initial superposition.
    qc.h(range(n_qubits))

    # 2. Grover iterations.
    iterations = max(
        1,
        int(np.floor(
            np.pi / 4 * np.sqrt(
                state_count / len(matching_indices)
            )
        ))
    )

    for _ in range(iterations):

        qc.append(oracle, range(n_qubits))

        # Diffusion operator.
        qc.h(range(n_qubits))
        qc.x(range(n_qubits))

        if n_qubits == 1:
            qc.z(0)
        else:
            qc.h(n_qubits - 1)
            qc.mcx(
                list(range(n_qubits - 1)),
                n_qubits - 1
            )
            qc.h(n_qubits - 1)

        qc.x(range(n_qubits))
        qc.h(range(n_qubits))

    # 3. Measurement.
    qc.measure(range(n_qubits), range(n_qubits))

    return qc, matching_indices, iterations


# Example using a localization AP pattern.
if __name__ == "__main__":

    query = [1, 1, 0, 1]

    reference = [
        1, 0, 1, 1, 0, 1,
        1, 1, 0, 1, 1
    ]

    circuit, matches, iterations = (
        build_localization_grover_circuit(
            query,
            reference,
            threshold=0
        )
    )

    print("Matching indices:", matches)
    print("Grover iterations:", iterations)

    print("\nQuantum circuit:")
    print(circuit.draw("text"))

    simulator = AerSimulator()

    compiled = transpile(circuit, simulator)

    result = simulator.run(
        compiled,
        shots=2048
    ).result()

    print("\nMeasurement counts:")
    print(result.get_counts())
