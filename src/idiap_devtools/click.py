# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import logging
import typing

import click

from .profile import get_profile_path


def verbosity_option(
    logger: logging.Logger,
    short_name: str = "v",
    name: str = "verbose",
    dflt: int = 0,
    **kwargs: typing.Any,
) -> typing.Callable[..., typing.Any]:
    """Click-option decorator that adds a ``-v``/``--verbose`` option to a cli.

    This decorator adds a click option to your CLI to set the log-level on a
    provided :py:class:`logging.Logger`.  You must specifically determine the
    logger that will be affected by this CLI option, via the ``logger`` option.

    .. code-block:: python

       @verbosity_option(logger=logger)

    The verbosity option has the "count" type, and has a default value of 0.
    At each time you provide ``-v`` options on the command-line, this value is
    increased by one.  For example, a CLI setting of ``-vvv`` will set the
    value of this option to 3.  This is the mapping between the value of this
    option (count of ``-v`` CLI options passed) and the log-level set at the
    provided logger:

    * 0 (no ``-v`` option provided): ``logger.setLevel(logging.ERROR)``
    * 1 (``-v``): ``logger.setLevel(logging.WARNING)``
    * 2 (``-vv``): ``logger.setLevel(logging.INFO)``
    * 3 (``-vvv`` or more): ``logger.setLevel(logging.DEBUG)``


    Arguments:

        logger: The :py:class:`logging.Logger` to be set.

        short_name: Short name of the option.  If not set, then use ``v``

        name: Long name of the option.  If not set, then use ``verbose`` --
            this will also become the name of the contextual parameter for
            click.

        dlft: The default verbosity level to use (defaults to 0).

        **kwargs: Further keyword-arguments to be forwarded to the underlying
            :py:func:`click.option`


    Returns:

        A callable, that follows the :py:mod:`click`-framework policy for
        option decorators.  Use it accordingly.
    """

    def custom_verbosity_option(f):
        def callback(ctx, param, value):
            ctx.meta[name] = value
            log_level: int = {
                0: logging.ERROR,
                1: logging.WARNING,
                2: logging.INFO,
                3: logging.DEBUG,
            }[value]

            logger.setLevel(log_level)
            logger.debug(
                f'Level of Logger("{logger.name}") was set to {log_level}'
            )
            return value

        return click.option(
            f"-{short_name}",
            f"--{name}",
            count=True,
            type=click.IntRange(min=0, max=3, clamp=True),
            default=dflt,
            show_default=True,
            help=(
                f"Increase the verbosity level from 0 (only error and "
                f"critical) messages will be displayed, to 1 (like 0, but adds "
                f"warnings), 2 (like 1, but adds info messags), and 3 (like 2, "
                f"but also adds debugging messages) by adding the --{name} "
                f"option as often as desired (e.g. '-vvv' for debug)."
            ),
            callback=callback,
            **kwargs,
        )(f)

    return custom_verbosity_option


class AliasedGroup(click.Group):
    """Class that handles prefix aliasing for commands."""

    def get_command(  # type: ignore
        self, ctx: click.core.Context, cmd_name: str
    ) -> click.Command | None:
        """Returns the decorated command.

        Arguments:

            ctx: The current command context being parsed

            cmd_name: The subcommand name that was called


        Returns:

            The decorated command with aliasing capabilities
        """

        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx) if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail("Too many matches: %s" % ", ".join(sorted(matches)))


class PreserveIndentCommand(click.Command):
    """A click command that preserves text indentation."""

    def format_epilog(
        self, _: click.core.Context, formatter: click.formatting.HelpFormatter
    ) -> None:
        """Formats the command epilog during --help.

        Arguments:

            _: The current parsing context

            formatter: The formatter to use for printing text
        """

        if self.epilog:
            formatter.write_paragraph()
            for line in self.epilog.split("\n"):
                formatter.write_text(line)

    def format_description(
        self, _: click.core.Context, formatter: click.formatting.HelpFormatter
    ) -> None:
        """Formats the command description during --help.

        Arguments:

            _: The current parsing context

            formatter: The formatter to use for printing text
        """

        if self.description:
            formatter.write_paragraph()
            for line in self.description.split("\n"):
                formatter.write_text(line)


def validate_profile(_: click.Context, __: str, value: str) -> str:
    """Callback for click doing a profile name validation.

    Arguments:

        _: current command context

        __: The option being validated

        value: The value set for the option


    Returns:

        The validated option value
    """
    profile_path = get_profile_path(value)
    if profile_path is None:
        raise click.BadParameter(
            "You have not provided a development profile path "
            "(-P/--profile) option or set the `default' profile at "
            "your configuration file.  I need one of these to "
            "load my development constants"
        )

    if not (profile_path / "profile.toml").exists():
        raise click.BadParameter(
            f"Error while attempting to load the profile `{value}' from "
            f"`{str(profile_path/'profile.toml')}' - file does not exist!"
        )

    return value
