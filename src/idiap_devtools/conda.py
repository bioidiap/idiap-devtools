# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import contextlib
import copy
import logging
import os
import typing

from .utils import uniq

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def root_logger_protection():
    """Protects the root logger against spurious (conda) manipulation."""
    root_logger = logging.getLogger()
    level = root_logger.level
    handlers = copy.copy(root_logger.handlers)

    yield

    root_logger.setLevel(level)
    root_logger.handlers = handlers


def make_conda_config(
    options: dict[str, typing.Any],
) -> typing.Any:
    """Creates a conda configuration for a build merging various sources.

    This function will use the conda-build API to construct a configuration by
    merging different sources of information.


    Arguments:

      options: A dictionary (typically read from a condarc YAML file) that
        contains build and channel options

    Returns:

        A dictionary containing the merged configuration, as produced by
        conda-build API's ``get_or_merge_config()`` function.
    """

    with root_logger_protection():
        import conda_build.api

        from conda_build.conda_interface import url_path

        retval = conda_build.api.get_or_merge_config(None, **options)

    retval.channel_urls = []

    for url in options["channels"]:
        # allow people to specify relative or absolute paths to local channels
        #    These channels still must follow conda rules - they must have the
        #    appropriate platform-specific subdir (e.g. win-64)
        if os.path.isdir(url):
            if not os.path.isabs(url):
                url = os.path.normpath(
                    os.path.abspath(os.path.join(os.getcwd(), url))
                )
            with root_logger_protection():
                url = url_path(url)
        retval.channel_urls.append(url)

    return retval


def use_mambabuild():
    """Will inject mamba solver to conda build API to speed up resolves."""
    # only importing this module will do the job.

    with root_logger_protection():
        from boa.cli.mambabuild import prepare

        prepare()


def get_rendered_metadata(recipe_dir, config):
    """Renders the recipe and returns the interpreted YAML file."""
    with root_logger_protection():
        import conda_build.api

        # use mambabuild instead
        use_mambabuild()
        return conda_build.api.render(recipe_dir, config=config)


def get_parsed_recipe(metadata):
    """Renders the recipe and returns the interpreted YAML file."""
    with root_logger_protection():
        return metadata[0][0].get_rendered_recipe_text()


def remove_pins(deps):
    return [ll.split()[0] for ll in deps]


def parse_dependencies(recipe_dir, config) -> tuple[str, list[str]]:
    metadata = get_rendered_metadata(recipe_dir, config)
    recipe = get_parsed_recipe(metadata)
    requirements = []
    for section in ("build", "host"):
        requirements += remove_pins(
            recipe.get("requirements", {}).get(section, [])
        )
    # we don't remove pins for the rest of the recipe
    requirements += recipe.get("requirements", {}).get("run", [])
    requirements += recipe.get("test", {}).get("requires", [])

    return recipe["package"]["name"], uniq(requirements)
