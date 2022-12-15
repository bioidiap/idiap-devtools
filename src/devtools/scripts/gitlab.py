# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import click

from ..click import AliasedGroup
from ..logging import setup
from .changelog import changelog
from .release import release

logger = setup(__name__.split(".", 1)[0])


@click.group(cls=AliasedGroup)
def gitlab() -> None:
    """Commands that interact directly with GitLab.

    Commands defined here are supposed to interact with gitlab, and
    add/modify/remove resources on it directly.  To avoid repetitive asking,
    create a configuration file as indicated in the
    :ref:`devtools.install.setup.gitlab` section of the user guide.
    """

    pass


gitlab.add_command(changelog)
gitlab.add_command(release)
