from __future__ import annotations

from e2e.types import FromStep, StopAfter

SECTION_UPLOAD = 0
SECTION_CONFIRM = 1
SECTION_PARSE = 2
SECTION_CANDIDATES = 3
SECTION_PUBLISH = 4
SECTION_RETRIEVAL = 5

FROM_STEP_START: dict[FromStep, int] = {
    "auto": SECTION_UPLOAD,
    "upload": SECTION_UPLOAD,
    "confirm": SECTION_CONFIRM,
    "parse": SECTION_PARSE,
    "candidates": SECTION_CANDIDATES,
    "publish": SECTION_PUBLISH,
    "retrieval": SECTION_RETRIEVAL,
}

STOP_AFTER_SECTION: dict[StopAfter, int] = {
    "candidates": SECTION_CANDIDATES,
    "publish": SECTION_PUBLISH,
    "retrieval": SECTION_RETRIEVAL,
}

PIPELINE_STEP_ORDER: list[FromStep] = [
    "upload",
    "confirm",
    "parse",
    "candidates",
    "publish",
    "retrieval",
]


def start_section(from_step: FromStep) -> int:
    return FROM_STEP_START[from_step]


def stop_section(stop_after: StopAfter) -> int:
    return STOP_AFTER_SECTION[stop_after]


def includes_section(from_step: FromStep, section: int) -> bool:
    return start_section(from_step) <= section


def section_in_range(from_step: FromStep, stop_after: StopAfter, section: int) -> bool:
    return start_section(from_step) <= section <= stop_section(stop_after)


def clamp_from_step(from_step: FromStep, stop_after: StopAfter) -> FromStep:
    if from_step == "auto":
        return from_step
    if start_section(from_step) <= stop_section(stop_after):
        return from_step
    return stop_after
