"""Strategies package for CHUOT selective delegation benchmark."""
from benchmarks.selective_delegation.strategies.local_only import LocalOnlyStrategy
from benchmarks.selective_delegation.strategies.local_retry import LocalRetryStrategy
from benchmarks.selective_delegation.strategies.verified_repair import VerifiedRepairStrategy
from benchmarks.selective_delegation.strategies.always_cloud import AlwaysCloudStrategy
from benchmarks.selective_delegation.strategies.static_escalation import StaticEscalationStrategy
from benchmarks.selective_delegation.strategies.selective import SelectiveStrategy, SelectiveDelegationPolicy
from benchmarks.selective_delegation.strategies.frugalgpt import FrugalGPTStrategy
from benchmarks.selective_delegation.strategies.automix import AutoMixStrategy
from benchmarks.selective_delegation.strategies.peer_review import LocalPeerReviewStrategy

__all__ = [
    "LocalOnlyStrategy",
    "LocalRetryStrategy",
    "VerifiedRepairStrategy",
    "AlwaysCloudStrategy",
    "StaticEscalationStrategy",
    "SelectiveStrategy",
    "SelectiveDelegationPolicy",
    "FrugalGPTStrategy",
    "AutoMixStrategy",
    "LocalPeerReviewStrategy",
]
