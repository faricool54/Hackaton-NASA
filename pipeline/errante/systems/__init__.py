"""3D system models (WS7): the challenge targets as explorable 3D systems.

- ``catalog``: the literature layer of each system (published values, each Fact
  with its source; checked in WS7-2). What no source gives stays ``None``.
- ``measured``: the measurement layer. Reads ``targets.toml`` and the frozen
  WS3 object-context snapshots in ``inputs/objects/`` (JSON only, no network,
  no WS3 code at build time), attaches the "seen by SPHEREx" facts and the
  catalog cross-checks, and explains every value left unknown.
- ``record``: dev-only. Re-records a snapshot by replaying the WS3 fixtures
  (or live archives) through ``errante.science.context``.
- ``sources``: archive fetchers used by the ``network`` tests.
- ``build``: writes ``<root>/systems/<id>.json`` products.

See docs/VISION_3D.md and tasks/WS7-3d-systems.md.
"""
