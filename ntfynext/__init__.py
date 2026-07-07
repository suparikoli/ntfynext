__version__ = "0.0.1"

# Developer entry points are re-exported lazily so that a bare ``import ntfynext``
# (e.g. bench reading __version__) stays cheap and free of import-time side
# effects, while ``from ntfynext import notify`` still works.
_LAZY_EXPORTS = {"notify", "send_notification", "publish"}

__all__ = ["notify", "publish", "send_notification"]


def __getattr__(name):
	if name in _LAZY_EXPORTS:
		from ntfynext import api

		return getattr(api, name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
