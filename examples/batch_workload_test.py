# from qiskit import QuantumCircuit

# from qflowpilot.core.models import (
#     WorkloadSpec,
#     WorkloadType,
# )
# from qflowpilot.profiler import WorkloadProfiler


# workload = WorkloadSpec(
#     workload_id="batch_001",
#     name="Independent QAOA Circuits",
#     workload_type=WorkloadType.BATCH,
#     algorithm="QAOA",
#     description="Five independent quantum circuit tasks.",
# )

# circuits = []

# for i in range(5):
#     circuit = QuantumCircuit(3, 3)

#     circuit.h([0, 1, 2])
#     circuit.cx(0, 1)
#     circuit.rz(0.5 + i * 0.1, 1)
#     circuit.measure([0, 1, 2], [0, 1, 2])

#     circuits.append(circuit)


# profiler = WorkloadProfiler()

# profile = profiler.profile_workload(
#     workload=workload,
#     circuits=circuits,
# )

# print("Workload:", profile.workload_name)
# print("Type:", profile.workload_type.value)
# print("Circuits:", profile.metadata["circuit_count"])
# print("Total gates:", profile.metadata["total_gates"])
# print("Average depth:", profile.metadata["average_depth"])
# print("Maximum depth:", profile.metadata["maximum_depth"])


from qiskit import QuantumCircuit
from qiskit.circuit import Parameter

from qflowpilot.core.models import (
    WorkloadSpec,
    WorkloadType,
)
from qflowpilot.profiler import WorkloadProfiler


workload = WorkloadSpec(
    workload_id="iterative_001",
    name="Iterative QAOA MaxCut",
    workload_type=WorkloadType.ITERATIVE,
    algorithm="QAOA",
    description=(
        "Iterative QAOA with quantum measurements "
        "and classical parameter updates."
    ),
)

gamma = Parameter("gamma")
beta = Parameter("beta")

rounds = []

for iteration in range(5):

    circuit = QuantumCircuit(3, 3)

    circuit.h([0, 1, 2])

    circuit.rzz(gamma, 0, 1)
    circuit.rzz(gamma, 1, 2)

    circuit.rx(beta, [0, 1, 2])

    circuit.measure([0, 1, 2], [0, 1, 2])

    rounds.append([circuit])


profiler = WorkloadProfiler()

profile = profiler.profile_workload(
    workload=workload,
    rounds=rounds,
)

print("Workload:", profile.workload_name)
print("Type:", profile.workload_type.value)
print("Rounds:", profile.metadata["number_of_rounds"])
print("Total circuits:", profile.metadata["circuit_count"])

for round_info in profile.metadata["round_summaries"]:
    print(
        "Round:",
        round_info["round_index"],
        "Gates:",
        round_info["total_gates"],
        "Depth:",
        round_info["maximum_depth"],
    )