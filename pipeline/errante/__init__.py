"""Errante: find what moves in NASA SPHEREx infrared images.

Sub-packages map 1:1 to workstreams (see tasks/):
  data/     WS1  archive search + downloads (IRSA TAP/SIA, S3, cutouts)
  imaging/  WS2  flags, reprojection to a common grid, PNG rendering
  detect/   WS2  source finding, difference imaging, track linking, scoring
  science/  WS3  known-object cross-match, motion/distance, spectra, Planet X
Shared (contract, change via PR): models.py, products.py, settings.py
"""

__version__ = "0.1.0"
