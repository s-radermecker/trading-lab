from __future__ import annotations

from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceType(str, Enum):
    OFFICIAL = "official"
    MARKET_DATA = "market_data"
    NEWSWIRE = "newswire"
    CALENDAR = "calendar"
    POSITIONING = "positioning"
    BROKER = "broker"
    INTERNAL_MODEL = "internal_model"


class SourceTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PillarName(str, Enum):
    MACRO = "macro"
    PRICE_ACTION = "price_action"
    SENTIMENT = "sentiment"
    RISK = "risk"
    PSYCHOLOGY = "psychology"
    PROCESS = "process"
    EXECUTION = "execution"


class TimeHorizon(str, Enum):
    INTRADAY = "intraday"
    SWING = "swing"
    WEEKLY = "weekly"
    MACRO = "macro"


class EventType(str, Enum):
    DATA_RELEASE = "data_release"
    CENTRAL_BANK = "central_bank"
    HEADLINE = "headline"
    MARKET_MOVE = "market_move"
    POSITIONING_UPDATE = "positioning_update"
    EXECUTION_CONSTRAINT = "execution_constraint"
    OTHER = "other"


class DirectionHint(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class DirectionalBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class PriorityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendedAction(str, Enum):
    LONG_BIAS = "long_bias"
    SHORT_BIAS = "short_bias"
    WAIT = "wait"
    NO_TRADE = "no_trade"
    WATCHLIST = "watchlist"


class GlobalStateLabel(str, Enum):
    ALIGNED_TRADE_READY = "aligned_trade_ready"
    ALIGNED_BUT_WAITING_EXECUTION = "aligned_but_waiting_execution"
    MIXED_CONTEXT_REDUCE_AGGRESSION = "mixed_context_reduce_aggression"
    CONTRADICTORY_NO_TRADE = "contradictory_no_trade"
    EXTREME_RISK_NO_TRADE = "extreme_risk_no_trade"


class TradePermission(str, Enum):
    YES = "yes"
    CONDITIONAL = "conditional"
    WAIT = "wait"
    NO = "no"


class StrategyStyle(str, Enum):
    CONTINUATION = "continuation"
    BREAKOUT = "breakout"
    RANGE_FADE = "range_fade"
    REVERSAL = "reversal"
    NO_TRADE = "no_trade"


class RiskPosture(str, Enum):
    AGGRESSIVE = "aggressive"
    NORMAL = "normal"
    REDUCED = "reduced"
    DEFENSIVE = "defensive"
    FLAT = "flat"


class TriggerType(str, Enum):
    FUNDAMENTAL = "fundamental"
    TECHNICAL = "technical"
    EITHER = "either"
    UNKNOWN = "unknown"


class TriggerState(str, Enum):
    ABSENT = "absent"
    WATCHING = "watching"
    DEVELOPING = "developing"
    CONFIRMED = "confirmed"


class ExecutionPermissionState(str, Enum):
    BLOCKED_NO_TRIGGER = "blocked_no_trigger"
    WATCH_TRIGGER = "watch_trigger"
    CONDITIONAL_ON_TRIGGER = "conditional_on_trigger"
    TRIGGER_CONFIRMED = "trigger_confirmed"


@dataclass
class MarketInfoObject:
    info_id: str
    pillar_target: PillarName
    source_name: str
    source_type: SourceType
    source_tier: SourceTier
    title: str
    raw_text: str
    normalized_summary: str

    timestamp_utc: str = field(default_factory=utc_now_iso)
    asset_scope: List[str] = field(default_factory=list)
    country_scope: List[str] = field(default_factory=list)
    time_horizon: TimeHorizon = TimeHorizon.INTRADAY
    event_type: EventType = EventType.OTHER
    numeric_payload: Dict[str, Any] = field(default_factory=dict)
    importance_score: int = 0
    confidence_score: int = 0
    novelty_score: int = 0
    market_relevance_score: int = 0
    direction_hint: DirectionHint = DirectionHint.UNKNOWN
    valid_from_utc: Optional[str] = None
    valid_until_utc: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    dedup_key: str = ""

    def __post_init__(self) -> None:
        self.importance_score = _clamp_score(self.importance_score)
        self.confidence_score = _clamp_score(self.confidence_score)
        self.novelty_score = _clamp_score(self.novelty_score)
        self.market_relevance_score = _clamp_score(self.market_relevance_score)

        if not self.valid_from_utc:
            self.valid_from_utc = self.timestamp_utc

        if not self.dedup_key:
            self.dedup_key = self.info_id

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class PillarThesisObject:
    thesis_id: str
    pillar_name: PillarName
    asset_scope: List[str]

    directional_bias: DirectionalBias = DirectionalBias.NEUTRAL
    conviction_score: int = 0
    uncertainty_score: int = 100
    tradable: bool = False
    state_label: str = "unclassified"

    timestamp_utc: str = field(default_factory=utc_now_iso)
    time_horizon: TimeHorizon = TimeHorizon.INTRADAY
    preferred_styles: List[StrategyStyle] = field(default_factory=list)
    forbidden_styles: List[StrategyStyle] = field(default_factory=list)
    priority_level: PriorityLevel = PriorityLevel.LOW

    thesis_summary_short: str = ""
    thesis_summary_long: str = ""
    key_drivers: List[str] = field(default_factory=list)
    supporting_info_ids: List[str] = field(default_factory=list)
    counter_arguments: List[str] = field(default_factory=list)
    main_risks: List[str] = field(default_factory=list)
    invalidation_conditions: List[str] = field(default_factory=list)

    valid_from_utc: Optional[str] = None
    valid_until_utc: Optional[str] = None
    confidence_penalty_flags: List[str] = field(default_factory=list)
    data_quality_score: int = 0
    recommended_action: RecommendedAction = RecommendedAction.WATCHLIST

    mispricing_score: int = 0
    trigger_needed: bool = True
    trigger_type_preferred: TriggerType = TriggerType.UNKNOWN
    trigger_watchlist: List[str] = field(default_factory=list)
    trigger_confirmed: bool = False
    trigger_readiness_score: int = 0

    def __post_init__(self) -> None:
        self.conviction_score = _clamp_score(self.conviction_score)
        self.uncertainty_score = _clamp_score(self.uncertainty_score)
        self.data_quality_score = _clamp_score(self.data_quality_score)
        self.mispricing_score = _clamp_score(self.mispricing_score)
        self.trigger_readiness_score = _clamp_score(self.trigger_readiness_score)

        if not self.valid_from_utc:
            self.valid_from_utc = self.timestamp_utc

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


@dataclass
class GlobalThesisObject:
    global_thesis_id: str
    asset_scope: List[str]

    state_label: GlobalStateLabel = GlobalStateLabel.CONTRADICTORY_NO_TRADE
    global_bias: DirectionalBias = DirectionalBias.NEUTRAL
    global_conviction: int = 0
    global_uncertainty: int = 100
    trade_permission: TradePermission = TradePermission.NO
    preferred_style: StrategyStyle = StrategyStyle.NO_TRADE

    timestamp_utc: str = field(default_factory=utc_now_iso)
    time_horizon: TimeHorizon = TimeHorizon.INTRADAY
    forbidden_styles: List[StrategyStyle] = field(default_factory=list)
    priority_market: str = ""
    watchlist_markets: List[str] = field(default_factory=list)

    macro_thesis_id: str = ""
    regime_thesis_id: str = ""
    sentiment_thesis_id: str = ""

    hard_veto: bool = False
    hard_veto_reason: str = ""
    soft_warnings: List[str] = field(default_factory=list)
    key_alignment_points: List[str] = field(default_factory=list)
    main_conflicts: List[str] = field(default_factory=list)

    summary_short: str = ""
    summary_long: str = ""
    risk_posture: RiskPosture = RiskPosture.FLAT
    next_step: str = "watch_only"

    global_mispricing_score: int = 0
    trigger_required: bool = True
    trigger_state: TriggerState = TriggerState.ABSENT
    preferred_trigger_type: TriggerType = TriggerType.UNKNOWN
    trigger_summary: str = ""
    execution_permission_state: ExecutionPermissionState = (
        ExecutionPermissionState.BLOCKED_NO_TRIGGER
    )

    def __post_init__(self) -> None:
        self.global_conviction = _clamp_score(self.global_conviction)
        self.global_uncertainty = _clamp_score(self.global_uncertainty)
        self.global_mispricing_score = _clamp_score(self.global_mispricing_score)

    def to_dict(self) -> Dict[str, Any]:
        return _serialize_value(asdict(self))


def _serialize_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if is_dataclass(value):
        return {k: _serialize_value(v) for k, v in asdict(value).items()}
    return value


def _clamp_score(value: int) -> int:
    return max(0, min(100, int(value)))