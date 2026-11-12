
# """
# QFlowPilot: Single-circuit application-quality experiment.

# Supports:
#     - AerIdealAdapter
#     - AerNoisyAdapter

# Change ADAPTER_CHOICE to switch execution backends.

# Measures:
#     1. Exact ideal reference distribution
#     2. Application success probability
#     3. Observable expectation and variance
#     4. Total variation distance
#     5. Application-quality decision

# Uses existing QFlowPilot adapters and QualityProfiler.

# No additional adapters.
# No QCloudSimpy or QSimKit.
# """

# from __future__ import annotations

# import sys
# from pathlib import Path

# ROOT = Path(__file__).resolve().parents[1]

# if str(ROOT) not in sys.path:
#     sys.path.insert(0, str(ROOT))

# from qiskit import qasm2, qasm3
# from qiskit.quantum_info import Statevector

# from qflowpilot.adapters import (
#     AerIdealAdapter,
#     AerNoisyAdapter,
# )

# from qflowpilot.core.models import (
#     ExecutionMode,
#     ExecutionRequest,
#     WorkloadSpec,
#     WorkloadType,
# )

# from qflowpilot.profiler.quality_profiler import QualityProfiler


# # =========================================================
# # 1. EXPERIMENT CONFIGURATION
# # =========================================================

# DATASET = ROOT / "workloads" / "mqt_bench"

# CIRCUIT_FILE = (
#     DATASET / "dj_nativegates_ibm_falcon_opt2_5.qasm"
# )

# # Change only this variable:
# # "ideal" = AerIdealAdapter
# # "noisy" = AerNoisyAdapter

# ADAPTER_CHOICE = "noisy_simulator"

# SHOTS = 1024
# SEED = 42

# MIN_SUCCESS_PROBABILITY = 0.95
# MAX_TV_DISTANCE = 0.05

# REFERENCE_TOLERANCE = 1e-12


# # =========================================================
# # 2. DISPLAY HELPERS
# # =========================================================

# def section(title: str) -> None:
#     print("\n" + "=" * 75)
#     print(title)
#     print("=" * 75)


# # =========================================================
# # 3. ADAPTER SWITCHING RUNTIME
# # =========================================================

# def create_adapter(adapter_choice: str):

#     if adapter_choice == "noisy_simulator":

#         adapter = AerIdealAdapter(
#             optimization_level=1,
#         )

#         execution_mode = ExecutionMode.IDEAL_SIMULATOR

#     elif adapter_choice == "noisy_simulator":

#         adapter = AerNoisyAdapter(
#             optimization_level=1,
#             single_qubit_error=0.001,
#             two_qubit_error=0.01,
#             readout_error=0.02,
#         )

#         execution_mode = ExecutionMode.NOISY_SIMULATOR

#     else:
#         raise ValueError(
#             "ADAPTER_CHOICE must be either 'ideal' or 'noisy'."
#         )

#     return adapter, execution_mode


# # =========================================================
# # 4. LOAD ONE CIRCUIT
# # =========================================================

# def load_one_circuit(path: Path):

#     if not path.exists():
#         raise FileNotFoundError(path)

#     content = path.read_text(encoding="utf-8-sig")

#     first_line = next(
#         line.strip()
#         for line in content.splitlines()
#         if line.strip()
#         and not line.strip().startswith("//")
#     )

#     if "3.0" in first_line:
#         circuit = qasm3.loads(content)

#     elif "2.0" in first_line:
#         circuit = qasm2.loads(content)

#     else:
#         raise ValueError(
#             f"Unknown QASM version: {first_line}"
#         )

#     return circuit


# # =========================================================
# # 5. BUILD EXACT IDEAL REFERENCE DISTRIBUTION
# # =========================================================

# def build_reference_distribution(circuit):

#     measurement_map = {}

#     for instruction in circuit.data:

#         if instruction.operation.name != "measure":
#             continue

#         qubit = circuit.find_bit(
#             instruction.qubits[0]
#         ).index

#         classical_bit = circuit.find_bit(
#             instruction.clbits[0]
#         ).index

#         measurement_map[classical_bit] = qubit

#     if not measurement_map:
#         raise ValueError(
#             "Circuit has no measurement operations."
#         )

#     if len(measurement_map) != circuit.num_clbits:
#         raise ValueError(
#             "Every classical bit must have a measurement mapping."
#         )

#     unitary_circuit = circuit.remove_final_measurements(
#         inplace=False
#     )

#     if any(
#         instruction.operation.name == "measure"
#         for instruction in unitary_circuit.data
#     ):
#         raise ValueError(
#             "Circuit contains non-final measurements."
#         )

#     unitary_circuit.data = [
#         instruction
#         for instruction in unitary_circuit.data
#         if instruction.operation.name != "barrier"
#     ]

#     statevector = Statevector.from_instruction(
#         unitary_circuit
#     )

#     reference = {}

#     for basis_index, amplitude in enumerate(statevector.data):

#         probability = float(abs(amplitude) ** 2)

#         if probability < REFERENCE_TOLERANCE:
#             continue

#         classical_bits = ["0"] * circuit.num_clbits

#         for classical_bit, qubit in measurement_map.items():

#             bit_value = (basis_index >> qubit) & 1

#             classical_bits[
#                 circuit.num_clbits - 1 - classical_bit
#             ] = str(bit_value)

#         output = "".join(classical_bits)

#         reference[output] = (
#             reference.get(output, 0.0) + probability
#         )

#     total = sum(reference.values())

#     return {
#         output: probability / total
#         for output, probability in reference.items()
#     }


# # =========================================================
# # 6. COUNTS TO PROBABILITIES
# # =========================================================

# def counts_to_probabilities(counts):

#     total_shots = sum(counts.values())

#     if total_shots == 0:
#         raise ValueError(
#             "No measurement shots available."
#         )

