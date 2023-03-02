# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import click

from ...click import PreserveIndentCommand, verbosity_option
from ...logging import setup

logger = setup(__name__.split(".", 1)[0])


# These show on the gitlab project landing page (not visible on PyPI)
PROJECT_BADGES = [
    {
        "name": "Docs (latest)",
        "link_url": "{idiap_server}/docs/%{{project_path}}/%{{default_branch}}/index.html",
        "image_url": "https://img.shields.io/badge/docs-latest-orange.svg",
    },
    {
        "name": "Docs (stable)",
        "link_url": "{idiap_server}/docs/%{{project_path}}/stable/index.html",
        "image_url": "https://img.shields.io/badge/docs-stable-yellow.svg",
    },
    {
        "name": "Pipeline (status)",
        "link_url": "https://gitlab.idiap.ch/%{{project_path}}/commits/%{{default_branch}}",
        "image_url": "https://gitlab.idiap.ch/%{{project_path}}/badges/%{{default_branch}}/pipeline.svg",
    },
    {
        "name": "Coverage (latest)",
        "link_url": "https://gitlab.idiap.ch/%{{project_path}}/commits/%{{default_branch}}",
        "image_url": "https://gitlab.idiap.ch/%{{project_path}}/badges/%{{default_branch}}/coverage.svg",
    },
    {
        "name": "PyPI (version)",
        "link_url": "https://pypi.python.org/pypi/{name}",
        "image_url": "https://img.shields.io/pypi/v/{name}.svg",
    },
]


# These show on the README and will be visible in PyPI
README_BADGES = [
    {
        "name": "latest-docs",
        "link_url": "{idiap_server}/docs/{group}/{name}/stable/index.html",
        "image_url": "https://img.shields.io/badge/docs-stable-yellow.svg",
    },
    {
        "name": "build",
        "link_url": "https://gitlab.idiap.ch/{group}/{name}/commits/master",
        "image_url": "https://gitlab.idiap.ch/{group}/{name}/badges/master/pipeline.svg",
    },
    {
        "name": "coverage",
        "link_url": "https://gitlab.idiap.ch/{group}/{name}/commits/master",
        "image_url": "https://gitlab.idiap.ch/{group}/{name}/badges/master/coverage.svg",
    },
    {
        "name": "repository",
        "link_url": "https://gitlab.idiap.ch/{group}/{name}",
        "image_url": "https://img.shields.io/badge/gitlab-project-0000c0.svg",
    },
]


def _update_readme(content, info):
    """Updates the README content provided, replacing badges."""
    import re

    new_badges_text = []
    for badge in README_BADGES:
        data = {k: v.format(**info) for (k, v) in badge.items()}
        new_badges_text.append(
            "[![{name}]({image_url})]({link_url})".format(**data)
        )
    new_badges_text = "\n" + "\n".join(new_badges_text) + "\n"
    # matches only 3 or more occurences of markdown badges
    expression = r"(\s?\[\!\[(?P<name>(\s|\w|-)+)\]\((?P<image_url>\S+)\)\]\((?P<link_url>\S+)\)){3,}"
    return re.sub(expression, new_badges_text, content)


@click.command(
    cls=PreserveIndentCommand,
    epilog="""
Examples:

  1. Creates (by replacing) all existing badges in a gitlab project
     (software/idiap-devtools):

     .. code:: sh

        devtool gitlab badges software/idiap-devtools

   .. note:: This command also affects the README.md file.

""",
)
@click.argument("package")
@click.option(
    "--update-readme/--no-update-readme",
    default=True,
    help="Whether to update badges in the readme or not.",
)
@click.option(
    "-d",
    "--dry-run/--no-dry-run",
    default=False,
    help="Only goes through the actions, but does not execute them "
    "(combine with the verbosity flags - e.g. ``-vvv``) to enable "
    "printing to help you understand what will be done",
)
@click.option(
    "-s",
    "--server",
    help="The documentation server. Default value is https://www.idiap.ch/software/{group}",
)
@verbosity_option(logger=logger)
def badges(package, update_readme, dry_run, server, **_) -> None:
    """Creates stock badges for a project repository."""
    import typing

    import gitlab

    from ...gitlab import get_gitlab_instance
    from ...gitlab.release import update_files_at_defaul_branch

    if dry_run:
        click.secho("!!!! DRY RUN MODE !!!!", fg="yellow", bold=True)
        click.secho(
            "No changes will be committed to GitLab.", fg="yellow", bold=True
        )

    if "/" not in package:
        raise RuntimeError('PACKAGE should be specified as "group/name"')

    gl = get_gitlab_instance()

    # we lookup the gitlab package once
    try:
        use_package = gl.projects.get(package)
        logger.info(
            "Found gitlab project %s (id=%d)",
            use_package.attributes["path_with_namespace"],
            use_package.id,
        )

        badges = use_package.badges.list()
        for badge in badges:
            logger.info(
                "Removing badge '%s' (id=%d) => '%s'",
                badge.name,
                badge.id,
                badge.link_url,
            )
            if not dry_run:
                badge.delete()

        # creates all stock badges, preserve positions
        info = dict(zip(("group", "name"), package.split("/", 1)))
        if not server:
            server = f"https://www.idiap.ch/software/{info['group']}"
        info["idiap_server"] = server[:-1] if server.endswith("/") else server
        for position, badge in enumerate(PROJECT_BADGES):
            data: dict[str, typing.Any] = {
                k: v.format(**info) for (k, v) in badge.items()
            }
            data["position"] = position
            logger.info(
                "Creating badge '%s' => '%s'",
                data["name"],
                data["link_url"],
            )
            if not dry_run:
                use_package.badges.create(data)

        # download and edit README to setup badges
        if update_readme:
            readme_file = use_package.files.get(
                file_path="README.md",
                ref=use_package.default_branch,
            )
            readme_content = readme_file.decode().decode()
            readme_content = _update_readme(readme_content, info)
            # commit and push changes
            logger.info("Changing README.md badges...")
            update_files_at_defaul_branch(
                use_package,
                {"README.md": readme_content},
                "Updated badges section [ci skip]",
                dry_run,
            )
            if dry_run:
                click.echo("(dry-run) contents of new README.md:\n")
                click.echo(readme_content)
        logger.info("All done.")

    except gitlab.GitlabGetError:
        logger.warn(
            "Gitlab access error - package %s does not exist?",
            package,
            exc_info=True,
        )
        click.secho(f"{package}: unknown", bold=True)
