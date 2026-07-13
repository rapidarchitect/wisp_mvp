"""Root pytest configuration and fixtures."""

import aiosqlite

# Make shared pytest-bdd step definitions available to all BDD test modules.
pytest_plugins = ["tests.steps.common_steps"]

# Workaround for aiosqlite issue where background threads can prevent pytest
# from exiting after async tests. Making the threads daemon lets the process
# exit even if a connection cleanup races with pytest's event loop teardown.
_original_start = aiosqlite.Connection.start


def _daemon_start(self) -> None:
    self.daemon = True
    return _original_start(self)


aiosqlite.Connection.start = _daemon_start