#     probabilities = {}

#     for bitstring, count in counts.items():

#         output = str(bitstring).replace(" ", "")

#         probabilities[output] = (
#             probabilities.get(output, 0.0)
#             + count / total_shots
#         )

#     return probabilities


# # =========================================================
# # 7. TOTAL VARIATION DISTANCE
# # =========================================================

# def calculate_tv_distance(reference, measured):

#     all_outputs = set(reference) | set(measured)

#     return 0.5 * sum(
#         abs(
#             reference.get(output, 0.0)
#             - measured.get(output, 0.0)
#         )
#         for output in all_outputs
#     )


# # =========================================================
# # 8. MAIN EXPERIMENT
# # =========================================================

# def main():

#     section("QFLOWPILOT SINGLE-CIRCUIT QUALITY EXPERIMENT")

#     print("Circuit file :", CIRCUIT_FILE.name)
#     print("Adapter choice:", ADAPTER_CHOICE)
#     print("Shots        :", SHOTS)
#     print("Seed         :", SEED)

#     # -----------------------------------------------------
#     # Step 1: Load circuit
#     # -----------------------------------------------------

#     section("1. CIRCUIT LOADING")

#     circuit = load_one_circuit(CIRCUIT_FILE)

#     print("Circuit name :", circuit.name)
#     print("Qubits       :", circuit.num_qubits)
#     print("Classical bits:", circuit.num_clbits)
#     print("Depth        :", circuit.depth())
#     print("Gate count   :", circuit.size())

#     # -----------------------------------------------------
#     # Step 2: Exact ideal reference
#     # -----------------------------------------------------

#     section("2. IDEAL REFERENCE DISTRIBUTION")

#     reference = build_reference_distribution(circuit)

#     for output, probability in sorted(reference.items()):
#         print(f"{output}: {probability:.8f}")

#     expected_outputs = set(reference.keys())

#     expected_output = max(
#         reference,
#         key=reference.get,
#     )

#     print("\nMost probable expected output:", expected_output)
#     print("Number of ideal output states:", len(expected_outputs))

#     # -----------------------------------------------------
#     # Step 3: Initialize selected adapter
#     # -----------------------------------------------------

#     section("3. ADAPTER INITIALIZATION")

#     adapter, execution_mode = create_adapter(
#         ADAPTER_CHOICE
#     )

#     if not adapter.is_available():
#         raise RuntimeError(
#             f"{adapter.__class__.__name__} is unavailable."
#         )

#     print("Adapter      :", adapter.__class__.__name__)
#     print("Backend      :", adapter.backend_name)
#     print("Execution mode:", execution_mode.value)

#     print("\nBackend information:")
#     print(adapter.get_backend_info())

#     if isinstance(adapter, AerNoisyAdapter):

#         print("\nNoise parameters:")

#         for name, value in adapter.get_noise_parameters().items():
#             print(f"{name}: {value}")

#     # -----------------------------------------------------
#     # Step 4: Prepare workload and execution request
#     # -----------------------------------------------------

#     section("4. WORKLOAD PREPARATION")

#     workload = WorkloadSpec(
#         workload_id="qflowpilot_single_dj_quality",
#         name="Single DJ Circuit Quality Experiment",
#         workload_type=WorkloadType.BATCH,
#         algorithm="Deutsch-Jozsa",
#         application="Application-quality validation",
#         description="Single MQT Bench circuit experiment.",
#         metadata={
#             "dataset": "MQT Bench",
#         },
#     )

#     request = ExecutionRequest(
#         request_id="single_dj_quality_001",
#         workload_id=workload.workload_id,
#         shots=SHOTS,

#         # Important: this now matches the selected adapter.
#         execution_mode=execution_mode,

#         backend_name=adapter.backend_name,
#         seed=SEED,

#         metadata={
#             "circuit_name": circuit.name,
#             "dataset_source": CIRCUIT_FILE.name,
#             "adapter_choice": ADAPTER_CHOICE,
#         },
#     )

#     # -----------------------------------------------------
#     # Step 5: Execute circuit
#     # -----------------------------------------------------

#     section("5. CIRCUIT EXECUTION")

#     result = adapter.execute(
#         request,
#         circuit,
#     )

#     print("Execution status:", result.status)
#     print("Execution adapter:", adapter.__class__.__name__)
#     print("Backend         :", result.backend_name)
#     print("Execution time  :", result.execution_time_s)
#     print("Actual shots    :", result.shots)
#     print("Measured counts :", result.counts)

#     if not result.counts:
#         raise RuntimeError(
#             "Adapter returned no measurement counts."
#         )

#     # -----------------------------------------------------
#     # Step 6: Measured distribution
#     # -----------------------------------------------------

#     section("6. MEASURED DISTRIBUTION")

#     measured = counts_to_probabilities(
#         result.counts
#     )

#     for output, probability in sorted(measured.items()):
#         print(f"{output}: {probability:.8f}")

#     # -----------------------------------------------------
#     # Step 7: Application success probability
#     # -----------------------------------------------------

#     section("7. APPLICATION SUCCESS PROBABILITY")

#     success_probability = sum(
#         measured.get(output, 0.0)
#         for output in expected_outputs
#     )

#     print("Expected output set:", sorted(expected_outputs))
#     print("Most probable output:", expected_output)
#     print("Success probability:", success_probability)

#     # -----------------------------------------------------
#     # Step 8: Quality profiler
#     # -----------------------------------------------------

#     section("8. QUALITY PROFILER")

#     observable_values = {
#         output: (
#             1.0 if output in expected_outputs else -1.0
#         )
#         for output in measured
#     }

#     profiler = QualityProfiler()

#     quality = profiler.estimate_from_counts(
#         counts=result.counts,
#         observable_values=observable_values,
#         confidence_level=0.95,
#     )

