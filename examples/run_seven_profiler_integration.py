"""
QFlowPilot seven-profiler / multi-adapter integration test.

Run from project root:
    py examples/run_seven_profiler_integration.py --adapter all

Adapter options:
    all, aer_ideal, aer_noisy, ionq_simulators, ibm, ionq_qpu

Cloud configuration:
    QFLOWPILOT_IONQ_TOKEN
    QFLOWPILOT_IBM_BACKEND
    QFLOWPILOT_IBM_CHANNEL       (optional)
    QFLOWPILOT_IBM_TOKEN         (optional)
    QFLOWPILOT_IBM_INSTANCE      (optional)

Explicit real-QPU opt-in:
    QFLOWPILOT_ENABLE_IBM_HARDWARE=1
    QFLOWPILOT_ENABLE_IONQ_QPU=1

This script reuses qflowpilot.adapters. It creates no adapter modules.
It does not use QCloudSimpy or QSimKit.
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

from qiskit import QuantumCircuit

from qflowpilot.core.models import (
    WorkloadSpec, WorkloadType, ExecutionRequest, ExecutionMode
)
from qflowpilot.adapters import (
    AerIdealAdapter, AerNoisyAdapter, IBMAdapter,
    ClassicalAdapter, IonQAdapter,
)
from qflowpilot.profiler.circuit_profiler import CircuitProfiler
from qflowpilot.profiler.workload_profiler import WorkloadProfiler
from qflowpilot.profiler.transpilation_profiler import TranspilationProfiler
from qflowpilot.profiler.quality_profiler import QualityProfiler
from qflowpilot.profiler.latency_profiler import LatencyProfiler
from qflowpilot.profiler.cost_estimator import CostEstimator
from qflowpilot.profiler.resource_profiler import ResourceProfiler

WORKLOAD_ID = "qflowpilot_multi_adapter_profiler_test"
SHOTS = 1024
SEED = 42
OPT_LEVEL = 1
CONFIDENCE = 0.95
TARGET_PRECISION = 0.05


def section(title: str) -> None:
    print("\n" + "=" * 84)
    print(title)
    print("=" * 84)


def show(label: str, value: Any) -> None:
    print(f"{label:<36}: {value}")


def show_profile(profile: Any) -> None:
    if hasattr(profile, "__dataclass_fields__"):
        names = profile.__dataclass_fields__.keys()
        for name in names:
            if name in {"circuit", "transpiled_circuit"}:
                continue
            try:
                show(name, getattr(profile, name))
            except Exception:
                pass
    elif hasattr(profile, "__dict__"):
        for name, value in vars(profile).items():
            if not name.startswith("_") and name not in {
                "circuit", "transpiled_circuit"
            }:
                show(name, value)
    else:
        print(profile)


def make_circuits() -> list[QuantumCircuit]:
    bell = QuantumCircuit(2, 2, name="bell_state")
    bell.h(0)
    bell.cx(0, 1)
    bell.measure([0, 1], [0, 1])

    modified_bell = QuantumCircuit(2, 2, name="modified_bell")
    modified_bell.x(0)
    modified_bell.h(0)
    modified_bell.cx(0, 1)
    modified_bell.measure([0, 1], [0, 1])

    ghz = QuantumCircuit(3, 3, name="ghz_state")
    ghz.h(0)
    ghz.cx(0, 1)
    ghz.cx(1, 2)
    ghz.measure([0, 1, 2], [0, 1, 2])

    return [bell, modified_bell, ghz]


def make_workload() -> WorkloadSpec:
    return WorkloadSpec(
        workload_id=WORKLOAD_ID,
        name="QFlowPilot Multi-Adapter Profiler Test",
        workload_type=WorkloadType.ITERATIVE,
        algorithm="Bell and GHZ demonstration circuits",
        application="Profiler and adapter integration testing",
        description="Three circuits arranged as three sequential rounds.",
        metadata={"shots": SHOTS, "seed": SEED},
    )


def build_adapters(selection: str) -> list[tuple[str, Any, int]]:
    adapters: list[tuple[str, Any, int]] = []

    if selection in ("all", "aer_ideal"):
        adapters.append((
            "Aer Ideal Simulator",
            AerIdealAdapter(optimization_level=OPT_LEVEL),
            SHOTS,
        ))

    if selection in ("all", "aer_noisy"):
        adapters.append((
            "Aer Noisy Simulator",
            AerNoisyAdapter(optimization_level=OPT_LEVEL),
            SHOTS,
        ))

    if selection in ("all", "ionq_simulators"):
        token = os.getenv("QFLOWPILOT_IONQ_TOKEN")
        if token:
            for target in (
                "ideal_simulator",
                "forte_noisy_simulator",
                "aria_noisy_simulator",
            ):
                try:
                    adapter = IonQAdapter(target=target, token=token)
                    shots = 1 if target == "ideal_simulator" else SHOTS
                    adapters.append((f"IonQ {target}", adapter, shots))
                except Exception as exc:
                    print(f"[SKIP] IonQ {target}: {exc}")
        else:
            print("[SKIP] IonQ simulators: QFLOWPILOT_IONQ_TOKEN is not set.")

    if selection in ("all", "ibm"):
        backend_name = os.getenv("QFLOWPILOT_IBM_BACKEND")
        enabled = os.getenv("QFLOWPILOT_ENABLE_IBM_HARDWARE") == "1"
        if backend_name and enabled:
            adapters.append((
                "IBM Quantum Hardware",
                IBMAdapter(
                    backend_name=backend_name,
                    channel=os.getenv("QFLOWPILOT_IBM_CHANNEL"),
                    token=os.getenv("QFLOWPILOT_IBM_TOKEN"),
                    instance=os.getenv("QFLOWPILOT_IBM_INSTANCE"),
                    optimization_level=OPT_LEVEL,
                ),
                SHOTS,
            ))
        else:
            print(
                "[SKIP] IBM hardware: set QFLOWPILOT_IBM_BACKEND and "
                "QFLOWPILOT_ENABLE_IBM_HARDWARE=1."
            )

    if selection in ("all", "ionq_qpu"):
        token = os.getenv("QFLOWPILOT_IONQ_TOKEN")
        enabled = os.getenv("QFLOWPILOT_ENABLE_IONQ_QPU") == "1"
        if token and enabled:
            adapters.append((
                "IonQ Forte QPU",
                IonQAdapter(target="forte_qpu", token=token),
                SHOTS,
            ))
        else:
            print(
                "[SKIP] IonQ QPU: set QFLOWPILOT_IONQ_TOKEN and "
                "QFLOWPILOT_ENABLE_IONQ_QPU=1."
            )

    return adapters


def make_transpilation_profiler(adapter: Any) -> TranspilationProfiler:
    # Match the constructor actually exposed by the installed profiler.
    params = inspect.signature(TranspilationProfiler).parameters
    target = getattr(adapter, "_simulator", None)
    if target is None:
        target = getattr(adapter, "_backend", None)

    kwargs = {}
    if "backend" in params and target is not None:
        kwargs["backend"] = target
    if "optimization_level" in params:
        kwargs["optimization_level"] = OPT_LEVEL
    return TranspilationProfiler(**kwargs)


def execution_mode_for(adapter: Any) -> ExecutionMode:
    if isinstance(adapter, AerIdealAdapter):
        return ExecutionMode.IDEAL_SIMULATOR
    if isinstance(adapter, AerNoisyAdapter):
        return ExecutionMode.NOISY_SIMULATOR
    if isinstance(adapter, IBMAdapter):
        return ExecutionMode.QUANTUM_HARDWARE
    if isinstance(adapter, IonQAdapter):
        return adapter.execution_mode
    raise TypeError(f"Unsupported adapter: {type(adapter).__name__}")


def run_one_quantum_adapter(
    display_name: str,
    adapter: Any,
    shots: int,
    workload: WorkloadSpec,
    circuits: list[QuantumCircuit],
) -> dict[str, str]:
    section(f"ADAPTER: {display_name}")
    show("Adapter", type(adapter).__name__)
    show("Backend information", adapter.get_backend_info())

    if not adapter.is_available():
        print("[UNAVAILABLE] Adapter reports unavailable.")
        return {"Adapter": "UNAVAILABLE"}

    status: dict[str, str] = {}

    # 1. CircuitProfiler
    section(f"{display_name} | 1. CircuitProfiler")
    try:
        cp = CircuitProfiler()
        circuit_profiles = []
        for i, circuit in enumerate(circuits, 1):
            profile = cp.profile_circuit(circuit)
            circuit_profiles.append(profile)
            print(f"\nCircuit {i}: {circuit.name}")
            show_profile(profile)
        status["CircuitProfiler"] = "PASS"
    except Exception:
        status["CircuitProfiler"] = "FAIL"
        traceback.print_exc()

    # 2. WorkloadProfiler
    section(f"{display_name} | 2. WorkloadProfiler")
    workload_profile = None
    try:
        wp = WorkloadProfiler()
        rounds = [[circuit] for circuit in circuits]
        workload_profile = wp.profile_iterative(workload, rounds)
        show_profile(workload_profile)
        status["WorkloadProfiler"] = "PASS"
    except Exception:
        status["WorkloadProfiler"] = "FAIL"
        traceback.print_exc()

    # 3. TranspilationProfiler
    section(f"{display_name} | 3. TranspilationProfiler")
    try:
        tp = make_transpilation_profiler(adapter)
        transpilation_profiles = tp.profile_multiple(circuits)
        if not isinstance(transpilation_profiles, (list, tuple)):
            transpilation_profiles = [transpilation_profiles]
        for i, profile in enumerate(transpilation_profiles, 1):
            print(f"\nTranspilation profile {i}")
            show_profile(profile)
        status["TranspilationProfiler"] = (
            "PASS" if transpilation_profiles else "PARTIAL"
        )
    except Exception:
        status["TranspilationProfiler"] = "FAIL"
        traceback.print_exc()

    # Execute using the selected existing adapter.
    section(f"{display_name} | Adapter Execution")
    results = []
    mode = execution_mode_for(adapter)

    for i, circuit in enumerate(circuits, 1):
        request = ExecutionRequest(
            request_id=f"{WORKLOAD_ID}_{adapter.backend_name}_{i}",
            workload_id=WORKLOAD_ID,
            shots=shots,
            execution_mode=mode,
            backend_name=adapter.backend_name,
            seed=SEED + i,
            metadata={
                "circuit_name": circuit.name,
                "workload_round": i,
                "adapter": type(adapter).__name__,
            },
        )
        print(f"\nExecuting circuit {i}: {circuit.name}")
        result = adapter.execute(request, circuit)
        results.append(result)
        show("Status", result.status)
        show("Backend", result.backend_name)
        show("Execution mode", result.execution_mode)
        show("Shots", result.shots)
        show("Counts", result.counts)
        show("Execution time (s)", result.execution_time_s)
        show("Metadata", result.metadata)

    status["AdapterExecution"] = (
        "PASS" if len(results) == len(circuits) else "PARTIAL"
    )

    # 4. QualityProfiler
    section(f"{display_name} | 4. QualityProfiler")
    try:
        qp = QualityProfiler()
        evaluated = 0
        for i, result in enumerate(results, 1):
            counts = result.counts or {}
            if not counts:
                probs = result.metadata.get("probabilities")
                if probs is not None:
                    print(
                        f"Circuit {i}: skipped count-based quality analysis. "
                        "IonQ ideal simulator returns probabilities, not counts."
                    )
                    show("Exact probabilities", probs)
                else:
                    print(f"Circuit {i}: no measurement counts; not applicable.")
                continue

            # Parity observable, computed for the returned bitstring keys.
            observable_values = {}
            for state in counts:
                compact = str(state).replace(" ", "")
                observable_values[state] = (
                    1.0 if compact.count("1") % 2 == 0 else -1.0
                )

            quality = qp.estimate_from_counts(
                counts=counts,
                observable_values=observable_values,
                confidence_level=CONFIDENCE,
            )
            evaluated += 1
            print(f"\nQuality profile {i}")
            show_profile(quality)

        status["QualityProfiler"] = (
            "PASS" if evaluated == len(results)
            else "PARTIAL / NOT APPLICABLE"
        )
    except Exception:
        status["QualityProfiler"] = "FAIL"
        traceback.print_exc()

    # 5. LatencyProfiler
    section(f"{display_name} | 5. LatencyProfiler")
    try:
        lp = LatencyProfiler()
        latency_profiles = []
        for i, result in enumerate(results, 1):
            profile = lp.profile_execution(result)
            latency_profiles.append(profile)
            print(f"\nLatency profile {i}")
            show_profile(profile)
        status["LatencyProfiler"] = "PASS"
    except Exception:
        status["LatencyProfiler"] = "FAIL"
        traceback.print_exc()

    # 6. CostEstimator
    section(f"{display_name} | 6. CostEstimator")
    try:
        estimator = CostEstimator()
        cost_profiles = []
        for i, result in enumerate(results, 1):
            # profile = estimator.estimate_from_execution(result,shots=result.shots)
            profile = estimator.estimate_from_execution(
                qpu_execution_time_s=result.execution_time_s or 0.0,
                shots=result.shots or 0,
                metadata={
                    "request_id": result.request_id,
                    "result_id": result.result_id,
                    "backend_name": result.backend_name,
                    "execution_mode": str(result.execution_mode),
                },
            )
            cost_profiles.append(profile)
            print(f"\nCost estimate {i}")
            show_profile(profile)
        status["CostEstimator"] = "PASS"
    except Exception:
        status["CostEstimator"] = "FAIL"
        traceback.print_exc()

    # 7. ResourceProfiler
    section(f"{display_name} | 7. ResourceProfiler")
    try:
        if workload_profile is None:
            raise RuntimeError("WorkloadProfiler did not produce a profile.")
        rp = ResourceProfiler()
        resource_profile = rp.profile_workload(
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

    return status


def run_classical_fallback_test() -> str:
    section("CLASSICAL ADAPTER | Fallback test")
    adapter = ClassicalAdapter()

    request = ExecutionRequest(
        request_id=f"{WORKLOAD_ID}_classical",
        workload_id=WORKLOAD_ID,
        shots=SHOTS,
        execution_mode=ExecutionMode.CLASSICAL,
        backend_name=adapter.backend_name,
        seed=SEED,
    )

    def classical_callable(req: ExecutionRequest) -> dict[str, Any]:
        return {
            "algorithm": "simple_classical_fallback",
            "received_shots": req.shots,
            "answer": 42,
        }

    result = adapter.execute(request, classical_callable)
    show("Backend information", adapter.get_backend_info())
    show("Status", result.status)
    show("Execution mode", result.execution_mode)
    show("Classical output", result.metadata.get("classical_output"))
    show("Execution time (s)", result.execution_time_s)
    print(
        "Measurement QualityProfiler is not applicable to this result: "
        "ClassicalAdapter returns an application output, not quantum counts."
    )
    return "PASS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--adapter",
        choices=[
            "all", "aer_ideal", "aer_noisy",
            "ionq_simulators", "ibm", "ionq_qpu",
        ],
        default="all",
    )
    parser.add_argument("--skip-classical", action="store_true")
    args = parser.parse_args()

    section("QFLOWPILOT SEVEN-PROFILER MULTI-ADAPTER TEST")
    show("Project root", ROOT)
    show("Selection", args.adapter)

    circuits = make_circuits()
    workload = make_workload()
    show("Workload ID", workload.workload_id)
    show("Workload type", workload.workload_type)
    show("Circuit count", len(circuits))

    adapters = build_adapters(args.adapter)
    if not adapters:
        print("No adapters configured for this selection.")
        return 2

    summary: dict[str, dict[str, str]] = {}

    for name, adapter, shots in adapters:
        try:
            summary[name] = run_one_quantum_adapter(
                name, adapter, shots, workload, circuits
            )
        except Exception as exc:
            print(f"\n[ADAPTER FAILED] {name}: {exc}")
            traceback.print_exc()
            summary[name] = {"AdapterPipeline": "FAIL"}

    if args.adapter == "all" and not args.skip_classical:
        try:
            summary["ClassicalAdapter"] = {
                "ClassicalAdapter": run_classical_fallback_test()
            }
        except Exception:
            traceback.print_exc()
            summary["ClassicalAdapter"] = {"ClassicalAdapter": "FAIL"}

    section("FINAL SUMMARY")
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
        if "PARTIAL" in result or "NOT APPLICABLE" in result
    ]

    show("Failed stages", len(failures))
    show("Partial / not applicable stages", len(partials))
    print(
        "\nA PARTIAL QualityProfiler result is expected for IonQ's ideal "
        "simulator because it returns probabilities instead of counts. "
        "It is also expected for the classical fallback because it does "
        "not produce a quantum measurement distribution."
    )
    print(
        "\nReal IBM/IonQ QPU execution is opt-in and may incur cost. "
        "Check account access, provider pricing, credits and backend status."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
