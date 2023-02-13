# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import sys

import click

from ..click import PreserveIndentCommand, validate_profile, verbosity_option
from ..logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

    1. Updates the default constraints taking as base a Python 3.10 environment:

       .. code:: sh

          devtool update-pins --python=3.10

    2. Updates the default constraints using the default Python version
       (installed on the base environment), and respecting a few provided
       constraints (manual pins):

       .. code:: sh

          devtool update-pins --python=3.10 opencv=4.5.1 pytorch=1.9

    3. Updates the constraints on a checked-out profile directory:

       .. code:: sh

          devtool update-pins --python=3.10 --profile=../another-profile
""",
)
@click.argument("manual_pins", nargs=-1)
@click.option(
    "-P",
    "--profile",
    default="default",
    show_default=True,
    callback=validate_profile,
    help="Directory containing the development profile (and a file named "
    "profile.toml), or the name of a configuration key pointing to the "
    "development profile to use",
)
@click.option(
    "-p",
    "--python",
    default=("%d.%d" % sys.version_info[:2]),
    show_default=True,
    help="Version of python to build the environment for",
)
@click.option(
    "-p/-P",
    "--only-pip/--no-only-pip",
    default=False,
    help="Set this to update **only** pip constraints. The pins will "
    "then be copied from the conda-constraints to the pip one.",
)
@verbosity_option(logger=logger)
def update_pins(manual_pins, profile, python, only_pip, **_) -> None:
    """Updates pip/mamba/conda package constraints (requires conda)

    The update is done by checking-up conda-forge and trying to create
    an environment with all packages listed on the current conda
    constraints. Once an environment has been resolved, it is "copied"
    to the Python (pip) constraints file, by excluding non-Python
    packages.
    """
    import subprocess

    from ..profile import Profile
    from ..update_pins import (
        filter_python_packages,
        load_packages_from_conda_build_config,
        update_pip_constraints_only,
    )

    # 1. loads profile data
    the_profile = Profile(profile)

    conda_config_path = the_profile.get_path(("conda", "constraints"))

    if conda_config_path is None:
        click.secho(
            f"No conda-constraints at profile `{profile}' - aborting",
            bold=True,
            fg="red",
        )
        return

    # 2. loads the current conda pins
    packages, package_names_map = load_packages_from_conda_build_config(
        conda_config_path, {"channels": []}
    )

    pip_constraints_path = the_profile.get_path(("python", "constraints"))
    conda_to_python = the_profile.get(("conda", "to_python"), {})

    if only_pip:
        if pip_constraints_path is None:
            click.secho(
                f"No pip-constraints at profile `{profile}' - aborting",
                bold=True,
                fg="red",
            )
            return

        click.secho(
            f"Copying pins from {str(conda_config_path)} to "
            f"{str(pip_constraints_path)}...",
            bold=True,
        )
        return update_pip_constraints_only(
            conda_config_path, pip_constraints_path, conda_to_python
        )

    reversed_package_names_map = {v: k for k, v in package_names_map.items()}

    # ask mamba to create an environment with the packages
    try:
        cmd = (
            [
                "mamba",
                "create",
                "--dry-run",
                "--override-channels",
                "-c",
                "conda-forge",
                "-n",
                "temp_env",
                f"python={python}",
            ]
            + packages
            + list(manual_pins)
        )
        click.secho(
            f"Executing `{' '.join(cmd)}' to calculate a viable "
            f"environment...",
            bold=True,
        )
        output = subprocess.run(cmd, capture_output=True, check=True)

    except subprocess.CalledProcessError as e:
        click.secho(e.output.decode(), bold=True, fg="red")
        raise e

    env_text = output.stdout.decode("utf-8")
    click.secho(env_text, fg="magenta")

    resolved_packages = []
    for line in env_text.split("\n"):
        line = line.strip()
        if line.startswith("+ "):
            values = line.split()
            name, version = values[1], values[2]
            resolved_packages.append((name, version))

    # we only monitor a subset of packages
    resolved_packages = [
        (p, v) for (p, v) in resolved_packages if p in packages
    ]

    # write the new pinning
    click.secho(
        f"Saving {len(resolved_packages)} updated entries to "
        f"`{conda_config_path}'...",
        bold=True,
    )

    with conda_config_path.open("rt") as f:
        content = f.read()

    START = """
# AUTOMATIC PARSING START
# DO NOT MODIFY THIS COMMENT

# list all packages with dashes or dots in their names, here:"""
    idx1 = content.find(START)
    idx2 = content.find("# AUTOMATIC PARSING END")
    pins = "\n".join(
        f'{reversed_package_names_map.get(name, name)}:\n  - "{version}"'
        for name, version in resolved_packages
    )
    package_names_map_str = "\n".join(
        f"  {k}: {v}" for k, v in package_names_map.items()
    )

    new_content = f"""{START}
package_names_map:
{package_names_map_str}


{pins}

"""

    content = content[:idx1] + new_content + content[idx2:]
    with conda_config_path.open("w") as f:
        f.write(content)

    if pip_constraints_path is None:
        click.secho(
            f"No pip-constraints at profile `{profile}' - not updating...",
            bold=True,
        )
        return

    with pip_constraints_path.open("w") as f:
        python_packages = filter_python_packages(
            resolved_packages, conda_to_python
        )
        click.secho(
            f"Saving {len(python_packages)} entries to "
            f"`{pip_constraints_path}'...",
            bold=True,
        )
        constraints = [
            f"{name}=={version}\n" for name, version in python_packages
        ]
        f.writelines(constraints)