#     print("Sample count       :", quality.sample_count)
#     print("Expectation value  :", quality.expectation_value)
#     print("Variance           :", quality.variance)
#     print("Standard error     :", quality.standard_error)
#     print("Confidence interval:", quality.confidence_interval)

#     # -----------------------------------------------------
#     # Step 9: Distribution comparison
#     # -----------------------------------------------------

#     section("9. REFERENCE VS MEASURED DISTRIBUTION")

#     tv_distance = calculate_tv_distance(
#         reference,
#         measured,
#     )

#     print("Total variation distance:", tv_distance)

#     for output in sorted(set(reference) | set(measured)):

#         ideal_probability = reference.get(output, 0.0)
#         measured_probability = measured.get(output, 0.0)

#         print(
#             f"{output}: "
#             f"Ideal={ideal_probability:.6f}, "
#             f"Measured={measured_probability:.6f}"
#         )

#     # -----------------------------------------------------
#     # Step 10: Application-quality decision
#     # -----------------------------------------------------

#     section("10. APPLICATION QUALITY DECISION")

#     success_pass = (
#         success_probability >= MIN_SUCCESS_PROBABILITY
#     )

#     distribution_pass = (
#         tv_distance <= MAX_TV_DISTANCE
#     )

#     quality_satisfied = (
#         success_pass and distribution_pass
#     )

#     print("Success threshold:", MIN_SUCCESS_PROBABILITY)
#     print("Actual success   :", success_probability)

#     print(
#         "Success check    :",
#         "PASS" if success_pass else "FAIL",
#     )

#     print("\nMaximum TV distance:", MAX_TV_DISTANCE)
#     print("Actual TV distance :", tv_distance)

#     print(
#         "Distribution check:",
#         "PASS" if distribution_pass else "FAIL",
#     )

#     print("\nAPPLICATION QUALITY:")

#     print(
#         "SATISFIED" if quality_satisfied
#         else "NOT SATISFIED"
#     )

#     # -----------------------------------------------------
#     # Step 11: Final summary
#     # -----------------------------------------------------

#     section("FINAL EXPERIMENT SUMMARY")

#     print("Circuit             :", circuit.name)
#     print("Execution adapter   :", adapter.__class__.__name__)
#     print("Execution mode      :", execution_mode.value)
#     print("Shots               :", result.shots)
#     print("Expected output     :", expected_output)
#     print("Success probability :", success_probability)
#     print("Expectation         :", quality.expectation_value)
#     print("Variance            :", quality.variance)
#     print("Standard error      :", quality.standard_error)
#     print("TV distance         :", tv_distance)
#     print("Application quality :", quality_satisfied)

#     return 0 if quality_satisfied else 1


# if __name__ == "__main__":
#     raise SystemExit(main())




# new Code  new run how to run this 



# py examples/test_one_circuit_application_quality.py --adapter aer_ideal
"""
QFlowPilot: Single-circuit application-quality and seven-profiler test.

One circuit is executed using selectable existing adapters.

Adapters:
    - AerIdealAdapter
    - AerNoisyAdapter
    - IBMAdapter
    - IonQ ideal simulator
    - IonQ Forte noisy simulator
    - IonQ Aria noisy simulator
    - IonQ Forte QPU
    - ClassicalAdapter

Seven profilers:
    1. CircuitProfiler
    2. WorkloadProfiler
    3. TranspilationProfiler
    4. QualityProfiler
    5. LatencyProfiler
    6. CostEstimator
    7. ResourceProfiler

Application-quality metrics:
    - Success probability
    - Observable expectation
    - Observable variance
    - Standard error (when sampled counts are available)
    - Total variation distance
    - Quality threshold decision

Run from project root:

    py examples/test_one_circuit_application_quality.py --adapter aer_ideal
    py examples/test_one_circuit_application_quality.py --adapter aer_noisy
    py examples/test_one_circuit_application_quality.py --adapter ionq_simulators
    py examples/test_one_circuit_application_quality.py --adapter ibm
    py examples/test_one_circuit_application_quality.py --adapter ionq_qpu
    py examples/test_one_circuit_application_quality.py --adapter classical
    py examples/test_one_circuit_application_quality.py --adapter all

Cloud configuration:
    QFLOWPILOT_IONQ_TOKEN
    QFLOWPILOT_IBM_BACKEND
    QFLOWPILOT_IBM_CHANNEL
    QFLOWPILOT_IBM_TOKEN
    QFLOWPILOT_IBM_INSTANCE

Explicit real-QPU opt-in:
    QFLOWPILOT_ENABLE_IBM_HARDWARE=1
    QFLOWPILOT_ENABLE_IONQ_QPU=1

No new adapter modules.
No QCloudSimpy or QSimKit.
"""

from __future__ import annotations

import argparse
import inspect
import os
import sys
import traceback

from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# =========================================================
# QISKIT
# =========================================================

from qiskit import qasm2, qasm3
from qiskit.quantum_info import Statevector


# =========================================================
# EXISTING QFLOWPILOT ADAPTERS
# =========================================================

from qflowpilot.adapters import (
    AerIdealAdapter,
    AerNoisyAdapter,
    IBMAdapter,
    ClassicalAdapter,
    IonQAdapter,
)


# =========================================================
# CORE MODELS
# =========================================================

from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    WorkloadSpec,
    WorkloadType,
)


# =========================================================
# SEVEN EXISTING PROFILERS
# =========================================================

from qflowpilot.profiler.circuit_profiler import CircuitProfiler
from qflowpilot.profiler.workload_profiler import WorkloadProfiler
from qflowpilot.profiler.transpilation_profiler import TranspilationProfiler
from qflowpilot.profiler.quality_profiler import QualityProfiler
from qflowpilot.profiler.latency_profiler import LatencyProfiler
from qflowpilot.profiler.cost_estimator import CostEstimator
from qflowpilot.profiler.resource_profiler import ResourceProfiler


