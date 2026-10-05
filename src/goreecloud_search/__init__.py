"""GoreeCloud Search core package."""

from .execution import (
    ExecutionPolicy,
    ExecutionReport,
    ProviderAttempt,
    ProviderExecutionError,
    ProviderExecutionStatus,
    SearchAvailability,
    SearchExecutor,
)
from .index_contract import (
    INDEX_CONTRACT_VERSION,
    IndexCapabilities,
    IndexContractError,
    IndexDocumentCandidate,
    IndexSearchRequest,
    IndexSearchResponse,
)
from .index_provider import GoreeCloudIndexProvider, IndexTransport
from .index_http_api import (
    AuthenticatedRequester,
    IndexHTTPBoundaryError,
    PrivacyCapabilityVerification,
    PrivacyCapabilityVerificationRequest,
    PrivacyCapabilityVerifier,
    RequesterIdentityVerifier,
    SearchIndexHTTPServer,
    capability_record,
    create_index_http_server,
)
from .models import ParsedQuery, ProviderDescriptor, ProviderOrigin, QueryDisclosureBudget, QueryFilters, SearchCategory, SourceMode, SourcePlan, SourcePlanStep
from .normalization import NormalizedResult, ResultNormalizationError, ResultProvenance, canonicalize_url, normalize_and_deduplicate
from .planner import (
    INDEX_ORIGINATED_DELEGATION_CONTRACT_VERSION,
    INDEX_ORIGINATED_DELEGATION_MODE,
    INDEX_ORIGINATED_FALLBACK_ALLOWED,
    INDEX_ORIGINATED_INDEX_PROVIDER_REENTRY_ALLOWED,
    SourcePlanningError,
    plan_index_originated_delegation,
    plan_sources,
)
from .providers import ProviderSearchBatch, ResultCandidate, SearchProvider
from .query_parser import QueryParseError, parse_query
from .ranking import RankedResult, RankingSignal, rank_results
from .service import SearchCore, SearchResponse
from .snippets import (
    DEFAULT_SNIPPET_MAX_CHARS,
    MAX_SNIPPET_SOURCE_CHARS,
    GeneratedSnippet,
    SnippetGenerationError,
    generate_snippet,
)
from .version import __version__

__all__ = [
    "__version__", "INDEX_CONTRACT_VERSION", "ParsedQuery", "ProviderDescriptor",
    "ProviderOrigin", "QueryDisclosureBudget", "QueryFilters", "SearchCategory",
    "SourceMode", "SourcePlan", "SourcePlanStep", "QueryParseError",
    "SourcePlanningError", "IndexContractError", "ResultNormalizationError",
    "ProviderExecutionError", "IndexCapabilities", "IndexDocumentCandidate",
    "IndexSearchRequest", "IndexSearchResponse", "GoreeCloudIndexProvider",
    "IndexTransport", "ResultCandidate", "ProviderSearchBatch", "SearchProvider",
    "ResultProvenance", "NormalizedResult", "canonicalize_url",
    "normalize_and_deduplicate", "RankingSignal", "RankedResult", "rank_results",
    "ExecutionPolicy", "ProviderExecutionStatus", "ProviderAttempt", "ExecutionReport",
    "SearchAvailability", "SearchExecutor", "SearchResponse",
    "DEFAULT_SNIPPET_MAX_CHARS", "MAX_SNIPPET_SOURCE_CHARS", "GeneratedSnippet",
    "SnippetGenerationError", "generate_snippet", "parse_query",
    "plan_sources", "plan_index_originated_delegation",
    "INDEX_ORIGINATED_DELEGATION_CONTRACT_VERSION",
    "INDEX_ORIGINATED_DELEGATION_MODE",
    "INDEX_ORIGINATED_INDEX_PROVIDER_REENTRY_ALLOWED",
    "INDEX_ORIGINATED_FALLBACK_ALLOWED",
    "SearchCore", "AuthenticatedRequester", "IndexHTTPBoundaryError",
    "PrivacyCapabilityVerification", "PrivacyCapabilityVerificationRequest",
    "PrivacyCapabilityVerifier", "RequesterIdentityVerifier", "SearchIndexHTTPServer",
    "capability_record", "create_index_http_server",
]
