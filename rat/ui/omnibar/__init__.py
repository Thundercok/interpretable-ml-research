"""
rat.ui.omnibar — Unified Casual Surface (Omnibar).
Package entry point providing backwards compatibility for all imports and mock patches.
"""

from __future__ import annotations

import sys
import types

from .workers import SearchWorker, StreamReasoningWorker
from .event_filters import (
    OmnibarInputFilter,
    OmnibarListFilter,
    handle_item_reveal_or_terminal,
    handle_omnibar_escape,
)
from .companion import (
    ArtisticSpeechBubble,
    CompanionAvatarButton,
    ConversationRibbon,
    PeekingRatMascot,
    RatCompanionStage,
    ResetConfirmationDialog,
)
from .window import (
    ChatPresentationState,
    FILTER_CATEGORIES,
    OmnibarWindow,
    SECTION_TABS,
    configure_macos_fullscreen_overlay,
    lower_overlay_geometry,
)
from . import window as _win


class _OmnibarModule(types.ModuleType):
    """Module proxy that transparently forwards attribute updates (e.g. mock.patch) to window."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if hasattr(_win, name):
            setattr(_win, name, value)

    def __delattr__(self, name: str) -> None:
        super().__delattr__(name)
        if hasattr(_win, name):
            delattr(_win, name)


_mod = sys.modules[__name__]
_mod.__class__ = _OmnibarModule

# Populate all exported names from window into the package namespace
for _k, _v in vars(_win).items():
    if not _k.startswith("__"):
        super(_OmnibarModule, _mod).__setattr__(_k, _v)

# Explicitly ensure extracted worker and filter classes are bound
super(_OmnibarModule, _mod).__setattr__("SearchWorker", SearchWorker)
super(_OmnibarModule, _mod).__setattr__("StreamReasoningWorker", StreamReasoningWorker)
super(_OmnibarModule, _mod).__setattr__("OmnibarInputFilter", OmnibarInputFilter)
super(_OmnibarModule, _mod).__setattr__("OmnibarListFilter", OmnibarListFilter)

__all__ = [
    "OmnibarWindow",
    "SearchWorker",
    "StreamReasoningWorker",
    "OmnibarInputFilter",
    "OmnibarListFilter",
    "ArtisticSpeechBubble",
    "CompanionAvatarButton",
    "ResetConfirmationDialog",
    "ConversationRibbon",
    "PeekingRatMascot",
    "RatCompanionStage",
    "ChatPresentationState",
    "lower_overlay_geometry",
    "configure_macos_fullscreen_overlay",
    "SECTION_TABS",
    "FILTER_CATEGORIES",
    "handle_omnibar_escape",
    "handle_item_reveal_or_terminal",
]
