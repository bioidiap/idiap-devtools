# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import click

from ..click import AliasedGroup
from .changelog import changelog
from .dav import dav
from .env import env
from .fullenv import fullenv
from .release import release
from .update_pins import update_pins


@click.group(
    cls=AliasedGroup,
    context_settings=dict(help_option_names=["-?", "-h", "--help"]),
)
def cli():
    """Idiap development tools - see available commands below"""
    pass


cli.add_command(changelog)
cli.add_command(dav)
cli.add_command(env)
cli.add_command(fullenv)
cli.add_command(release)
cli.add_command(update_pins)
