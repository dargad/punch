from importlib.metadata import version, PackageNotFoundError

# IMPORTANT: this must be the *distribution* name from pyproject.toml -> [tool.poetry].name
_DISTRIBUTION = "punch"

try:
    __version__ = version(_DISTRIBUTION)
except PackageNotFoundError:
    # e.g. running from a Git checkout without installing
    __version__ = "0+unknown"