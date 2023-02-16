# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pkg_resources
import tomlkit


def dependencies_from_pyproject_toml(
    path: str,
) -> tuple[str, list[pkg_resources.Requirement]]:
    """Returns a list with all ``project.optional-dependencies``

    Arguments:

        path: The path to a ``pyproject.toml`` file to load


    Returns:

        A list of optional dependencies (if any exist) on the provided python
        project.
    """

    data = tomlkit.load(open(path, "rb"))

    deps = data.get("project", {}).get("dependencies", [])
    optional_deps = data.get("project", {}).get("optional-dependencies", {})

    retval = list(pkg_resources.parse_requirements(deps))
    for v in optional_deps.values():
        retval += list(pkg_resources.parse_requirements(v))

    return data.get("project", {}).get("name", "UNKNOWN"), retval
