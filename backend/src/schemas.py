from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NaiveDatetime, StringConstraints, model_validator

from .models import Action, DelayClass

Code = Annotated[str, StringConstraints(pattern=r'^[A-Z0-9][A-Z0-9-]{1,31}$')]
Name = Annotated[str, StringConstraints(min_length=2, max_length=80)]
Note = Annotated[str, StringConstraints(min_length=5, max_length=300)]


class Payload(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class Login(Payload):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class TideInput(Payload):
    code: Code
    berth_code: Code
    starts_at: NaiveDatetime
    ends_at: NaiveDatetime
    max_draft_m: float = Field(gt=0, le=25)
    bulletin: str = Field(min_length=3, max_length=120)

    @model_validator(mode='after')
    def chronological(self):
        if self.starts_at >= self.ends_at:
            raise ValueError('潮窗结束需晚于开始')
        return self


class Schedule(Payload):
    window_code: Code
    eta: NaiveDatetime
    maneuver_minutes: int = Field(ge=15, le=180)


class RequestInput(Schedule):
    code: Code
    vessel: Name
    berth_code: Code
    draft_m: float = Field(gt=0, le=25)


class AssignTug(Payload):
    tug_code: Code


class IncidentInput(Payload):
    code: Code
    request_code: Code
    radio_reference: str = Field(min_length=3, max_length=64)
    observed_at: NaiveDatetime
    wind_kn: float = Field(ge=0, le=65)
    tug_wait_min: int = Field(ge=0, le=180)
    event_note: Note


class MarginDecision(Payload):
    decision: DelayClass
    reason: Note


class DispatchInput(Payload):
    action: Action
    instruction: Note


class CloseInput(Payload):
    all_fast_at: NaiveDatetime
    outcome: Note
