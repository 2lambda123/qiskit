# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The Conditional Value at Risk (CVaR) measurement."""

import unittest
import warnings

from test.python.opflow import QiskitOpflowTestCase
import numpy as np
from ddt import ddt, data

from qiskit import QuantumCircuit
from qiskit.utils import algorithm_globals
from qiskit.opflow import (
    CVaRMeasurement,
    StateFn,
    Z,
    I,
    X,
    Y,
    Plus,
    PauliSumOp,
    PauliExpectation,
    MatrixExpectation,
    CVaRExpectation,
    ListOp,
    CircuitOp,
    AerPauliExpectation,
    MatrixOp,
    OpflowError,
)


class TestCVaRMeasurement(QiskitOpflowTestCase):
    """Test the CVaR measurement."""

    def expected_cvar(self, statevector, operator, alpha):
        """Compute the expected CVaR expected value."""

        probabilities = statevector * np.conj(statevector)

        # get energies
        num_bits = int(np.log2(len(statevector)))
        energies = []
        for i, _ in enumerate(probabilities):
            basis_state = np.binary_repr(i, num_bits)
            energies += [operator.eval(basis_state).eval(basis_state)]

        # sort ascending
        i_sorted = np.argsort(energies)
        energies = [energies[i] for i in i_sorted]
        probabilities = [probabilities[i] for i in i_sorted]

        # add up
        result = 0
        accumulated_probabilities = 0
        for energy, probability in zip(energies, probabilities):
            accumulated_probabilities += probability
            if accumulated_probabilities <= alpha:
                result += probability * energy
            else:  # final term
                result += (alpha - accumulated_probabilities + probability) * energy
                break

        return result / alpha

    def cleanup_algorithm_globals(self, massive):
        """Method used to reset the values of algorithm_globals."""
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            algorithm_globals.massive = massive

    def test_cvar_simple(self):
        """Test a simple case with a single Pauli."""
        theta = 1.2
        qc = QuantumCircuit(1)
        qc.ry(theta, 0)
        statefn = StateFn(qc)

        for alpha in [0.2, 0.4, 1]:
            with self.subTest(alpha=alpha):
                cvar = (CVaRMeasurement(Z, alpha) @ statefn).eval()
                ref = self.expected_cvar(statefn.to_matrix(), Z, alpha)
                self.assertAlmostEqual(cvar, ref)

    def test_cvar_simple_with_coeff(self):
        """Test a simple case with a non-unity coefficient"""
        theta = 2.2
        qc = QuantumCircuit(1)
        qc.ry(theta, 0)
        statefn = StateFn(qc)

        alpha = 0.2
        cvar = ((-1 * CVaRMeasurement(Z, alpha)) @ statefn).eval()
        ref = self.expected_cvar(statefn.to_matrix(), Z, alpha)
        self.assertAlmostEqual(cvar, -1 * ref)

    def test_add(self):
        """Test addition."""
        theta = 2.2
        qc = QuantumCircuit(1)
        qc.ry(theta, 0)
        statefn = StateFn(qc)

        alpha = 0.2
        cvar = -1 * CVaRMeasurement(Z, alpha)
        ref = self.expected_cvar(statefn.to_matrix(), Z, alpha)

        other = ~StateFn(I)

        # test add in both directions
        res1 = ((cvar + other) @ statefn).eval()
        res2 = ((other + other) @ statefn).eval()

        self.assertAlmostEqual(res1, 1 - ref)
        self.assertAlmostEqual(res2, 1 - ref)

    def invalid_input(self):
        """Test invalid input raises an error."""
        op = Z

        with self.subTest("alpha < 0"):
            with self.assertRaises(ValueError):
                _ = CVaRMeasurement(op, alpha=-0.2)

        with self.subTest("alpha > 1"):
            with self.assertRaises(ValueError):
                _ = CVaRMeasurement(op, alpha=12.3)

        with self.subTest("Single pauli operator not diagonal"):
            op = Y
            with self.assertRaises(OpflowError):
                _ = CVaRMeasurement(op)

        with self.subTest("Summed pauli operator not diagonal"):
            op = X ^ Z + Z ^ I
            with self.assertRaises(OpflowError):
                _ = CVaRMeasurement(op)

        with self.subTest("List operator not diagonal"):
            op = ListOp([X ^ Z, Z ^ I])
            with self.assertRaises(OpflowError):
                _ = CVaRMeasurement(op)

        with self.subTest("Matrix operator not diagonal"):
            op = MatrixOp([[1, 1], [0, 1]])
            with self.assertRaises(OpflowError):
                _ = CVaRMeasurement(op)

    def test_unsupported_operations(self):
        """Assert unsupported operations raise an error."""
        cvar = CVaRMeasurement(Z)

        attrs = ["to_matrix", "to_matrix_op", "to_density_matrix", "to_circuit_op", "sample"]
        for attr in attrs:
            with self.subTest(attr):
                with self.assertRaises(NotImplementedError):
                    _ = getattr(cvar, attr)()

        with self.subTest("adjoint"):
            with self.assertRaises(OpflowError):
                cvar.adjoint()

    def test_cvar_on_paulisumop(self):
        """Test a large PauliSumOp is checked for diagonality efficiently.

        Regression test for Qiskit/qiskit-terra#7573.
        """
        op = PauliSumOp.from_list([("Z" * 30, 1)])
        # assert global algorithm settings do not have massive calculations turned on
        # -- which is the default, but better to be sure in the test!
        # also add a cleanup so we're sure to reset to the original value after the test, even if
        # the test would fail
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            self.addCleanup(self.cleanup_algorithm_globals, algorithm_globals.massive)
            algorithm_globals.massive = False

        cvar = CVaRMeasurement(op, alpha=0.1)
        fake_probabilities = [0.2, 0.8]
        fake_energies = [1, 2]

        expectation = cvar.compute_cvar(fake_energies, fake_probabilities)
        self.assertEqual(expectation, 1)


