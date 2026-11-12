"""
Single-adapter QFlowPilot dataset integration test.

Uses the existing AerIdealAdapter and the seven existing profiler modules.
It loads a small number of QASM/QPY circuits from the QFlowPilot dataset.

Run from the QFlowPilot project root:
    py examples/test_dataset_aer_ideal.py

Optional:
    py examples/test_dataset_aer_ideal.py --dataset-dir dataset --max-circuits 5 --shots 1024

This script does not create or duplicate adapters.
It does not use QCloudSimpy or QSimKit.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qiskit import QuantumCircuit, qasm2, qasm3
from qiskit import qpy

from qflowpilot.core.models import (
    ExecutionMode,
    ExecutionRequest,
    WorkloadSpec,
    WorkloadType,
)
from qflowpilot.adapters import AerIdealAdapter
from qflowpilot.profiler.circuit_profiler import CircuitProfiler
from qflowpilot.profiler.workload_profiler import WorkloadProfiler
from qflowpilot.profiler.transpilation_profiler import TranspilationProfiler
from qflowpilot.profiler.quality_profiler import QualityProfiler
from qflowpilot.profiler.latency_profiler import LatencyProfiler
from qflowpilot.profiler.cost_estimator import CostEstimator
from qflowpilot.profiler.resource_profiler import ResourceProfiler


SUPPORTED_SUFFIXES = {".qasm", ".qasm2", ".qasm3", ".qpy"}


def section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def load_qasm_file(path: Path) -> QuantumCircuit:
    """
    Load OpenQASM 2.0 or 3.0 by detecting the version
    from the file contents rather than its extension.
    """

    content = path.read_text(encoding="utf-8-sig")

    # Detect the declared OpenQASM version.
    first_line = next(
        (
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("//")
        ),
        "",
    )

    if "3.0" in first_line:
        return qasm3.loads(content)

    if "2.0" in first_line:
        return qasm2.loads(content)

    raise ValueError(
        f"Unsupported or unrecognized OpenQASM version: {first_line}"
    )


def load_circuits(
    dataset_dir: Path,
    max_circuits: int
) -> list[tuple[str, QuantumCircuit]]:
    """Load circuits from QASM 2, QASM 3, and QPY files."""

    if not dataset_dir.exists():
        raise FileNotFoundError(
            f"Dataset directory does not exist: {dataset_dir}"
        )

    files = sorted(
        path for path in dataset_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
    )

    if not files:
        raise RuntimeError(
            f"No supported circuit files found under {dataset_dir}"
        )

    loaded = []
    errors = []

    for path in files:
        if len(loaded) >= max_circuits:
            break

        try:
            suffix = path.suffix.lower()

            if suffix in {".qasm", ".qasm2", ".qasm3"}:
                circuits = [load_qasm_file(path)]

            elif suffix == ".qpy":
                with path.open("rb") as file_obj:
                    circuits = qpy.load(file_obj)

            else:
                continue

            for index, circuit in enumerate(circuits):

                if len(loaded) >= max_circuits:
                    break

                if not isinstance(circuit, QuantumCircuit):
                    continue

                if not circuit.name or circuit.name == "circuit":
                    circuit.name = path.stem

                label = path.relative_to(dataset_dir).as_posix()

                if suffix == ".qpy" and len(circuits) > 1:
                    label = f"{label} [circuit {index}]"

                loaded.append((label, circuit))

        except Exception as exc:
            errors.append(
                f"{path}: {type(exc).__name__}: {exc}"
            )

    print(f"Dataset directory : {dataset_dir.resolve()}")
    print(f"Supported files   : {len(files)}")
    print(f"Circuits loaded   : {len(loaded)}")

    if errors:
        print(f"Files skipped     : {len(errors)}")
        for message in errors[:10]:
            print(f"  [LOAD WARNING] {message}")

    if not loaded:
        raise RuntimeError(
            "Circuit files were found, but none could be loaded."
        )

    return loaded



def print_profile(profile: Any, excluded: set[str] | None = None) -> None:
    excluded = excluded or set()
    if hasattr(profile, "__dataclass_fields__"):
        for name in profile.__dataclass_fields__:
            if name in excluded:
                continue
            print(f"{name:<34}: {getattr(profile, name)}")
    elif hasattr(profile, "__dict__"):
        for name, value in vars(profile).items():
            if name.startswith("_") or name in excluded:
                continue
            print(f"{name:<34}: {value}")
    else:
        print(profile)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test QFlowPilot's seven profilers with AerIdealAdapter."
    )
    parser.add_argument(
        "--dataset-dir",
        default="./workloads/mqt_bench/",
        help="Dataset directory relative to the project root (default: dataset).",
    )
    parser.add_argument(
        "--max-circuits",
        type=int,
        default=3,
        help="Maximum number of circuits to load and execute (default: 3).",
    )
    parser.add_argument(
        "--shots",
        type=int,
        default=1024,
        help="Shots per circuit (default: 1024).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed (default: 42).",
    )
    parser.add_argument(
        "--optimization-level",
        type=int,
        choices=(0, 1, 2, 3),
        default=1,
        help="Qiskit transpiler optimization level (default: 1).",
    )
    args = parser.parse_args()

    if args.max_circuits < 1 or args.shots < 1:
        parser.error("--max-circuits and --shots must be positive integers.")

    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = ROOT / dataset_dir

    section("QFLOWPILOT DATASET TEST — ONE ADAPTER")
    print("Adapter           : AerIdealAdapter")
    print("Execution mode    : IDEAL_SIMULATOR")
    print("Profiler modules  : Seven")
    print("Project root      :", ROOT)

    # Load real circuit files from the user's dataset.
    loaded = load_circuits(dataset_dir, args.max_circuits)
    circuits = [circuit for _, circuit in loaded]

    workload = WorkloadSpec(
        workload_id="qflowpilot_dataset_aer_ideal_test",
        name="QFlowPilot Dataset Aer Ideal Test",
        workload_type=WorkloadType.BATCH,
        algorithm="Dataset circuits",
        application="Seven-profiler integration test",
        description="A small batch of circuits loaded from the local dataset.",
        metadata={"dataset_dir": str(dataset_dir), "shots": args.shots},
    )

    adapter = AerIdealAdapter(optimization_level=args.optimization_level)
    print("Backend information:", adapter.get_backend_info())
    if not adapter.is_available():
        print("[STOP] AerIdealAdapter is not available.")
        return 2

    status: dict[str, str] = {}
    circuit_profiles = []
    workload_profile = None
    results = []

    # 1. CircuitProfiler
    section("1. CircuitProfiler")
    cp = CircuitProfiler()
    for (source, circuit) in loaded:
        print(f"\nCircuit source: {source}")
        profile = cp.profile_circuit(circuit)
        circuit_profiles.append(profile)
        print(f"Circuit name       : {circuit.name}")
        print(f"Qubits             : {profile.num_qubits}")
        print(f"Depth              : {profile.depth}")
        print(f"Total gates        : {profile.total_gates}")
        print(f"Two-qubit gates    : {profile.two_qubit_gates}")
        print(f"Gate counts        : {profile.gate_counts}")
    status["CircuitProfiler"] = "PASS"

    # 2. WorkloadProfiler
    section("2. WorkloadProfiler")
    wp = WorkloadProfiler()
    workload_profile = wp.profile_batch(workload, circuits)
    print_profile(workload_profile)
    status["WorkloadProfiler"] = "PASS"

    # 3. TranspilationProfiler
    section("3. TranspilationProfiler")
    try:
        tp = TranspilationProfiler(
            backend=getattr(adapter, "_simulator", None),
            optimization_level=args.optimization_level,
        )
        transpilation_profiles = tp.profile_multiple(circuits)
        for index, profile in enumerate(transpilation_profiles, start=1):
            print(f"\nTranspilation profile {index}")
            print_profile(profile, {"transpiled_circuit"})
        status["TranspilationProfiler"] = "PASS"
    except Exception as exc:
        print(f"[ERROR] TranspilationProfiler: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        status["TranspilationProfiler"] = "FAIL"

    # Execute each loaded circuit using this one adapter only.
    section("ADAPTER EXECUTION — AerIdealAdapter")
    for index, circuit in enumerate(circuits, start=1):
        request = ExecutionRequest(
            request_id=f"dataset_aer_ideal_{index}",
            workload_id=workload.workload_id,
            shots=args.shots,
            execution_mode=ExecutionMode.IDEAL_SIMULATOR,
            backend_name=adapter.backend_name,
            seed=args.seed + index,
            metadata={
                "circuit_name": circuit.name,
                "dataset_source": loaded[index - 1][0],
            },
        )
        print(f"\nExecuting {index}/{len(circuits)}: {circuit.name}")
        result = adapter.execute(request, circuit)
        results.append(result)
        print("Status             :", result.status)
        print("Backend            :", result.backend_name)
        print("Shots              :", result.shots)
        print("Execution time (s) :", result.execution_time_s)
        print("Counts             :", result.counts)
    status["AerIdealAdapter execution"] = (
        "PASS" if len(results) == len(circuits) else "FAIL"
    )

    # 4. QualityProfiler
    section("4. QualityProfiler")
    qp = QualityProfiler()
    quality_count = 0
    for index, result in enumerate(results, start=1):
        if not result.counts:
            print(f"Circuit {index}: no counts; quality analysis skipped.")
            continue

        # A parity observable is used only as a generic demonstration.
        # Replace it with an application-specific observable for research.
        observable_values = {}
        for bitstring in result.counts:
            compact = str(bitstring).replace(" ", "")
            observable_values[bitstring] = (
                1.0 if compact.count("1") % 2 == 0 else -1.0
            )

        estimate = qp.estimate_from_counts(
            counts=result.counts,
            observable_values=observable_values,
            confidence_level=0.95,
        )
        quality_count += 1
        print(f"\nQuality profile {index}")
        print_profile(estimate)

    status["QualityProfiler"] = (
        "PASS" if quality_count == len(results) else "PARTIAL"
    )

    # 5. LatencyProfiler
    section("5. LatencyProfiler")
    lp = LatencyProfiler()
    for index, result in enumerate(results, start=1):
        print(f"\nLatency profile {index}")
        print_profile(lp.profile_execution(result))
    status["LatencyProfiler"] = "PASS"

    # 6. CostEstimator
    section("6. CostEstimator")
    estimator = CostEstimator()  # No provider prices are assumed.
    for index, result in enumerate(results, start=1):
        estimate = estimator.estimate_from_execution(
            qpu_execution_time_s=result.execution_time_s or 0.0,
            shots=result.shots if result.shots is not None else args.shots,
            metadata={
                "request_id": result.request_id,
                "backend_name": result.backend_name,
                "execution_mode": str(result.execution_mode),
            },
        )
        print(f"\nCost estimate {index}")
        print("QPU measured time  :", estimate.qpu.quantities)
        print("QPU monetary cost :", estimate.qpu.monetary_cost)
        print("Total monetary cost:", estimate.total_cost)
        print("Estimate complete :", estimate.is_complete)
        print("Missing components:", estimate.metadata.get("missing_components"))
    status["CostEstimator"] = "PASS"

    # 7. ResourceProfiler
    section("7. ResourceProfiler")
    rp = ResourceProfiler()
    resource_profile = rp.profile_workload(
        workload_profile,
        shots_per_circuit=args.shots,
        variance=1.0,
        target_precision=0.05,
        confidence_level=0.95,
    )
    print_profile(resource_profile)
    status["ResourceProfiler"] = "PASS"

    # Summary
    section("FINAL SUMMARY")
    for module, result in status.items():
        print(f"{module:<36}: {result}")

    passed = sum(value == "PASS" for value in status.values())
    failed = sum(value == "FAIL" for value in status.values())
    partial = sum(value == "PARTIAL" for value in status.values())
    print(f"\nPassed: {passed} | Failed: {failed} | Partial: {partial}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
