from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2
from qiskit_optimization import QuadraticProgram
from qiskit_optimization.algorithms import MinimumEigenOptimizer
from qiskit_optimization.minimum_eigensolvers import QAOA
from qiskit_optimization.optimizers import COBYLA
import numpy as np

# ---------- 1. Build a small Max-Cut problem ----------
qp = QuadraticProgram()
for i in range(4):
    qp.binary_var(name=f"x{i}")

# Simple ring graph: 0-1, 1-2, 2-3, 3-0
edges = [(0,1), (1,2), (2,3), (3,0)]
linear = {f"x{i}": 0 for i in range(4)}
quadratic = {}
for i, j in edges:
    quadratic[(f"x{i}", f"x{j}")] = 2  # max-cut -> minimize -cut
qp.minimize(linear=linear, quadratic=quadratic)

# ---------- 2. Configure Sampler (QFlowPilot's "execution backend") ----------
backend = AerSimulator()
sampler = SamplerV2(seed=42, default_shots=1024)  # 初始 shots=1024

# ---------- 3. Build QAOA ----------
optimizer = COBYLA(maxiter=50)
qaoa = QAOA(sampler=sampler, optimizer=optimizer, reps=1)

# ---------- 4. Run and observe "quality signal" ----------
print("Running QAOA with 1024 shots...")
result = qaoa.compute_minimum_eigenvalue(qp.to_ising()[0])
print(f"Optimal value (energy): {result.optimal_value:.4f}")
print(f"Optimal point: {result.best_measurement['bitstring']}")

# QFlowPilot's ExecutionProfiler would record:
# - shots_used = 1024
# - eval_count = optimizer's function evaluation count (approximately)
# - optimal_value

# ---------- 5. Simple runtime decision (rule-based) ----------
# Assume the quality requirement is: energy must be below a threshold, otherwise increase shots and rerun.
QUALITY_THRESHOLD = -1.5  # 这个值需要根据实际图跑一次最优解来定，此处仅为演示

if result.optimal_value > QUALITY_THRESHOLD:
    print("\n[RuntimePolicy] Quality insufficient, retrying with 4096 shots...")
    sampler_hi = SamplerV2(seed=42, default_shots=4096)
    qaoa_hi = QAOA(sampler=sampler_hi, optimizer=COBYLA(maxiter=50), reps=1)
    result_hi = qaoa_hi.compute_minimum_eigenvalue(qp.to_ising()[0])
    print(f"Retry optimal value: {result_hi.optimal_value:.4f}")
    print(f"Retry bitstring: {result_hi.best_measurement['bitstring']}")
else:
    print("\n[RuntimePolicy] Quality acceptable, no retry needed.")