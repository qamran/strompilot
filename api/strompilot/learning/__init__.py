"""Learning loop: feedback shifts future plans through prefs."""

from .apply import apply_learned_windows
from .models import Feedback, LearningError
from .update import LEARNED_KEY, update_from_feedback

__all__ = [
    "LEARNED_KEY",
    "Feedback",
    "LearningError",
    "apply_learned_windows",
    "update_from_feedback",
]
