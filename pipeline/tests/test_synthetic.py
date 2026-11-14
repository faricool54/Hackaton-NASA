from errante.products import ProductStore
from errante.synthetic import DEMO_FIELDS, build_demo


def test_build_demo_writes_valid_products(tmp_path):
    build_demo(tmp_path)
    store = ProductStore(tmp_path)
    manifest = store.read_manifest()
    assert manifest.synthetic is True
    assert {f.id for f in manifest.fields} == {s.id for s in DEMO_FIELDS}
    for fs in manifest.fields:
        field = store.read_field(fs.id)
        assert field.provenance.synthetic
        assert all((store.field_dir(fs.id) / fr.image).exists() for fr in field.frames)
        cands = store.read_candidates(fs.id).candidates
        assert cands, "every demo field should have at least one candidate"
        frame_ids = {fr.id for fr in field.frames}
        for c in cands:
            assert {d.frame_id for d in c.detections} <= frame_ids
            for d in c.detections:
                assert 0 <= d.x < field.grid.width_px and 0 <= d.y < field.grid.height_px


def test_demo_asteroid_rate_is_physical(tmp_path):
    build_demo(tmp_path)
    cands = {c.id: c for c in ProductStore(tmp_path).read_candidates("demo-ecliptic").candidates}
    ast = cands["SYN-AST-1"]
    # 4.1 px/h * 6.15"/px ≈ 25"/h  -> main belt (~2-3.5 AU)
    assert 20 < ast.motion.rate_arcsec_per_hour < 30
    assert 1.5 < ast.distance.au_median < 4
    assert cands["SYN-ART-1"].status == "artifact"
