__version__ = "0.0.1"

# Developer entry points are re-exported lazily so that a bare ``import mith_ntfy``
# (e.g. bench reading __version__) stays cheap and free of import-time side
# effects, while ``from mith_ntfy import notify`` still works.
_LAZY_EXPORTS = {"notify", "send_notification", "publish"}

__all__ = ["notify", "publish", "send_notification"]


def __getattr__(name):
	if name in _LAZY_EXPORTS:
		from mith_ntfy import api

		return getattr(api, name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
