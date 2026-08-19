"""Environment verification tests.

Verifies that all required packages can be successfully imported.
"""

import sys

import pytest


def test_python_version():
    """Verify that Python version is at least 3.11."""
    assert sys.version_info.major == 3
    assert sys.version_info.minor >= 11


def test_imports():
    """Verify that all core project dependencies can be successfully imported."""
    try:
        import dotenv
        import folium
        import geopandas
        import joblib
        import jupyterlab
        import matplotlib
        import numpy
        import openpyxl
        import pandas
        import pyarrow
        import pyproj
        import requests
        import ruff
        import sklearn
        import shap
        import shapely
        import streamlit
        import streamlit_folium
        import xgboost

        # Simple checks to ensure packages are loaded correctly
        assert numpy.__version__ is not None
        assert pandas.__version__ is not None
        assert geopandas.__version__ is not None
        assert xgboost.__version__ is not None

    except ImportError as e:
        pytest.fail(f"Required package failed to import: {e}")
