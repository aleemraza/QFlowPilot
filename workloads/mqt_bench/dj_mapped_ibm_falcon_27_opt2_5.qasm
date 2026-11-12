// Benchmark created by MQT Bench on 2026-10-06
// For more info: https://mqt-bench.app/
// MQT Bench version: 2.3.0
// Qiskit version: 2.1.1
// Output format: qasm3
// Level: mapped
// Target: ibm_falcon_27
// Used gateset: ['id', 'x', 'sx', 'rz', 'cx', 'reset', 'delay', 'measure', 'if_else', 'while_loop', 'for_loop', 'switch_case', 'break', 'continue', 'box']
// Coupling map: [[0, 1], [1, 0], [1, 2], [1, 4], [2, 1], [2, 3], [3, 2], [3, 5], [4, 1], [4, 7], [5, 3], [5, 8], [6, 7], [7, 4], [7, 6], [7, 10], [8, 5], [8, 9], [8, 11], [9, 8], [10, 7], [10, 12], [11, 8], [11, 14], [12, 10], [12, 13], [12, 15], [13, 12], [13, 14], [14, 11], [14, 13], [14, 16], [15, 12], [15, 18], [16, 14], [16, 19], [17, 18], [18, 15], [18, 17], [18, 21], [19, 16], [19, 20], [19, 22], [20, 19], [21, 18], [21, 23], [22, 19], [22, 25], [23, 21], [23, 24], [24, 23], [24, 25], [25, 22], [25, 24], [25, 26], [26, 25]]

OPENQASM 3.0;
include "stdgates.inc";
bit[4] c;
rz(pi/2) $3;
sx $3;
rz(pi/2) $3;
rz(-pi/2) $5;
sx $5;
rz(pi) $5;
rz(pi/2) $8;
sx $8;
rz(-pi/2) $8;
rz(-pi/2) $9;
sx $9;
rz(pi) $9;
cx $9, $8;
cx $5, $8;
sx $5;
rz(-pi/2) $5;
cx $3, $5;
cx $5, $3;
cx $3, $5;
cx $5, $8;
rz(pi/2) $5;
sx $5;
rz(pi/2) $5;
sx $9;
rz(-pi/2) $9;
rz(pi/2) $11;
sx $11;
rz(pi) $11;
cx $11, $8;
sx $11;
rz(pi/2) $11;
barrier $9, $3, $5, $11, $8;
c[0] = measure $9;
c[1] = measure $3;
c[2] = measure $5;
c[3] = measure $11;
