from packages.core.logging import setup_logger

logger = setup_logger(__name__)


# ==============================================================================
# FALLBACK PROTOCOL DEFINITIONS
# ==============================================================================
# These protocols provide fallback definitions when analysis.protocol_definitions
# is not available. They are defined at module level to ensure importability.
