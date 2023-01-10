# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import logging
import pathlib
import typing

import gitlab
import gitlab.v4.objects

logger = logging.getLogger(__name__)


def get_runner_from_description(
    gl: gitlab.Gitlab, descr: str
) -> gitlab.v4.objects.runners.Runner:
    """Retrieves a runner object matching the description, or raises.

    Arguments:

        gl: gitlab service instance

        str: the runner description


    Returns:

        runner: the runner object, if one is found matching the description


    Raises:

        RuntimeError: if no runner matching the description is found.
    """

    # search for the runner to affect
    runners = [
        k
        for k in gl.runners.list(all=True)
        if k.attributes["description"] == descr
    ]
    if not runners:
        raise RuntimeError("Cannot find runner with description = %s", descr)
    the_runner = typing.cast(gitlab.v4.objects.runners.Runner, runners[0])
    logger.info(
        "Found runner %s (id=%d)",
        the_runner.attributes["description"],
        the_runner.attributes["id"],
    )

    return the_runner


def get_project(
    gl: gitlab.Gitlab, name: str
) -> gitlab.v4.objects.projects.Project:
    """Retrieves one single project."""

    retval = gl.projects.get(name)
    logger.debug(
        "Found gitlab project %s (id=%d)",
        retval.attributes["path_with_namespace"],
        retval.id,
    )
    return retval


def get_projects_from_group(
    gl: gitlab.Gitlab, name: str
) -> list[gitlab.v4.objects.projects.Project]:
    """Returns a list with all projects in a GitLab group."""

    group = gl.groups.get(name)
    logger.debug(
        "Found gitlab group %s (id=%d)",
        group.attributes["path"],
        group.id,
    )
    projects = group.projects.list(all=True, simple=True)
    logger.info(
        "Retrieving details for %d projects in group %s (id=%d). "
        "This may take a while...",
        len(projects),
        group.attributes["path"],
        group.id,
    )
    packages = []
    for k, proj in enumerate(projects):
        packages.append(get_project(gl, proj.id))
        logger.debug("Got data from project %d/%d", k + 1, len(projects))
    return packages


def get_projects_from_runner(
    gl: gitlab.Gitlab, runner: gitlab.v4.objects.runners.Runner
) -> list[gitlab.v4.objects.projects.Project]:
    """Retrieves a list of all projects that include a particular runner."""

    the_runner = gl.runners.get(runner.id)
    logger.info(
        "Retrieving details for %d projects using runner %s (id=%d). "
        "This may take a while...",
        len(the_runner.projects),
        the_runner.description,
        the_runner.id,
    )
    packages = []
    for k, proj in enumerate(the_runner.projects):
        packages.append(get_project(gl, proj["id"]))
        logger.debug(
            "Got data from project %d/%d", k + 1, len(the_runner.projects)
        )
    return packages


def get_projects_from_file(
    gl: gitlab.Gitlab, filename: pathlib.Path
) -> list[gitlab.v4.objects.projects.Project]:
    """Retrieves a list of projects based on lines of a file."""

    packages = []
    with filename.open("rt") as f:
        lines = [k.strip() for k in f.readlines()]
        lines = [k for k in lines if k and not k.startswith("#")]
        logger.info("Loaded %d entries from file %s", len(lines), filename)
        for k, proj in enumerate(lines):
            packages.append(get_project(gl, proj))
            logger.debug("Got data from project %d/%d", k + 1, len(lines))
    return packages
