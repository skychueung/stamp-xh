"""Tests for PepFlow and PepHAR adapter modules (P31C).

Instantiation requires the models to be registered in the shared registry,
which is intentionally not modified in this phase. We verify only that the
modules import cleanly and expose the expected classes.
"""

from app.services.model_adapters import pepflow_adapter, pephar_adapter


def test_pepflow_adapter_module_imports():
    assert hasattr(pepflow_adapter, "PepFlowAdapter")


def test_pephar_adapter_module_imports():
    assert hasattr(pephar_adapter, "PepHARAdapter")