# =========================================================
# 1. EXPERIMENT CONFIGURATION
# =========================================================

WORKLOAD_ID = "qflowpilot_single_circuit_quality"

DATASET = ROOT / "workloads" / "mqt_bench"

CIRCUIT_FILE = (
    DATASET / "dj_nativegates_ibm_falcon_opt2_5.qasm"
)

SHOTS = 1024
SEED = 42

OPT_LEVEL = 1

CONFIDENCE = 0.95
TARGET_PRECISION = 0.05

MIN_SUCCESS_PROBABILITY = 0.95
MAX_TV_DISTANCE = 0.05

REFERENCE_TOLERANCE = 1e-12


# =========================================================
# 2. DISPLAY HELPERS
# =========================================================

def section(title: str) -> None:

    print("\n" + "=" * 84)
    print(title)
    print("=" * 84)


def show(label: str, value: Any) -> None:

    print(f"{label:<36}: {value}")


def show_profile(profile: Any) -> None:
    """
    Display profiler output without printing circuit objects.
    """

    if hasattr(profile, "__dataclass_fields__"):

        names = profile.__dataclass_fields__.keys()

        for name in names:

            if name in {
                "circuit",
                "transpiled_circuit",
            }:
                continue

            try:
                show(name, getattr(profile, name))
            except Exception:
                pass

    elif hasattr(profile, "__dict__"):

        for name, value in vars(profile).items():

            if name.startswith("_"):
                continue

            if name in {
                "circuit",
                "transpiled_circuit",
            }:
                continue

            show(name, value)

    else:
        print(profile)


# =========================================================
# 3. LOAD ONE CIRCUIT
# =========================================================

def load_one_circuit(path: Path):

    if not path.exists():
        raise FileNotFoundError(path)

    content = path.read_text(
        encoding="utf-8-sig"
    )

    first_line = next(
        line.strip()
        for line in content.splitlines()
        if line.strip()
        and not line.strip().startswith("//")
    )

    if "3.0" in first_line:

        circuit = qasm3.loads(content)

    elif "2.0" in first_line:

        circuit = qasm2.loads(content)

    else:

        raise ValueError(
            f"Unknown OpenQASM version: {first_line}"
        )

    return circuit


# =========================================================
# 4. EXACT IDEAL REFERENCE DISTRIBUTION
# =========================================================

def build_reference_distribution(circuit):
    """
    Calculate the exact ideal output distribution using Statevector.

    Assumptions:
        - Final measurements only.
        - Every classical bit has a measurement mapping.
        - No mid-circuit measurement or dynamic control flow.
    """

    measurement_map = {}

    for instruction in circuit.data:

        if instruction.operation.name != "measure":
            continue

        qubit = circuit.find_bit(
            instruction.qubits[0]
        ).index

        classical_bit = circuit.find_bit(
            instruction.clbits[0]
        ).index

        measurement_map[classical_bit] = qubit

    if not measurement_map:

        raise ValueError(
            "Circuit has no measurement operations."
        )

    if len(measurement_map) != circuit.num_clbits:

        raise ValueError(
            "Every classical bit must have a measurement mapping."
        )

    unitary_circuit = circuit.remove_final_measurements(
        inplace=False
    )

    if any(
        instruction.operation.name == "measure"
        for instruction in unitary_circuit.data
    ):

        raise ValueError(
            "Circuit contains non-final measurements. "
            "This reference method supports final measurements only."
        )

    unitary_circuit.data = [
        instruction
        for instruction in unitary_circuit.data
        if instruction.operation.name != "barrier"
    ]

    statevector = Statevector.from_instruction(
        unitary_circuit
    )

    reference = {}

    for basis_index, amplitude in enumerate(statevector.data):

        probability = float(abs(amplitude) ** 2)

        if probability < REFERENCE_TOLERANCE:
            continue

        classical_bits = ["0"] * circuit.num_clbits

        for classical_bit, qubit in measurement_map.items():

            bit_value = (basis_index >> qubit) & 1

            classical_bits[
                circuit.num_clbits - 1 - classical_bit
            ] = str(bit_value)

        output = "".join(classical_bits)

        reference[output] = (
            reference.get(output, 0.0) + probability
        )

    total = sum(reference.values())

    if total <= 0:
        raise ValueError("Ideal reference distribution is empty.")

    return {
        output: probability / total
        for output, probability in reference.items()
    }


# =========================================================
# 5. PROBABILITY AND QUALITY CALCULATIONS
# =========================================================

def normalize_bitstring(bitstring: Any) -> str:

    return str(bitstring).replace(" ", "")


def counts_to_probabilities(counts):

    total_shots = sum(counts.values())

    if total_shots <= 0:

        raise ValueError(
            "No measurement shots available."
        )

    probabilities = {}

    for bitstring, count in counts.items():

        output = normalize_bitstring(bitstring)

        probabilities[output] = (
            probabilities.get(output, 0.0)
            + count / total_shots
        )

    return probabilities


def normalize_probability_distribution(probabilities):

    normalized = {}

    for bitstring, probability in probabilities.items():

        output = normalize_bitstring(bitstring)

        normalized[output] = (
            normalized.get(output, 0.0)
            + float(probability)
        )

    total = sum(normalized.values())

    if total <= 0:
        raise ValueError("Probability distribution is empty.")

    return {
        output: probability / total
        for output, probability in normalized.items()
    }


def calculate_success_probability(
    measured,
    expected_outputs,
):

    return sum(
        measured.get(output, 0.0)
        for output in expected_outputs
    )


def calculate_tv_distance(reference, measured):

    all_outputs = set(reference) | set(measured)

    return 0.5 * sum(
        abs(
            reference.get(output, 0.0)
            - measured.get(output, 0.0)
        )
        for output in all_outputs
    )


