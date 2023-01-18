# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import io
import os
import pathlib
import typing

import conda_build.config
import pkg_resources
import tomli
import xdg
import yaml

from .logging import setup

logger = setup(__name__)


USER_CONFIGURATION = xdg.xdg_config_home() / "devtools.toml"
"""The default location for the user configuration file"""


def load(dir: pathlib.Path) -> dict[str, typing.Any]:
    """Loads a profile TOML file, returns a dictionary with contents."""

    with (dir / "profile.toml").open("rb") as f:
        return tomli.load(f)


def get_path(name: str | pathlib.Path) -> pathlib.Path | None:
    """Returns the local directory of the named profile.

    If the input name corresponds to an existing directory, then that is
    returned.  Otherwise, we lookup the said name inside the user
    configuration.  If one exists, then the path pointed by that variable is
    returned.  Otherwise, an exception is raised.


    Arguments:

        name: The name of the local profile to return - can be either an
            existing path, or any name from the user configuration file.


    Returns:

        Either ``None``, if the profile cannot be found, or a verified path, if
        one is found.
    """

    path = pathlib.Path(name)

    if path.exists() and os.path.isdir(path):
        logger.debug(f"Returning path to profile {str(path)}...")
        return path

    # if you get to this point, then no local directory with that name exists
    # check the user configuration for a specific key
    if os.path.exists(USER_CONFIGURATION):
        logger.debug(
            f"Loading user-configuration from {str(USER_CONFIGURATION)}..."
        )
        with open(USER_CONFIGURATION, "rb") as f:
            usercfg = tomli.load(f)
    else:
        usercfg = {}

    if name == "default":
        value = usercfg.get("profiles", {}).get("default", None)
        if value is None:
            return None
        name = value

    value = usercfg.get("profiles", {}).get(name, None)
    if value is None:
        logger.warning(
            f"Requested profile `{name}' is not an existing directory "
            f"or an existing profile key (may be you forgot to clone "
            f"the relevant repository or setup your configuration file?)"
        )
        return None

    return pathlib.Path(os.path.expanduser(value))


