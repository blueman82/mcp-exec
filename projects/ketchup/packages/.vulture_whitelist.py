# Vulture whitelist: Suppress false positives for required but unused symbols
# See: https://github.com/jendrikseipp/vulture#whitelists


# --- core/async_client.py ---
def exc_type():
    pass  # required for __aexit__ signature


def exc_val():
    pass  # required for __aexit__ signature


def exc_tb():
    pass  # required for __aexit__ signature


# --- core/cleanup_utils.py ---
def cleanup_resources():
    pass  # used in resource cleanup routines


# --- core/di_container.py ---
async def get_container():
    pass  # used in lambda_function.py


async def cleanup_container():
    pass  # used in lambda_function.py


# --- slack/command_processing/command_parameters/models.py ---
class ListCommandParams:
    channels_to_list = "all"  # used in production and tests
