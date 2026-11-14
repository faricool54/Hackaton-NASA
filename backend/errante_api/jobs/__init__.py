"""Internal job engine (WS4-5/10).

Receives a normalised build request, persists it, executes the pipeline in an
isolated child process and records the structured result.  None of the internal
types are part of the public OpenAPI contract.
"""
