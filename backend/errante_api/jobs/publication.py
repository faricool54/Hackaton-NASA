"""Job publication adapter over the shared, process-locked publisher."""

from pathlib import Path

from ..publication import file_hash, publish_field, validate_product  # noqa: F401 (compatibility exports)
from .errors import PublicationError


def publish_job(*, staging_dir: Path, field_id: str, products_dir: Path, repo, job_id: str) -> str:
    def prepared(fingerprint):
        repo.record_publication_hashes(job_id, fingerprint)

    try:
        return publish_field(staging_dir / "products", field_id, products_dir, prepared=prepared)
    except Exception as error:
        raise PublicationError(f"Product validation/publication failed: {error}") from error
