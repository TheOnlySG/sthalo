"""Scaffold smoke tests. Feature tests start in later slices."""

from fastapi import FastAPI

from app import __version__
from app.core.config import Environment
from app.main import create_app


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_app_factory_boots() -> None:
    application = create_app()
    assert isinstance(application, FastAPI)
    assert application.title == "Sthalo API"
    assert application.state.settings.env is Environment.TEST
