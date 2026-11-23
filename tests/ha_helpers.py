"""Share test helpers across the supported legacy and official HA test packages."""

from importlib import import_module
from importlib.util import find_spec

# Each CI environment installs exactly one package. Do not hide import failures
# inside an installed package by falling back to a different set of fixtures.
_package = (
    "pytest_homeassistant"
    if find_spec("pytest_homeassistant") is not None
    else "pytest_homeassistant_custom_component"
)
MockConfigEntry = import_module(f"{_package}.common").MockConfigEntry
