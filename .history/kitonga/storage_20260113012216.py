"""
Custom storage backend for WhiteNoise that handles missing source map files.
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    A static files storage that ignores missing source map files (.map).

    Some third-party CSS/JS files reference source maps that don't exist.
    This storage class gracefully handles those missing files instead of
    raising an error during collectstatic.
    """

    # Patterns to ignore when they're missing
    manifest_strict = False

    def post_process(self, paths, dry_run=False, **options):
        """
        Post-process files and handle missing file errors gracefully.
        """
        for original_name, processed in super().post_process(paths, dry_run, **options):
            # If there's an error and it's about a .map file, skip it
            if isinstance(processed, Exception):
                if (
                    ".map" in str(processed)
                    or "MissingFileError" in type(processed).__name__
                ):
                    # Log and skip missing source map files
                    print(f"⚠️  Skipping missing file: {original_name}")
                    yield original_name, original_name, True
                    continue
            yield original_name, (
                processed[0] if isinstance(processed, tuple) else processed
            ), (True if isinstance(processed, tuple) else processed)


class IgnoreMissingStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Alternative: Simply ignore all missing file errors.
    """

    manifest_strict = False

    def hashed_name(self, name, content=None, filename=None):
        try:
            return super().hashed_name(name, content, filename)
        except ValueError:
            # Return the original name if hashing fails
            return name