@ddt
class TestCVaRExpectation(QiskitOpflowTestCase):
    """Test the CVaR expectation object."""

    def test_construction(self):
        """Test the correct operator expression is constructed."""

        alpha = 0.5
        base_expecation = PauliExpectation()
        cvar_expecation = CVaRExpectation(alpha=alpha, expectation=base_expecation)

        with self.subTest("single operator"):
            op = ~StateFn(Z) @ Plus
            expected = CVaRMeasurement(Z, alpha) @ Plus
            cvar = cvar_expecation.convert(op)
            self.assertEqual(cvar, expected)

        with self.subTest("list operator"):
            op = ~StateFn(ListOp([Z ^ Z, I ^ Z])) @ (Plus ^ Plus)
            expected = ListOp(
                [
                    CVaRMeasurement((Z ^ Z), alpha) @ (Plus ^ Plus),
                    CVaRMeasurement((I ^ Z), alpha) @ (Plus ^ Plus),
                ]
            )
            cvar = cvar_expecation.convert(op)
            self.assertEqual(cvar, expected)

    def test_unsupported_expectation(self):
        """Assert passing an AerPauliExpectation raises an error."""
        expecation = AerPauliExpectation()
        with self.assertRaises(NotImplementedError):
            _ = CVaRExpectation(alpha=1, expectation=expecation)

    @data(PauliExpectation(), MatrixExpectation())
    def test_underlying_expectation(self, base_expecation):
        """Test the underlying expectation works correctly."""

        cvar_expecation = CVaRExpectation(alpha=0.3, expectation=base_expecation)
        circuit = QuantumCircuit(2)
        circuit.z(0)
        circuit.cp(0.5, 0, 1)
        circuit.t(1)
        op = ~StateFn(CircuitOp(circuit)) @ (Plus ^ 2)

        cvar = cvar_expecation.convert(op)
        expected = base_expecation.convert(op)

        # test if the operators have been transformed in the same manner
        self.assertEqual(cvar.oplist[0].primitive, expected.oplist[0].primitive)

    def test_compute_variance(self):
        """Test if the compute_variance method works"""
        alphas = [0, 0.3, 0.5, 0.7, 1]
        correct_vars = [0, 0, 0, 0.8163, 1]
        for i, alpha in enumerate(alphas):
            base_expecation = PauliExpectation()
            cvar_expecation = CVaRExpectation(alpha=alpha, expectation=base_expecation)
            op = ~StateFn(Z ^ Z) @ (Plus ^ Plus)
            cvar_var = cvar_expecation.compute_variance(op)
            np.testing.assert_almost_equal(cvar_var, correct_vars[i], decimal=3)


if __name__ == "__main__":
    unittest.main()
