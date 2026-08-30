"""Minimal metadata backend; the teaching project runs directly from its source tree."""


def _not_packaged(*args, **kwargs):
    raise RuntimeError("This generated teaching project is intended to run from its source tree.")


build_wheel = _not_packaged
build_sdist = _not_packaged
prepare_metadata_for_build_wheel = _not_packaged
