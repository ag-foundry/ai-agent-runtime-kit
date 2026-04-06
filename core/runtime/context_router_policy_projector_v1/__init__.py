"""Context router / policy / projector / trace runtime v1."""

from .runtime import build_context_packet, rewrite_text_with_projection

__all__ = ["build_context_packet", "rewrite_text_with_projection"]
