# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import typing

import click

from ...click import PreserveIndentCommand, verbosity_option
from ...logging import setup

logger = setup(__name__.split(".", 1)[0])


def _change_settings(
    project, info: dict[str, typing.Any], dry_run: bool
) -> None:
    """Updates the project settings using ``info``"""

    name = f"{project.namespace['full_path']}/{project.name}"
    click.echo(f"Changing {name}...")

    if info.get("archive") is not None:
        if info["archive"]:
            click.secho("  -> archiving", bold=True)
            if not dry_run:
                project.archive()
        else:
            click.secho("  -> unarchiving", bold=True)
            if not dry_run:
                project.unarchive()

    if info.get("description") is not None:
        click.secho(
            f"  -> set description to '{info['description']}'", bold=True
        )
        if not dry_run:
            project.description = info["description"]
            project.save()

    if info.get("avatar") is not None:
        click.secho(f"  -> setting avatar to '{info['avatar']}'", bold=True)
        if not dry_run:
            project.avatar = open(info["avatar"], "rb")
            project.save()


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. List settings in a gitlab project (software/idiap-devtools):

     .. code::sh

        devtool gitlab settings software/idiap-devtools


  2. Simulates an update to the project description:

     .. code::sh

        devtool gitlab settings --description="new description" --dry-run software/idiap-devtools

""",
)
@click.argument("projects", nargs=-1, required=True)
@click.option(
    "-a",
    "--avatar",
    default=None,
    type=click.Path(file_okay=True, dir_okay=False, exists=True),
    help="Set this to update the project icon (avatar)",
)
@click.option(
    "-D",
    "--description",
    default=None,
    type=str,
    help="Set this to update the project description",
)
@click.option(
    "-g",
    "--group/--no-group",
    default=False,
    help="If set, consider the the provided name as a group name",
)
@click.option(
    "-A",
    "--archive/--unarchive",
    default=None,
    help="Set this to archive or unarchive a project",
)
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@verbosity_option(logger=logger)
def settings(
    projects, avatar, description, group, archive, dry_run, **_
) -> None:
    """Updates project settings."""

    import os

    from ...gitlab import get_gitlab_instance
    from ...gitlab.runners import (
        get_project,
        get_projects_from_file,
        get_projects_from_group,
    )

    # if we are in a dry-run mode, let's let it be known
    if dry_run:
        click.secho("!!!! DRY RUN MODE !!!!", fg="yellow", bold=True)
        click.secho(
            "No changes will be committed to GitLab.", fg="yellow", bold=True
        )

    gl = get_gitlab_instance()
    gl_projects = []

    for target in projects:

        if os.path.exists(target):  # it is a file with project names
            gl_projects += get_projects_from_file(gl, target)

        elif not group:  # it is a specific project
            gl_projects.append(get_project(gl, target))

        else:  # it is a group - get all projects
            gl_projects += get_projects_from_group(gl, target)

        for k in gl_projects:

            try:

                logger.info(
                    "Processing project %s (id=%d)",
                    k.attributes["path_with_namespace"],
                    k.id,
                )

                info_to_update = {}

                if avatar is not None:
                    info_to_update["avatar"] = avatar

                if archive is not None:
                    info_to_update["archive"] = archive

                if description is not None:
                    info_to_update["description"] = description

                if not info_to_update:
                    # list current settings
                    s = f"{k.namespace['name']}/{k.name}"
                    if k.archived:
                        s += " [archived]"
                    s += f": {k.description}"
                    click.echo(s)

                else:
                    _change_settings(k, info_to_update, dry_run)

            except Exception as e:
                logger.error(
                    "Ignoring project %s (id=%d): %s",
                    k.attributes["path_with_namespace"],
                    k.id,
                    str(e),
                )
