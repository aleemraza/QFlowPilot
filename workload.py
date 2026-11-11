# workload.py
from qiskit_optimization import QuadraticProgram
import numpy as np

class MaxCutWorkload:
    def __init__(self, num_nodes=5): # Changed to 5 to force CX gates
        self.num_nodes = num_nodes
        self.qp = self._build_problem()
        
    def _build_problem(self):
        qp = QuadraticProgram()
        for i in range(self.num_nodes):
            qp.binary_var(name=f"x{i}")
        
        # Complete graph K5 (every node connected to every other node)
        quadratic = {}
        for i in range(self.num_nodes):
            for j in range(i+1, self.num_nodes):
                quadratic[(f"x{i}", f"x{j}")] = 2 
                
        linear = {f"x{i}": 0 for i in range(self.num_nodes)}
        qp.minimize(linear=linear, quadratic=quadratic)
        return qp

    def get_ising(self):
        return self.qp.to_ising()[0]

    def get_classical_fallback(self):
        """Step 5: Classical Fallback (Brute force)"""
        best_val = float('inf')
        best_bitstring = None
        ising_op = self.get_ising()
        
        # We must evaluate using the Ising Hamiltonian to match QAOA
        from qiskit.quantum_info import SparsePauliOp
        
        for i in range(2**self.num_nodes):
            bitstring = format(i, f'0{self.num_nodes}b')
            
            # Evaluate the Ising Energy
            # Convert bitstring to measurement outcome dict
            outcome = {bitstring: 1.0}
            energy = ising_op.expectation_value(outcome).real
            
            if energy < best_val:
                best_val = energy
                best_bitstring = bitstring
                
        return best_bitstring, best_val