def calculate_binary_observable(
    measured,
    expected_outputs,
):
    """
    Observable:
        +1: output belongs to ideal reference support.
        -1: output is outside ideal reference support.
    """

    expectation = 0.0
    second_moment = 0.0

    for output, probability in measured.items():

        value = (
            1.0 if output in expected_outputs else -1.0
        )

        expectation += probability * value

        second_moment += probability * value**2

    variance = max(
        0.0,
        second_moment - expectation**2,
    )

    return expectation, variance


# =========================================================
# 6. WORKLOAD
# =========================================================

def make_workload() -> WorkloadSpec:

    return WorkloadSpec(
        workload_id=WORKLOAD_ID,
        name="QFlowPilot Single-Circuit Quality Experiment",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="Deutsch-Jozsa",
        application="Application-quality validation",
        description=(
            "Single MQT Bench circuit executed through "
            "selectable QFlowPilot adapters."
        ),
        metadata={
            "dataset": "MQT Bench",
            "circuit": CIRCUIT_FILE.name,
            "shots": SHOTS,
            "seed": SEED,
        },
    )


# =========================================================
# 7. ADAPTER CONFIGURATION
# =========================================================

def build_adapters(selection: str):

    adapters = []

    # -----------------------------------------------------
    # Aer ideal
    # -----------------------------------------------------

    if selection in ("all", "aer_ideal"):

        adapters.append((
            "Aer Ideal Simulator",
            AerIdealAdapter(
                optimization_level=OPT_LEVEL
            ),
            SHOTS,
        ))

    # -----------------------------------------------------
    # Aer noisy
    # -----------------------------------------------------

    if selection in ("all", "aer_noisy"):

        adapters.append((
            "Aer Noisy Simulator",
            AerNoisyAdapter(
                optimization_level=OPT_LEVEL,
                single_qubit_error=0.001,
                two_qubit_error=0.01,
                readout_error=0.02,
            ),
            SHOTS,
        ))

    # -----------------------------------------------------
    # IonQ simulators
    # -----------------------------------------------------

    if selection in (
        "all",
        "ionq_simulators",
        "ionq_ideal",
        "ionq_forte_noisy",
        "ionq_aria_noisy",
    ):

        token = os.getenv("QFLOWPILOT_IONQ_TOKEN")

        if not token:

            print(
                "[SKIP] IonQ simulators: "
                "QFLOWPILOT_IONQ_TOKEN is not set."
            )

        else:

            targets = {
                "ionq_simulators": [
                    "ideal_simulator",
                    "forte_noisy_simulator",
                    "aria_noisy_simulator",
                ],
                "ionq_ideal": [
                    "ideal_simulator",
                ],
                "ionq_forte_noisy": [
                    "forte_noisy_simulator",
                ],
                "ionq_aria_noisy": [
                    "aria_noisy_simulator",
                ],
                "all": [
                    "ideal_simulator",
                    "forte_noisy_simulator",
                    "aria_noisy_simulator",
                ],
            }

            for target in targets.get(selection, []):

                try:

                    adapter = IonQAdapter(
                        target=target,
                        token=token,
                    )

                    target_shots = (
                        1
                        if target == "ideal_simulator"
                        else SHOTS
                    )

                    adapters.append((
                        f"IonQ {target}",
                        adapter,
                        target_shots,
                    ))

                except Exception as exc:

                    print(
                        f"[SKIP] IonQ {target}: {exc}"
                    )

    # -----------------------------------------------------
    # IBM Quantum hardware
    # -----------------------------------------------------

    if selection in ("all", "ibm"):

        backend_name = os.getenv(
            "QFLOWPILOT_IBM_BACKEND"
        )

        enabled = (
            os.getenv("QFLOWPILOT_ENABLE_IBM_HARDWARE")
            == "1"
        )

        if backend_name and enabled:

            try:

                adapter = IBMAdapter(
                    backend_name=backend_name,
                    channel=os.getenv(
                        "QFLOWPILOT_IBM_CHANNEL"
                    ),
                    token=os.getenv(
                        "QFLOWPILOT_IBM_TOKEN"
                    ),
                    instance=os.getenv(
                        "QFLOWPILOT_IBM_INSTANCE"
                    ),
                    optimization_level=OPT_LEVEL,
                )

                adapters.append((
                    "IBM Quantum Hardware",
                    adapter,
                    SHOTS,
                ))

            except Exception as exc:

                print(f"[SKIP] IBM initialization: {exc}")

        else:

            print(
                "[SKIP] IBM hardware: configure "
                "QFLOWPILOT_IBM_BACKEND and set "
                "QFLOWPILOT_ENABLE_IBM_HARDWARE=1."
            )

    # -----------------------------------------------------
    # IonQ Forte QPU
    # -----------------------------------------------------

    if selection in ("all", "ionq_qpu"):

        token = os.getenv("QFLOWPILOT_IONQ_TOKEN")

        enabled = (
            os.getenv("QFLOWPILOT_ENABLE_IONQ_QPU")
            == "1"
        )

        if token and enabled:

            try:

                adapter = IonQAdapter(
                    target="forte_qpu",
                    token=token,
                )

                adapters.append((
                    "IonQ Forte QPU",
                    adapter,
                    SHOTS,
                ))

            except Exception as exc:

                print(f"[SKIP] IonQ QPU initialization: {exc}")

        else:

            print(
                "[SKIP] IonQ QPU: configure "
                "QFLOWPILOT_IONQ_TOKEN and "
                "QFLOWPILOT_ENABLE_IONQ_QPU=1."
            )

    # -----------------------------------------------------
    # Classical fallback
    # -----------------------------------------------------

    if selection in ("all", "classical"):

        adapters.append((
            "Classical Fallback",
            ClassicalAdapter(),
            SHOTS,
        ))

    return adapters


