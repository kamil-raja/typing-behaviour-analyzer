"""Pure event replay for the Typing Behaviour Analyzer.

Responsibility: reconstruct the typed buffer from validated keyboard events and
derive the session end state (completion or timer expiry). This module contains
no HTTP calls, no database access, and no metric formulas beyond the derived
counts needed to describe the replay (K, C, E, N, U, Ec, Eu).

Reference: ``docs/EVENT_SCHEMA.md`` §4 and ``TBA_BLUEPRINT_v3_FINAL.md`` §7.1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

INVALID_EVENT_SEQUENCE = "INVALID_EVENT_SEQUENCE"
END_COMPLETED = "completed"
END_TIME_UP = "time_up"

PRINTABLE = "printable"
BACKSPACE = "backspace"


class InvalidEventSequence(ValueError):
    """Raised when the event stream violates the replay contract.

    The API layer maps this to ``INVALID_EVENT_SEQUENCE`` (422).
    """

    code = INVALID_EVENT_SEQUENCE


@dataclass
class _PendingKey:
    """An unmatched non-repeat keydown, keyed by ``event.code``."""

    t_down: float
    is_backspace: bool


@dataclass
class Keystroke:
    """An accepted printable keystroke and its buffer position."""

    seq: int
    position: int
    t: float
    code: str
    typed: str
    expected: str
    correct: bool
    deleted: bool = False


@dataclass(frozen=True)
class DwellSample:
    """A paired non-repeat keydown/keyup, including Backspace."""

    code: str
    t_down: float
    t_up: float
    is_backspace: bool

    @property
    def dwell_ms(self) -> float:
        """Dwell duration measured from the original keydown."""
        return self.t_up - self.t_down


@dataclass(frozen=True)
class TimedAction:
    """A non-repeat action that participates in the interval list.

    Printable keystrokes are timed actions. A Backspace is a timed action only
    when its non-repeat down actually deleted a character. Repeat downs never
    appear here.
    """

    seq: int
    t: float
    kind: str
    code: str
    expected: str | None = None
    typed: str | None = None
    correct: bool | None = None


@dataclass
class ReplayResult:
    """The complete replay state needed by the metric layer."""

    text: str
    mode: str
    duration_limit_ms: float | None
    end_reason: str | None
    active_duration_ms: float
    keystrokes: list[Keystroke]
    typed_final: str
    backspace_deletions: int
    backspace_presses: int
    dwell_samples: list[DwellSample]
    timed_actions: list[TimedAction]
    dropped_after_end: int
    orphan_up: int
    missing_up: int
    open_at_end: int
    discarded_repeat_keydowns: int

    @property
    def K(self) -> int:
        """Total accepted printable keystrokes."""
        return len(self.keystrokes)

    @property
    def C(self) -> int:
        """Correct accepted printable keystrokes."""
        return sum(1 for keystroke in self.keystrokes if keystroke.correct)

    @property
    def E(self) -> int:
        """Incorrect accepted printable keystrokes: ``K - C``."""
        return self.K - self.C

    @property
    def N(self) -> int:
        """Length of the final buffer."""
        return len(self.typed_final)

    @property
    def U(self) -> int:
        """Uncorrected errors still present in the final buffer."""
        return sum(
            1
            for position, typed in enumerate(self.typed_final)
            if typed != self.text[position]
        )

    def _position_fixed(self, position: int) -> bool:
        """Return whether the final buffer holds the correct char at ``position``."""
        return (
            position < self.N
            and self.typed_final[position] == self.text[position]
        )

    @property
    def Ec(self) -> int:
        """Deleted incorrect keystrokes whose position was finally corrected."""
        return sum(
            1
            for keystroke in self.keystrokes
            if keystroke.deleted
            and not keystroke.correct
            and self._position_fixed(keystroke.position)
        )

    @property
    def Eu(self) -> int:
        """Deleted incorrect keystrokes whose position is empty or still wrong."""
        return sum(
            1
            for keystroke in self.keystrokes
            if keystroke.deleted
            and not keystroke.correct
            and not self._position_fixed(keystroke.position)
        )

    @property
    def is_complete(self) -> bool:
        """Whether the replay reached exact completion."""
        return self.end_reason == END_COMPLETED


def replay_events(
    text: str,
    mode: str,
    duration_limit_ms: float | None,
    events: Sequence[Mapping[str, Any]],
) -> ReplayResult:
    """Replay validated events against ``text`` and derive the session end.

    ``mode`` is ``"time"`` or ``"passage"``. Time mode requires a duration
    limit; passage mode requires ``None``. Events are assumed to have passed
    schema and sequence validation. The replay still enforces the two
    sequence-level rules that belong to it:

    * a printable down at a full buffer raises :class:`InvalidEventSequence`;
    * a Backspace repeat without a pending original raises the same error.

    A passage run that never completes returns ``end_reason=None``. The caller
    applies the ``INCOMPLETE_SESSION`` outcome check, per the documented server
    processing order.
    """
    if mode not in {"time", "passage"}:
        raise ValueError(f"unsupported mode: {mode!r}")
    if mode == "time" and duration_limit_ms is None:
        raise ValueError("time mode requires duration_limit_ms")
    if mode == "passage" and duration_limit_ms is not None:
        raise ValueError("passage mode must not have duration_limit_ms")

    buffer: list[Keystroke] = []
    keystrokes: list[Keystroke] = []
    pending: dict[str, _PendingKey] = {}
    timed_actions: list[TimedAction] = []
    dwell_samples: list[DwellSample] = []

    end_reason: str | None = None
    active_duration_ms = 0.0
    last_t = 0.0
    dropped_after_end = 0
    orphan_up = 0
    missing_up = 0
    backspace_deletions = 0
    backspace_presses = 0
    discarded_repeat_keydowns = 0

    for event in events:
        seq = int(event["seq"])
        t = float(event["t"])
        last_t = t

        if end_reason is not None:
            dropped_after_end += 1
            continue

        # Timer expiry wins at the exact boundary. The boundary event itself is
        # excluded, as are all later events.
        if (
            mode == "time"
            and duration_limit_ms is not None
            and t >= duration_limit_ms
        ):
            end_reason = END_TIME_UP
            active_duration_ms = float(duration_limit_ms)
            dropped_after_end += 1
            continue

        event_type = event["type"]
        code = str(event["code"])
        key = event["key"]
        repeat = bool(event["repeat"])

        if event_type == "up":
            entry = pending.pop(code, None)
            if entry is None:
                orphan_up += 1
                continue
            dwell_samples.append(
                DwellSample(
                    code=code,
                    t_down=entry.t_down,
                    t_up=t,
                    is_backspace=entry.is_backspace,
                )
            )
            continue

        if repeat:
            if key == "Backspace":
                if code not in pending:
                    raise InvalidEventSequence(
                        f"Backspace repeat at seq {seq} has no pending original"
                    )
                # Repeats delete but never read, write, or overwrite pending.
                if buffer:
                    buffer.pop().deleted = True
                    backspace_deletions += 1
                continue

            # A repeat printable is never a keystroke. Validators reject it in a
            # submitted payload; replay discards it defensively.
            discarded_repeat_keydowns += 1
            continue

        if key == "Backspace":
            if code in pending:
                missing_up += 1
            pending[code] = _PendingKey(t_down=t, is_backspace=True)
            backspace_presses += 1
            if buffer:
                buffer.pop().deleted = True
                backspace_deletions += 1
                timed_actions.append(
                    TimedAction(seq=seq, t=t, kind=BACKSPACE, code=code)
                )
            continue

        # Accepted printable non-repeat down.
        if len(buffer) >= len(text):
            raise InvalidEventSequence(
                f"printable keydown at seq {seq} when the buffer is full"
            )
        if code in pending:
            missing_up += 1
        pending[code] = _PendingKey(t_down=t, is_backspace=False)

        position = len(buffer)
        expected = text[position]
        typed = str(key)
        correct = typed == expected
        keystroke = Keystroke(
            seq=seq,
            position=position,
            t=t,
            code=code,
            typed=typed,
            expected=expected,
            correct=correct,
        )
        buffer.append(keystroke)
        keystrokes.append(keystroke)
        timed_actions.append(
            TimedAction(
                seq=seq,
                t=t,
                kind=PRINTABLE,
                code=code,
                expected=expected,
                typed=typed,
                correct=correct,
            )
        )

        if len(buffer) == len(text) and all(
            slot.typed == text[index] for index, slot in enumerate(buffer)
        ):
            end_reason = END_COMPLETED
            active_duration_ms = t

    if end_reason is None:
        if mode == "time":
            assert duration_limit_ms is not None
            end_reason = END_TIME_UP
            active_duration_ms = float(duration_limit_ms)
        else:
            # Passage mode did not complete. T is not a defined result for a
            # rejected session; retain the last event timestamp for diagnostics.
            active_duration_ms = last_t

    return ReplayResult(
        text=text,
        mode=mode,
        duration_limit_ms=duration_limit_ms,
        end_reason=end_reason,
        active_duration_ms=active_duration_ms,
        keystrokes=keystrokes,
        typed_final="".join(slot.typed for slot in buffer),
        backspace_deletions=backspace_deletions,
        backspace_presses=backspace_presses,
        dwell_samples=dwell_samples,
        timed_actions=timed_actions,
        dropped_after_end=dropped_after_end,
        orphan_up=orphan_up,
        missing_up=missing_up,
        open_at_end=len(pending),
        discarded_repeat_keydowns=discarded_repeat_keydowns,
    )
