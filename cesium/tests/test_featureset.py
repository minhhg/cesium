import os
from os.path import join as pjoin
import numpy as np
import numpy.testing as npt
import scipy.stats
import xarray as xr
from cesium.featureset import Featureset


DATA_PATH = pjoin(os.path.dirname(__file__), "data")


def test_repr():
    """Testing Featureset printing."""
    fset = Featureset(xr.open_dataset(pjoin(DATA_PATH, "test_featureset.nc")))
    repr(fset)


def test_impute():
    """Test imputation of missing Featureset values."""
    fset = Featureset(xr.open_dataset(pjoin(DATA_PATH, "test_featureset.nc")))
    fset.amplitude.values[0] = np.inf
    fset.amplitude.values[1] = np.nan
    values = fset.amplitude.values[2:]

    imputed = fset.impute(strategy='constant', value=-1e4)
    npt.assert_allclose(-1e4, imputed.amplitude.values[0:2])

    imputed = fset.impute(strategy='mean')
    npt.assert_allclose(np.mean(values), imputed.amplitude.values[0:2])

    imputed = fset.impute(strategy='median')
    npt.assert_allclose(np.median(values), imputed.amplitude.values[0:2])

    imputed = fset.impute(strategy='most_frequent')
    npt.assert_allclose(scipy.stats.mode(values).mode[0, 0], imputed.amplitude.values[0:2])


def test_indexing():
    """Test indexing overloading (__getattr__)."""
    fset = Featureset(xr.open_dataset(pjoin(DATA_PATH, "test_featureset.nc")))
    assert all(fset[0] == fset.isel(name=0))
    assert all(fset[0:2] == fset.isel(name=[0, 1]))
    assert all(fset['a'] == fset.sel(name='a'))
    assert all(fset[['a', 'b']] == fset.sel(name=['a', 'b']))
    assert all(fset['amplitude'] == fset._construct_dataarray('amplitude'))