class Profile:
    """A class representing the development profile.

    Arguments:

        path: A directory, containing the file ``profile.toml``, defining the
            development profile.
    """

    data: dict[str, typing.Any]  #: A readout of the ``profile.toml`` file
    _basedir: pathlib.Path

    def __init__(self, path: str | pathlib.Path):
        basedir = get_path(path)
        if basedir is None:
            raise FileNotFoundError(
                f"Cannot find `profile.toml' in the input "
                f"profile path or key: {path}"
            )
        self._basedir = basedir
        with (self._basedir / "profile.toml").open("rb") as f:
            self.data = tomli.load(f)

    def conda_config(
        self, python: str, public: bool, stable: bool
    ) -> conda_build.config.Config:
        """Builds the conda-configuration to use based on the profile.

        Arguments:

            python: The python version in the format "X.Y" (e.g. "3.9" or
               "3.10")

            private: Set to ``True`` if we should use private channels/indexes
               to lookup dependencies.  Should be ``False`` otherwise

            stable: Set to ``True`` if we should only consider stable versions
              of packages, as opposed to pre-release ones (beta packages).  Set
              to ``False`` otherwise.
        """

        baserc = self.data.get("conda", {}).get("baserc")
        if baserc is None:
            condarc_options: dict[str, typing.Any] = dict(
                show_channel_urls=True
            )
        else:
            f = io.BytesIO(self.data["conda"]["baserc"].encode())
            condarc_options = yaml.load(f, Loader=yaml.FullLoader)

        channel_data = self.data.get("conda", {}).get("channels")
        privacy_key = "public" if public else "private"
        stability_key = "stable" if stable else "beta"
        if channel_data is not None:
            channels = channel_data[privacy_key][stability_key]
        else:
            channels = ["conda-forge"]

        condarc_options["channels"] = channels

        # incorporate constraints, if there are any
        constraints = self.data.get("conda", {}).get("constraints")
        if constraints is not None:
            if not os.path.isabs(constraints):
                constraints = self._basedir / pathlib.Path(constraints)
            condarc_options["variant_config_files"] = str(constraints)

        # detect append-file, if any
        copy_files = self.data.get("conda", {}).get("build-copy")
        if copy_files is not None:
            append_file = [
                k for k in copy_files if k.endswith("recipe_append.yaml")
            ]
            if append_file:
                condarc_options["append_sections_file"] = append_file[0]

        condarc_options["python"] = python

        conda_build_copy = self.data.get("conda", {}).get("build-copy", [])
        append_file = [k for k in conda_build_copy if k != constraints]
        append_file = append_file[0] if append_file else None

        from .conda import make_conda_config

        return make_conda_config(condarc_options)

    def python_indexes(self, public: bool, stable: bool) -> list[str]:
        """Returns Python indexes to be used according to the current profile.

        Arguments:

            private: Set to ``True`` if we should use private channels/indexes
               to lookup dependencies.  Should be ``False`` otherwise

            stable: Set to ``True`` if we should only consider stable versions
              of packages, as opposed to pre-release ones (beta packages).  Set
              to ``False`` otherwise.
        """
        indexes = self.data.get("python", {}).get("indexes")
        privacy_key = "public" if public else "private"
        stability_key = "stable" if stable else "beta"
        if indexes is not None:
            return indexes[privacy_key][stability_key]

        return [] if stable else ["--pre"]

    def get(
        self, key: str | typing.Iterable[str], default: typing.Any = None
    ) -> typing.Any:
        """Reads the contents of a certain toml profile variable."""

        if isinstance(key, str):
            return self.data.get(key, default)

        # key is a tuple of strings, iterate over the dictionary
        d = self.data
        for level in key:
            d = d.get(level)
            if d is None:
                return default
        return d

    def get_path(
        self,
        key: str | typing.Iterable[str],
        default: None | pathlib.Path = None,
    ) -> pathlib.Path | None:
        """Reads the contents of path from the profile and resolves it.

        This function will search for a given profile key, consider it points
        to a path (relative or absolute) and will return that resolved path to
        the caller.

        Arguments:

            key: The key, pointing to the variable inside ``profile.toml`` that
                contains the datafile to be _load_conda_packages

            default: The value to return to the caller by default, if the key
              does not exist within the profile.


        Returns:

            The selected profile file path, or the contents of ``default``
            otherwise.
        """

        path = self.get(key)

        if path is None:
            return default

        if isinstance(path, dict):
            raise KeyError(f"Key {key} does not correspond to a path")

        ppath = pathlib.Path(path)

        if not ppath.is_absolute():
            ppath = self._basedir / ppath

        return ppath

    def get_file_contents(
        self, key: str | typing.Iterable[str], default: None | str = None
    ) -> str | None:
        """Reads the contents of a file from the profile.

        This function will search for a given profile key, consider it points
        to a filename (relative or absolute) and will read its contents,
        returning them to the caller.

        Arguments:

            key: The key, pointing to the variable inside ``profile.toml`` that
                contains the datafile to be _load_conda_packages

            default: The value to return to the caller by default, if the key
              does not exist within the profile.


        Returns:

            The contents of the selected profile file, or the contents of
            ``default`` otherwise.
        """

        path = self.get_path(key)
        return path.open().read() if path is not None else default

    def conda_constraints(self, python: str) -> dict[str, str] | None:
        """Returns a list of conda constraints given the current profile.

        Arguments:

            python: The python version in the format "X.Y" (e.g. "3.9" or
               "3.10")
        """

        content = self.get_file_contents(("conda", "constraints"))

        if content is None:
            return None

        idx1 = content.find("# AUTOMATIC PARSING START")
        idx2 = content.find("# AUTOMATIC PARSING END")
        content = content[idx1:idx2]

        # filter out using conda-build specific markers
        from conda_build.metadata import ns_cfg, select_lines

        config = self.conda_config(python, public=True, stable=True)
        content = select_lines(content, ns_cfg(config), variants_in_place=False)

        package_pins = yaml.safe_load(content)

        package_names_map = package_pins.pop("package_names_map")

        return {
            f"{package_names_map.get(p, p)}": f"{str(v[0]).split(' ')[0]}"
            for p, v in package_pins.items()
        }

    def python_constraints(self) -> list[pkg_resources.Requirement] | None:
        """Returns a list of Python requirements given the current profile."""

        content = self.get_file_contents(("python", "constraints"))

        if content is None:
            return None

        return list(pkg_resources.parse_requirements(content))
