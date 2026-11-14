"""3D system models (WS7): the objects we track, as explorable 3D systems.

- ``catalog``: curated system definitions (hand-typed for now, every value
  flagged ``verified=False`` until checked against a catalog).
- ``sources``: fetchers for real parameters (NASA Exoplanet Archive, JPL SBDB,
  SIMBAD/Gaia) — stubs with TODO(WS7).
- ``build``: writes ``<root>/systems/<id>.json`` products.

See docs/VISION_3D.md and tasks/WS7-3d-systems.md.
"""