# =========================================================
# 8. EXECUTION MODE SELECTION
# =========================================================

def execution_mode_for(adapter: Any) -> ExecutionMode:

    if isinstance(adapter, AerIdealAdapter):

        return ExecutionMode.IDEAL_SIMULATOR

    if isinstance(adapter, AerNoisyAdapter):

        return ExecutionMode.NOISY_SIMULATOR

    if isinstance(adapter, IBMAdapter):

        return ExecutionMode.QUANTUM_HARDWARE

    if isinstance(adapter, IonQAdapter):

        return adapter.execution_mode

    if isinstance(adapter, ClassicalAdapter):

        return ExecutionMode.CLASSICAL

    raise TypeError(
        f"Unsupported adapter: {type(adapter).__name__}"
    )


# =========================================================
# 9. TRANSPILATION PROFILER INITIALIZATION
# =========================================================

def make_transpilation_profiler(
    adapter: Any,
) -> TranspilationProfiler:
    """
    Reuse the constructor supported by the installed profiler.
    """

    params = inspect.signature(
        TranspilationProfiler
    ).parameters

    target = getattr(
        adapter,
        "_simulator",
        None,
    )

    if target is None:

        target = getattr(
            adapter,
            "_backend",
            None,
        )

    kwargs = {}

    if "backend" in params and target is not None:

        kwargs["backend"] = target

    if "optimization_level" in params:

        kwargs["optimization_level"] = OPT_LEVEL

    return TranspilationProfiler(**kwargs)


# =========================================================
# 10. CLASSICAL ADAPTER EXECUTION
# =========================================================

def execute_classical_adapter(
    adapter,
    circuit,
    request,
    reference,
):

    expected_output = max(
        reference,
        key=reference.get,
    )

    def classical_callable(req):

        # This is a reference-output integration test.
        # It is not a separate implementation of Deutsch-Jozsa.

        return {
            "algorithm": "reference_output_integration_test",
            "circuit_name": circuit.name,
            "expected_output": expected_output,
            "reference_distribution": reference,
            "received_shots": req.shots,
        }

    return adapter.execute(
        request,
        classical_callable,
    )


# =========================================================
# 11. SINGLE ADAPTER EXPERIMENT
# =========================================================

