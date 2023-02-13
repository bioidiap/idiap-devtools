# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import contextlib
import copy
import logging
import os
import pathlib
import typing

import requests


@contextlib.contextmanager
def _root_logger_protection():
    """Protects the root logger against spurious (conda) manipulation."""

    root_logger = logging.getLogger()
    level = root_logger.level
    handlers = copy.copy(root_logger.handlers)

    yield

    root_logger.setLevel(level)
    root_logger.handlers = handlers


def _make_conda_config(config, python, append_file, condarc_options):
    """Creates a conda configuration for a build merging various sources.

    This function will use the conda-build API to construct a configuration by
    merging different sources of information.

    Args:

      config: Path leading to the ``conda_build_config.yaml`` to use
      python: The version of python to use for the build as ``x.y`` (e.g.
        ``3.6``)
      append_file: Path leading to the ``recipe_append.yaml`` file to use
      condarc_options: A dictionary (typically read from a condarc YAML file)
        that contains build and channel options

    Returns: A dictionary containing the merged configuration, as produced by
    conda-build API's ``get_or_merge_config()`` function.
    """

    with _root_logger_protection():
        from conda_build.api import get_or_merge_config
        from conda_build.conda_interface import url_path

        retval = get_or_merge_config(
            None,
            variant_config_files=config,
            python=python,
            append_sections_file=append_file,
            **condarc_options,
        )

    retval.channel_urls = []  # type: ignore

    for url in condarc_options["channels"]:
        # allow people to specify relative or absolute paths to local channels
        #    These channels still must follow conda rules - they must have the
        #    appropriate platform-specific subdir (e.g. win-64)
        if os.path.isdir(url):
            if not os.path.isabs(url):
                url = os.path.normpath(
                    os.path.abspath(os.path.join(os.getcwd(), url))
                )
            with _root_logger_protection():
                url = url_path(url)
        retval.channel_urls.append(url)  # type: ignore

    return retval


def load_packages_from_conda_build_config(
    conda_build_config: pathlib.Path,
    condarc_options: dict[str, typing.Any],
    with_pins: bool = False,
) -> tuple[list[str], dict[str, str]]:
    with open(conda_build_config) as f:
        content = f.read()

    idx1 = content.find("# AUTOMATIC PARSING START")
    idx2 = content.find("# AUTOMATIC PARSING END")
    content = content[idx1:idx2]

    # filter out using conda-build specific markers
    from conda_build.metadata import ns_cfg, select_lines

    config = _make_conda_config(conda_build_config, None, None, condarc_options)
    content = select_lines(content, ns_cfg(config), variants_in_place=False)

    import yaml

    package_pins = yaml.safe_load(content)

    package_names_map = package_pins.pop("package_names_map")

    if with_pins:
        # NB : in pins, need to strip the occasional " cuda*" suffix
        # tensorflow=x.x.x cuda* -> tensorflow=x.x.x
        packages = [
            f"{package_names_map.get(p, p)}={str(v[0]).split(' ')[0]}"
            for p, v in package_pins.items()
        ]
    else:
        packages = [package_names_map.get(p, p) for p in package_pins.keys()]

    return packages, package_names_map


def filter_python_packages(
    resolved_packages, conda_to_python: dict[str, str | None]
):
    """Filters the list of packages to return only Python packages available on
    PyPI.

    This function will also perform name translation and de-duplication of
    package names when possible.


    Args:

        resolved_packages: list of tuples ``(package, version)``, returned by the
            ``mamba create --dry-run`` subprocess, for the packages we care
            about.


    Returns:

        List of of packages and versions available on PyPI
    """

    keep_list = []

    print(f"Filtering {len(resolved_packages)} packages for PyPI availability")

    for p, v in resolved_packages:

        if p in conda_to_python["__ignore__"]:
            continue

        p = conda_to_python.get(p, p)

        try:
            url = f"https://pypi.org/pypi/{p}/{v}/json"
            r = requests.get(url)
            if r.ok:
                keep_list.append((p, v))
            else:
                print(f"{p}@{v} NOT found - ignoring")
        except requests.exceptions.RequestException:
            continue

    return keep_list


def update_pip_constraints_only(
    conda_config_path: pathlib.Path,
    pip_constraints_path: pathlib.Path,
    conda_to_python: dict[str, typing.Any],
) -> None:

    packages, _ = load_packages_from_conda_build_config(
        conda_config_path,
        {"channels": []},
        with_pins=True,
    )
    package_pairs = [p.split("=", 1) for p in packages]

    with pip_constraints_path.open("wt") as f:
        python_packages = filter_python_packages(package_pairs, conda_to_python)
        print(
            f"Saving {len(python_packages)} entries to "
            f"`{pip_constraints_path}'..."
        )
        constraints = [
            f"{name}=={version}\n" for name, version in python_packages
        ]
        f.writelines(constraints)
