# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import os

import click

from ...click import AliasedGroup, PreserveIndentCommand, verbosity_option
from ...logging import setup

logger = setup(__name__.split(".", 1)[0])


@click.group(cls=AliasedGroup)
def runners() -> None:
    """Commands for handling runners."""
    pass


@runners.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Enables the runner with description "linux-srv01" on all projects inside
     groups "group1" and "group2":

     .. code:: sh

        devtool gitlab runners enable --group -vv linux-srv01 group1 group2


  2. Enables the runner with description "linux-srv02" on a specific project:

     .. code:: sh

        devtool gitlab runners enable -vv linux-srv02 group1/my-project

""",
)
@click.argument("name")
@click.argument("targets", nargs=-1, required=True)
@click.option(
    "-g",
    "--group/--no-group",
    default=False,
    help="If set, consider the the provided name as a group name",
)
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@verbosity_option(logger)
def enable(name, targets, group, dry_run, **_) -> None:
    """Enables runners on whole gitlab groups or single projects.

    You may provide project names (like "group/project"), whole groups,
    and files containing list of projects to enable at certain runner
    at.
    """

    import pathlib

    from ...gitlab import get_gitlab_instance
    from ...gitlab.runners import (
        get_project,
        get_projects_from_file,
        get_projects_from_group,
        get_runner_from_description,
    )

    gl = get_gitlab_instance()
    gl.auth()

    the_runner = get_runner_from_description(gl, name)

    packages = []
    for target in targets:

        if os.path.exists(target):  # it is a file with project names
            packages += get_projects_from_file(gl, pathlib.Path(target))

        elif not group:  # it is a specific project
            packages.append(get_project(gl, target))

        else:  # it is a group - get all projects
            packages += get_projects_from_group(gl, target)

    for k in packages:

        try:

            logger.info(
                "Processing project %s (id=%d)",
                k.attributes["path_with_namespace"],
                k.id,
            )

            # checks if runner is not enabled first
            enabled = False
            for ll in k.runners.list(all=True):
                if ll.id == the_runner.id:  # it is there already
                    logger.warn(
                        "Runner %s (id=%d) is already enabled for project %s",
                        ll.attributes["description"],
                        ll.id,
                        k.attributes["path_with_namespace"],
                    )
                    enabled = True
                    break

            if not enabled:  # enable it
                if not dry_run:
                    k.runners.create({"runner_id": the_runner.id})
                    logger.info(
                        "Enabled runner %s (id=%d) for project %s",
                        the_runner.attributes["description"],
                        the_runner.id,
                        k.attributes["path_with_namespace"],
                    )
                else:
                    logger.info(
                        "Would enable runner %s (id=%d) for project %s",
                        the_runner.attributes["description"],
                        the_runner.id,
                        k.attributes["path_with_namespace"],
                    )

        except Exception as e:
            logger.error(
                "Ignoring project %s (id=%d): %s",
                k.attributes["path_with_namespace"],
                k.id,
                str(e),
            )


@runners.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Disables the runner with description "macmini" in project software/clapp
     and software/auto-intersphinx:

     .. code:: sh

        devtool gitlab runners disable -vv macmini software/clapp software/auto-intersphinx


  1. Disables the runner with description "macmini" for all projects in group software:

     .. code:: sh

        devtool gitlab runners disable -vv macmini software


  2. Disables the runner with description "macpro" on all projects it is
     associated to.  Notice this command effectively deletes the runner from
     the gitlab instance:

     .. code:: sh

        devtool gitlab runners disable -vv pro

""",
)
@click.argument("name")
@click.argument("targets", nargs=-1, required=False)
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@verbosity_option(logger)
def disable(name, targets, dry_run, **_) -> None:
    """Disables runners on whole gitlab groups or single projects.

    You may provide project names (like "group/project"), whole groups,
    files containing list of projects to load or omit the last argument,
    in which case all projects using this runner will be affected.
    """

    import pathlib

    from ...gitlab import get_gitlab_instance
    from ...gitlab.runners import (
        get_project,
        get_projects_from_file,
        get_projects_from_group,
        get_projects_from_runner,
        get_runner_from_description,
    )

    gl = get_gitlab_instance()
    gl.auth()

    the_runner = get_runner_from_description(gl, name)

    packages = []
    for target in targets:
        if "/" in target:  # it is a specific project
            packages.append(get_project(gl, target))

        elif os.path.exists(target):  # it is a file with project names
            packages += get_projects_from_file(gl, pathlib.Path(target))

        elif isinstance(target, str) and target:  # it is a group
            packages += get_projects_from_group(gl, target)

    if not targets:
        logger.info("Retrieving all runner associated projects...")
        packages += get_projects_from_runner(gl, the_runner)

    for k in packages:
        try:

            logger.info(
                "Processing project %s (id=%d)",
                k.attributes["path_with_namespace"],
                k.id,
            )

            # checks if runner is not already disabled first
            disabled = True
            for ll in k.runners.list(all=True):
                if ll.id == the_runner.id:  # it is there already
                    logger.debug(
                        "Runner %s (id=%d) is enabled for project %s",
                        ll.attributes["description"],
                        ll.id,
                        k.attributes["path_with_namespace"],
                    )
                    disabled = False
                    break

            if not disabled:  # disable it
                if not dry_run:
                    k.runners.delete(the_runner.id)
                    logger.info(
                        "Disabled runner %s (id=%d) for project %s",
                        the_runner.attributes["description"],
                        the_runner.id,
                        k.attributes["path_with_namespace"],
                    )
                else:
                    logger.info(
                        "Would disable runner %s (id=%d) for project %s",
                        the_runner.attributes["description"],
                        the_runner.id,
                        k.attributes["path_with_namespace"],
                    )

        except Exception as e:
            logger.error(
                "Ignoring project %s (id=%d): %s",
                k.attributes["path_with_namespace"],
                k.id,
                str(e),
            )


@runners.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Lists all projects a runner is associated to:

     .. code:: sh

        devtool gitlab runners list -vv macmini

""",
)
@click.argument("name")
@verbosity_option(logger=logger)
def list(name, **_) -> None:
    """Lists projects a runner is associated to."""

    from ...gitlab import get_gitlab_instance
    from ...gitlab.runners import get_runner_from_description

    gl = get_gitlab_instance()
    gl.auth()

    the_runner = get_runner_from_description(gl, name)

    logger.info("Retrieving all runner associated projects...")
    # gets extended version of object
    the_runner = gl.runners.get(the_runner.id)
    logger.info(
        "Found %d projects using runner %s",
        len(the_runner.projects),
        the_runner.description,
    )

    for k in the_runner.projects:
        click.echo(k["path_with_namespace"])