def run_one_adapter(
    display_name: str,
    adapter: Any,
    shots: int,
    workload: WorkloadSpec,
    circuit,
    reference,
):

    section(f"ADAPTER: {display_name}")

    show("Adapter", type(adapter).__name__)
    show("Backend information", adapter.get_backend_info())

    status = {}

    if not adapter.is_available():

        print("[UNAVAILABLE] Adapter reports unavailable.")

        return {
            "Adapter": "UNAVAILABLE",
        }

    # -----------------------------------------------------
    # 1. CircuitProfiler
    # -----------------------------------------------------

    section(f"{display_name} | 1. CircuitProfiler")

    try:

        profiler = CircuitProfiler()

        circuit_profile = profiler.profile_circuit(
            circuit
        )

        show_profile(circuit_profile)

        status["CircuitProfiler"] = "PASS"

    except Exception:

        status["CircuitProfiler"] = "FAIL"

        traceback.print_exc()

    # -----------------------------------------------------
    # 2. WorkloadProfiler
    # -----------------------------------------------------

    section(f"{display_name} | 2. WorkloadProfiler")

    workload_profile = None

    try:

        profiler = WorkloadProfiler()

        rounds = [[circuit]]

        workload_profile = profiler.profile_iterative(
            workload,
            rounds,
        )

        show_profile(workload_profile)

        status["WorkloadProfiler"] = "PASS"

    except Exception:

        status["WorkloadProfiler"] = "FAIL"

        traceback.print_exc()

    # -----------------------------------------------------
    # 3. TranspilationProfiler
    # -----------------------------------------------------

    section(f"{display_name} | 3. TranspilationProfiler")

    if isinstance(adapter, ClassicalAdapter):

        print(
            "NOT APPLICABLE: ClassicalAdapter does not "
            "submit a quantum circuit to a quantum backend."
        )

        status["TranspilationProfiler"] = "NOT APPLICABLE"

    else:

        try:

            profiler = make_transpilation_profiler(
                adapter
            )

            profiles = profiler.profile_multiple(
                [circuit]
            )

            if not isinstance(profiles, (list, tuple)):

                profiles = [profiles]

            for profile in profiles:

                show_profile(profile)

            status["TranspilationProfiler"] = (
                "PASS" if profiles else "PARTIAL"
            )

        except Exception:

            status["TranspilationProfiler"] = "FAIL"

            traceback.print_exc()

    # -----------------------------------------------------
    # 4. Adapter execution
    # -----------------------------------------------------

    section(f"{display_name} | Adapter Execution")

    mode = execution_mode_for(adapter)

    request = ExecutionRequest(
        request_id=(
            f"{WORKLOAD_ID}_{adapter.backend_name}"
        ),
        workload_id=WORKLOAD_ID,
        shots=shots,
        execution_mode=mode,
        backend_name=adapter.backend_name,
        seed=SEED,
        metadata={
            "circuit_name": circuit.name,
            "dataset_source": CIRCUIT_FILE.name,
            "adapter": type(adapter).__name__,
        },
    )

    try:

        if isinstance(adapter, ClassicalAdapter):

            result = execute_classical_adapter(
                adapter,
                circuit,
                request,
                reference,
            )

        else:

            result = adapter.execute(
                request,
                circuit,
            )

        status["AdapterExecution"] = "PASS"

        show("Execution status", result.status)
        show("Backend", result.backend_name)
        show("Execution mode", result.execution_mode)
        show("Shots", result.shots)
        show("Execution time (s)", result.execution_time_s)
        show("Counts", result.counts)
        show("Metadata", result.metadata)

    except Exception:

        status["AdapterExecution"] = "FAIL"

        traceback.print_exc()

        return status

    # -----------------------------------------------------
    # 5. Application-quality metrics
    # -----------------------------------------------------

    section(f"{display_name} | Application Quality")

    expected_outputs = set(reference.keys())

    expected_output = max(
        reference,
        key=reference.get,
    )

    measured = None

    # Classical output is not a quantum measurement distribution.
    if isinstance(adapter, ClassicalAdapter):

        print(
            "QualityProfiler: NOT APPLICABLE."
        )

        print(
            "ClassicalAdapter returns an application-level "
            "output, not quantum measurement counts."
        )

        show(
            "Classical output",
            result.metadata.get("classical_output"),
        )

        status["QualityProfiler"] = "NOT APPLICABLE"

    else:

        # -------------------------------------------------
        # Sampled measurement counts
        # -------------------------------------------------

        if result.counts:

            measured = counts_to_probabilities(
                result.counts
            )

            observable_values = {}

            for state in result.counts:

                compact = normalize_bitstring(state)

                observable_values[state] = (
                    1.0
                    if compact in expected_outputs
                    else -1.0
                )

            try:

                profiler = QualityProfiler()

                quality = profiler.estimate_from_counts(
                    counts=result.counts,
                    observable_values=observable_values,
                    confidence_level=CONFIDENCE,
                )

                show("Sample count", quality.sample_count)
                show(
                    "Expectation",
                    quality.expectation_value,
                )
                show("Variance", quality.variance)
                show(
                    "Standard error",
                    quality.standard_error,
                )
                show(
                    "Confidence interval",
                    quality.confidence_interval,
                )

                status["QualityProfiler"] = "PASS"

            except Exception:

                status["QualityProfiler"] = "FAIL"

                traceback.print_exc()

        # -------------------------------------------------
        # IonQ ideal simulator probabilities
        # -------------------------------------------------

        elif result.metadata.get("probabilities") is not None:

            measured = normalize_probability_distribution(
                result.metadata["probabilities"]
            )

            expectation, variance = calculate_binary_observable(
                measured,
                expected_outputs,
            )

            print(
                "IonQ ideal simulator returned exact "
                "probabilities instead of sampled counts."
            )

            show("Exact expectation", expectation)
            show("Exact variance", variance)
            show("Standard error", "NOT APPLICABLE")
            show("Confidence interval", "NOT APPLICABLE")

            status["QualityProfiler"] = (
                "PARTIAL - ANALYTIC PROBABILITIES"
            )

        else:

            status["QualityProfiler"] = "NOT APPLICABLE"

            print(
                "No measurement counts or probability "
                "distribution were returned."
            )

    # -----------------------------------------------------
    # 6. Application success and TV distance
    # -----------------------------------------------------

    if measured is not None:

        section(f"{display_name} | Reference Comparison")

        success_probability = calculate_success_probability(
            measured,
            expected_outputs,
        )

        tv_distance = calculate_tv_distance(
            reference,
            measured,
        )

        expectation, variance = calculate_binary_observable(
            measured,
            expected_outputs,
        )

        success_pass = (
            success_probability >= MIN_SUCCESS_PROBABILITY
        )

        distribution_pass = (
            tv_distance <= MAX_TV_DISTANCE
        )

        quality_satisfied = (
            success_pass and distribution_pass
        )

        show("Ideal expected outputs", sorted(expected_outputs))
        show("Most probable expected output", expected_output)
        show("Success probability", success_probability)
        show("Expectation", expectation)
        show("Variance", variance)
        show("TV distance", tv_distance)

        show(
            "Success threshold",
            MIN_SUCCESS_PROBABILITY,
        )

        show(
            "Success check",
            "PASS" if success_pass else "FAIL",
        )

        show(
            "Maximum TV distance",
            MAX_TV_DISTANCE,
        )

        show(
            "Distribution check",
            "PASS" if distribution_pass else "FAIL",
        )

        show(
            "APPLICATION QUALITY",
            "SATISFIED" if quality_satisfied
            else "NOT SATISFIED",
        )

        print("\nMeasured distribution:")

        for output, probability in sorted(measured.items()):

            print(
                f"{output}: {probability:.8f}"
            )

        status["ApplicationQuality"] = (
            "PASS" if quality_satisfied else "FAIL"
        )

    else:

        success_probability = None
        tv_distance = None
        quality_satisfied = None

        status["ApplicationQuality"] = "NOT APPLICABLE"

    # -----------------------------------------------------
    # 7. LatencyProfiler
    # -----------------------------------------------------

    section(f"{display_name} | 5. LatencyProfiler")

    try:

        profiler = LatencyProfiler()

        latency_profile = profiler.profile_execution(
            result
        )

        show_profile(latency_profile)

        status["LatencyProfiler"] = "PASS"

    except Exception:

        status["LatencyProfiler"] = "FAIL"

        traceback.print_exc()

    # -----------------------------------------------------
    # 8. CostEstimator
    # -----------------------------------------------------

    section(f"{display_name} | 6. CostEstimator")

    try:

        estimator = CostEstimator()

        cost_profile = estimator.estimate_from_execution(
            qpu_execution_time_s=(
                result.execution_time_s or 0.0
            ),
            shots=result.shots or 0,
            metadata={
                "request_id": result.request_id,
                "result_id": result.result_id,
                "backend_name": result.backend_name,
                "execution_mode": str(result.execution_mode),
            },
        )

        show_profile(cost_profile)

        status["CostEstimator"] = (
            "PASS - CHECK RATE CONFIGURATION"
        )

    except Exception:

        status["CostEstimator"] = "FAIL"

        traceback.print_exc()

    # -----------------------------------------------------
    # 9. ResourceProfiler
    # -----------------------------------------------------

    section(f"{display_name} | 7. ResourceProfiler")

    try:

        if workload_profile is None:

            raise RuntimeError(
                "WorkloadProfiler did not produce a profile."
            )

        profiler = ResourceProfiler()

        resource_profile = profiler.profile_workload(
            workload_profile,
            shots_per_circuit=shots,
            variance=1.0,
            target_precision=TARGET_PRECISION,
            confidence_level=CONFIDENCE,
        )

        show_profile(resource_profile)

        status["ResourceProfiler"] = "PASS"

    except Exception:

        status["ResourceProfiler"] = "FAIL"

        traceback.print_exc()

    # -----------------------------------------------------
    # Final adapter summary
    # -----------------------------------------------------

    section(f"{display_name} | FINAL RESULT")

    show("Adapter", type(adapter).__name__)
    show("Execution mode", mode.value)
    show("Shots", result.shots)
    show("Success probability", success_probability)
    show("TV distance", tv_distance)
    show("Application quality", quality_satisfied)

    return status


