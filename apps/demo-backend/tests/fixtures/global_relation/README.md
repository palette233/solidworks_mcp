# Global relation test fixtures

These JSON files are immutable test fixtures extracted from the validated
Project02 global relation catalog and context snapshots.

They are stored under `tests/fixtures` deliberately: regression tests must not
depend on ignored runtime files under `demo/`. When the catalog schema changes,
regenerate and review these fixtures together with the tests that consume them.
