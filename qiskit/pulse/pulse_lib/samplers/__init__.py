# This code is part of Qiskit.
#
# (C) Copyright IBM 2017, 2019.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Module for methods which sample continuous functions."""
import warnings

from qiskit.pulse.library.samplers.decorators import left, right, midpoint
warnings.warn("the pulse_lib module is deprecated, pulse_lib is renamed to library",
              DeprecationWarning, stacklevel=2)