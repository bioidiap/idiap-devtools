# Copyright © 2022 Idiap Research Institute <contact@idiap.ch>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
import typing

logger = logging.getLogger(__name__)

_INTERVALS = (
    ("weeks", 604800),  # 60 * 60 * 24 * 7
    ("days", 86400),  # 60 * 60 * 24
    ("hours", 3600),  # 60 * 60
    ("minutes", 60),
    ("seconds", 1),
)
"""Time intervals that make up human readable time slots"""


def set_environment(
    name: str, value: str, env: dict[str, str] | os._Environ[str] = os.environ
) -> str:
    """Function to setup the environment variable and print debug message.

    Parameters:

        name: The name of the environment variable to set

        value: The value to set the environment variable to

        env: Optional environment (dictionary) where to set the variable at


    Returns:

        The value just set.
    """

    env[name] = value
    logger.info(f"environ['{name}'] = '{value}'")
    return value


def human_time(seconds: int | float, granularity: int = 2) -> str:
    """Returns a human readable time string like "1 day, 2 hours".

    This function will convert the provided time in seconds into weeks, days,
    hours, minutes and seconds.


    Parameters:

        seconds: The number of seconds to convert

        granularity: The granularity corresponds to how many elements will
            output. For a granularity of 2, only the first two non-zero entries
            are output.


    Returns:

        A string, that contains the human readable time.
    """

    result: list[str | None] = []

    for name, count in _INTERVALS:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip("s")
            result.append(f"{int(value)} {name}")
        else:
            # Add a blank if we're in the middle of other values
            if len(result) > 0:
                result.append(None)

    if not result:
        if seconds < 1.0:
            return "%.2f seconds" % seconds
        else:
            if seconds == 1:
                return "1 second"
            else:
                return "%d seconds" % seconds

    return ", ".join([x for x in result[:granularity] if x is not None])


def run_cmdline(
    cmd: list[str],
    logger: logging.Logger,
    **kwargs,
) -> int:
    """Runs a command on a environment, logs output and reports status.

    Parameters:

        cmd: The command to run, with parameters separated on a list of strings

        logger: A logger to log messages to console

        kwargs: Further kwargs to be set on the call to
            :py:class:`subprocess.Popen`.


    Returns:
    """

    logger.info("(system) %s" % " ".join(cmd))

    start = time.time()

    p = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
        **kwargs,
    )

    for line in iter(p.stdout.readline, ""):
        sys.stdout.write(line)
        sys.stdout.flush()

    if p.wait() != 0:
        raise RuntimeError(
            "command `%s' exited with error state (%d)"
            % (" ".join(cmd), p.returncode)
        )

    total = time.time() - start

    logger.info("command took %s" % human_time(total))

    return p.pid


def uniq(
    seq: list[typing.Any], idfun: typing.Callable | None = None
) -> list[typing.Any]:
    """Very fast, order preserving uniq function."""

    # order preserving
    idfun = idfun or (lambda x: x)

    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen:
            continue
        seen[marker] = 1
        result.append(item)

    return result
