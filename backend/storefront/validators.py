"""
Upload checks shared by every model that accepts files.

Uploaded files are served from the website's own address, so an .html or scripted .svg
slipping in would run with the site's privileges. Every file field therefore has an
extension allow-list and a size limit (and nginx adds a sandbox header on /media/).
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible


@deconstructible
class MaxFileSize:
    def __init__(self, mb):
        self.mb = mb

    def __call__(self, f):
        size = getattr(f, "size", 0) or 0
        if size > self.mb * 1024 * 1024:
            raise ValidationError(f"This file is {size / 1048576:.1f} MB. The limit is {self.mb} MB — please compress it.")

    def __eq__(self, other):
        return isinstance(other, MaxFileSize) and other.mb == self.mb


@deconstructible
class GlbHeader:
    """A real binary glTF 2.0 file starts with the bytes 'glTF' followed by version 2."""

    def __call__(self, f):
        handle = getattr(f, "file", f)
        try:
            pos = handle.tell()
            handle.seek(0)
            head = handle.read(12)
            handle.seek(pos)
        except (AttributeError, OSError, ValueError):
            raise ValidationError("Could not read this 3D file.")
        if len(head) < 12 or head[:4] != b"glTF" or int.from_bytes(head[4:8], "little") != 2:
            raise ValidationError("This is not a valid .glb (binary glTF 2.0) file. Export your model as .glb.")

    def __eq__(self, other):
        return isinstance(other, GlbHeader)


VIDEO = [FileExtensionValidator(["mp4", "webm"]), MaxFileSize(10)]
LOGO = [FileExtensionValidator(["png", "webp", "jpg", "jpeg", "svg"]), MaxFileSize(2)]
FAVICON = [FileExtensionValidator(["png", "ico", "svg", "webp"]), MaxFileSize(1)]
IMAGE = [MaxFileSize(15)]  # ImageField already checks it is a real picture
MODEL_3D = [FileExtensionValidator(["glb"]), MaxFileSize(getattr(settings, "MAX_3D_MODEL_MB", 20)), GlbHeader()]
RECEIPT = [FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "webp"]), MaxFileSize(5)]


def run(validators, f):
    """Apply a validator list outside of a form (API uploads). Raises ValidationError."""
    for v in validators:
        v(f)
