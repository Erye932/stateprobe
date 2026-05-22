"""Entry point for ``python -m stateprobe``.

Forwards to the standard CLI defined by ``[project.scripts] stateprobe`` so
users who don't have the ``stateprobe`` script on PATH (e.g. ``pip install
--user`` without PATH set, or running directly from a checkout) can still
invoke the CLI in the conventional way.
"""

from stateprobe.cli import main


if __name__ == "__main__":
    main()
