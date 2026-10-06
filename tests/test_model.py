import numpy as np
import pytest
from sciqlop_vdf.model import VDFBatch, VDFError


def _arrays(nt=3, nphi=4, nth=2, ne=5):
    t = (np.arange(nt) * 1e9).astype("datetime64[ns]")
    return dict(
        time=t,
        f=np.ones((nt, nphi, nth, ne)),
        energy=np.tile(np.logspace(1, 3, ne), (nt, 1)),
        theta=np.tile(np.linspace(30, 150, nth), (nt, 1)),
        phi=np.tile(np.linspace(0, 270, nphi), (nt, 1)),
        mass_amu=1.0, charge=1, native_frame="TEST",
    )


def test_valid_batch():
    b = VDFBatch(**_arrays())
    assert len(b) == 3
    np.testing.assert_allclose(b.time_s, [0.0, 1.0, 2.0])


@pytest.mark.parametrize("key,bad", [
    ("f", np.ones((3, 4, 2))),
    ("energy", np.ones((3, 6))),
    ("theta", np.ones((2, 2))),
    ("phi", np.ones((3, 3))),
])
def test_rejects_bad_shapes(key, bad):
    a = _arrays(); a[key] = bad
    with pytest.raises(VDFError, match=key):
        VDFBatch(**a)


def test_rejects_bad_aux_shapes():
    a = _arrays()
    with pytest.raises(VDFError, match="b"):
        VDFBatch(**a, b=np.ones((3, 2)))
    with pytest.raises(VDFError, match="rotation 'GSE'"):
        VDFBatch(**a, rotations={"GSE": np.ones((3, 3))})
    with pytest.raises(VDFError, match="one_count"):
        VDFBatch(**a, one_count=np.ones((3, 4, 2, 4)))
