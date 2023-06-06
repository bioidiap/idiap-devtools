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
        Requirement("pkg-e@ https://www.idiap.ch/dummy/pkg-e"),  # URL constr.
        Requirement("pkg-f[extra1] == 1.2.3"),  # With extras
        Requirement("pkg-g[extra2]@ https://www.idiap.ch/dummy/pkg-g"),
        Requirement("pkg-h == 1.2.3; sys_platform == 'darwin'"),  # With marker
        Requirement(
            "pkg-i@ https://www.idiap.ch/dummy/pkg-i ; sys_platform == 'darwin'"
        ),
        Requirement("pkg-z == 1.0.0"),  # Constraint not in the packages list
    ]
    pkgs = [
        "pkg-a",
        "pkg-b",
        "pkg-c",
        "pkg-d",
        "pkg-e",
        "pkg-f",
        "pkg-g",
        "pkg-h",
        "pkg-i",
    ]

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
        "pkg-f[extra1]==1.2.3",
        "pkg-g[extra2]@ https://www.idiap.ch/dummy/pkg-g",
        'pkg-h==1.2.3; sys_platform == "darwin"',
        'pkg-i@ https://www.idiap.ch/dummy/pkg-i ; sys_platform == "darwin"',
    ]

    assert pkgs == expected_pkgs


def test_pinning_multiple_times():
    """Pinning with a constraint present multiple times is not supported."""
    constraints = [
        Requirement("pkg-a == 1.2.3; sys_platform == 'darwin'"),
        Requirement("pkg-a == 3.2.1; sys_platform != 'darwin'"),
    ]
    pkgs = ["pkg-a"]

    with pytest.raises(NotImplementedError):
        release._pin_versions_of_packages_list(pkgs, constraints)


def test_pinning_with_constraints():
    """Pinning a packages list with any constraints already applied."""
    constraints = [Requirement("pkg-a == 1.2.3")]
    pkgs = ["pkg-a == 2.0"]  # Constraints can not be set in the packages list.

    with pytest.raises(ValueError):
        release._pin_versions_of_packages_list(pkgs, constraints)

    constraints = [Requirement("pkg-a == 1.2.3")]
    pkgs = ["pkg-a; sys_platform != 'darwin'"]  # Neither can the markers

    with pytest.raises(ValueError):
        release._pin_versions_of_packages_list(pkgs, constraints)

    constraints = [Requirement("pkg-a == 1.2.3")]
    pkgs = ["pkg-a(extra)"]  # Nor the extras

    with pytest.raises(ValueError):
        release._pin_versions_of_packages_list(pkgs, constraints)
