"""WS2 — detection: find sources, subtract the static sky, link movers, score.

Pipeline per field (see docs/ARCHITECTURE.md):
  frames on common grid -> sources.find_sources (per frame)
  -> difference.static_sky + difference.residuals (remove stars)
  -> linking.link_tracks (sources consistent with linear motion)
  -> scoring.score_tracks (confidence + vetting -> Candidate)
  -> inject.* (plant fake movers to measure what we can and cannot find)
"""
