# Copyright © 2023 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

import pytest

from pkg_resources import Requirement

from idiap_devtools.gitlab import release


def test_pinning_no_constraints():
    """Pinning a simple packages list without pre-constraints."""
    constraints = [
        Requirement("pkg-a == 1.2.3"),  # Strict constraint
        Requirement("pkg-b >= 2.5"),  # Greater or equal constraint
        # pkg-c: package not in the constraints list
        Requirement("pkg-d ~= 2.0"),  # Compatible constraint
        Requirement("pkg-e@https://www.idiap.ch/dummy/pkg-e"),  # URL constraint
        Requirement("pkg-z == 1.0.0"),  # Constraint not in the packages list
    ]
    pkgs = ["pkg-a", "pkg-b", "pkg-c", "pkg-d", "pkg-e"]

    # Actual call. Modifies pkgs in-place.
    release._pin_versions_of_packages_list(
        packages_list=pkgs,
        dependencies_versions=constraints,
    )

    expected_pkgs = [
        "pkg-a==1.2.3",
        "pkg-b>=2.5",
        "pkg-c",
        "pkg-d~=2.0",
        "pkg-e@ https://www.idiap.ch/dummy/pkg-e",
    ]

    assert pkgs == expected_pkgs


def test_pinning_with_compatible_constraints():
    """Pinning a packages list with some constraints already applied."""
    constraints = [
        Requirement("pkg-a == 1.2.3"),  # Specific constraint
        Requirement("pkg-b >= 2.5"),  # Greater or equal constraint
        Requirement("pkg-c == 2.5"),  # Specific constraint
        Requirement("pkg-d ~= 1.2"),  # Compatible constraint
        Requirement(
            "pkg-e@ https://www.idiap.ch/dummy/pkg-e"
        ),  # URL constraint
        Requirement("pkg-g == 1.1.2"),
        Requirement("pkg-z == 1.0.0"),  # Constraint not in the packages list
    ]
    pkgs = [
        "pkg-a == 1.2.3",  # Same specific version as the constraint
        "pkg-b == 2.8",  # Stricter than the constraint
        "pkg-c >= 2.0",  # Less strict than the constraint
        "pkg-d ~= 1.2",
        "pkg-e == 1.2",  # Less strict than an URL constraint
        "pkg-f == 1.0",  # Not in constraints
        "pkg-g@ https://www.idiap.ch/dummy/pgk-g",  # URL in pre-constraint
    ]

    # Actual call. Modifies pkgs in-place.
    release._pin_versions_of_packages_list(
        packages_list=pkgs,
        dependencies_versions=constraints,
    )

    expected_pkgs = [
        "pkg-a==1.2.3",
        "pkg-b == 2.8",
        "pkg-c==2.5",
        "pkg-d~=1.2",
        "pkg-e@ https://www.idiap.ch/dummy/pkg-e",
        "pkg-f == 1.0",
        "pkg-g@ https://www.idiap.ch/dummy/pkg-g",
    ]

    assert pkgs == expected_pkgs


def test_pinning_with_incompatible_constraints():
    """Pinning a packages list with some constraints already applied but
    incompatible."""

    # Straight up incompatible
    constraints = [Requirement("pkg-a == 1.2.3")]
    pkgs = ["pkg-a == 2.0"]

    with pytest.raises(ValueError):
        release._pin_versions_of_packages_list(pkgs, constraints)

    # Incompatible due to a range specifier
    constraints = [Requirement("pkg-a >= 2.5")]
    pkgs = ["pkg-a < 2"]

    with pytest.raises(ValueError):
        release._pin_versions_of_packages_list(pkgs, constraints)