# =========================================================
# 12. MAIN
# =========================================================

def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "QFlowPilot single-circuit quality and "
            "seven-profiler adapter test."
        )
    )

    parser.add_argument(
        "--adapter",
        choices=[
            "all",
            "aer_ideal",
            "aer_noisy",
            "ionq_simulators",
            "ionq_ideal",
            "ionq_forte_noisy",
            "ionq_aria_noisy",
            "ibm",
            "ionq_qpu",
            "classical",
        ],
        default="aer_noisy",
    )

    args = parser.parse_args()

    section(
        "QFLOWPILOT SINGLE-CIRCUIT APPLICATION-QUALITY TEST"
    )

    show("Project root", ROOT)
    show("Circuit file", CIRCUIT_FILE)
    show("Adapter selection", args.adapter)
    show("Shots", SHOTS)
    show("Seed", SEED)

    # -----------------------------------------------------
    # Load circuit
    # -----------------------------------------------------

    section("1. CIRCUIT LOADING")

    circuit = load_one_circuit(
        CIRCUIT_FILE
    )

    show("Circuit name", circuit.name)
    show("Qubits", circuit.num_qubits)
    show("Classical bits", circuit.num_clbits)
    show("Circuit depth", circuit.depth())
    show("Gate count", circuit.size())

    # -----------------------------------------------------
    # Exact ideal reference
    # -----------------------------------------------------

    section("2. EXACT IDEAL REFERENCE")

    reference = build_reference_distribution(
        circuit
    )

    for output, probability in sorted(reference.items()):

        print(
            f"{output}: {probability:.8f}"
        )

    expected_output = max(
        reference,
        key=reference.get,
    )

    show("Expected output", expected_output)
    show("Ideal output states", len(reference))

    # -----------------------------------------------------
    # Workload
    # -----------------------------------------------------

    workload = make_workload()

    section("3. WORKLOAD")

    show("Workload ID", workload.workload_id)
    show("Workload type", workload.workload_type)
    show("Algorithm", workload.algorithm)

    # -----------------------------------------------------
    # Build selected adapters
    # -----------------------------------------------------

    section("4. ADAPTER CONFIGURATION")

    adapters = build_adapters(
        args.adapter
    )

    if not adapters:

        print(
            "No adapters configured. "
            "Check cloud credentials and adapter selection."
        )

        return 2

    show("Configured adapters", len(adapters))

    summary = {}

    # -----------------------------------------------------
    # Run each adapter
    # -----------------------------------------------------

    for display_name, adapter, shots in adapters:

        try:

            summary[display_name] = run_one_adapter(
                display_name=display_name,
                adapter=adapter,
                shots=shots,
                workload=workload,
                circuit=circuit,
                reference=reference,
            )

        except Exception as exc:

            print(
                f"\n[ADAPTER FAILED] {display_name}: {exc}"
            )

            traceback.print_exc()

            summary[display_name] = {
                "AdapterPipeline": "FAIL",
            }

    # -----------------------------------------------------
    # Final comparison
    # -----------------------------------------------------

    section("FINAL MULTI-ADAPTER SUMMARY")

    for adapter_name, stages in summary.items():

        print(f"\n{adapter_name}")

        for stage, result in stages.items():

            show(stage, result)

    failures = [
        (adapter, stage)
        for adapter, stages in summary.items()
        for stage, result in stages.items()
        if result == "FAIL"
    ]

    partials = [
        (adapter, stage)
        for adapter, stages in summary.items()
        for stage, result in stages.items()
        if (
            "PARTIAL" in result
            or "NOT APPLICABLE" in result
            or "UNAVAILABLE" in result
        )
    ]

    section("EXPERIMENT SUMMARY")

    show("Adapters tested", len(summary))
    show("Failed stages", len(failures))
    show("Partial / not applicable", len(partials))

    print(
        "\nInterpretation:"
    )

    print(
        "- QualityProfiler PASS means sampled-count quality "
        "statistics were calculated."
    )

    print(
        "- IonQ ideal uses analytic probabilities; its standard "
        "error and confidence interval are not sampled estimates."
    )

    print(
        "- ClassicalAdapter does not produce quantum measurement "
        "counts, so quantum quality metrics are not applicable."
    )

    print(
        "- CostEstimator PASS means the estimator executed. "
        "A monetary cost may remain unavailable without configured rates."
    )

    print(
        "- IBM and IonQ QPU runs require explicit opt-in and may incur cost."
    )

    print(
        "\nThe exact Statevector distribution is a mathematical "
        "reference for this circuit. It does not independently verify "
        "that the circuit implements the intended Deutsch-Jozsa problem."
    )

    return 1 if failures else 0


if __name__ == "__main__":

    raise SystemExit(main())
