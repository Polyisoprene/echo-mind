"""E1-G: the default satiation constant is the fitted inter-burst median."""

from __future__ import annotations

from echomind.mind.social_satiation import TAU_S


def test_default_tau_is_the_fitted_median() -> None:
    assert TAU_S == 247.0
