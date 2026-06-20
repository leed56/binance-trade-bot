from .live import LiveExecutor
from .paper import PaperExecutor


def get_executor(config, web3_client, wallet, pancake, database, logger):
    if config.is_live:
        return LiveExecutor(config, web3_client, wallet, pancake, database, logger)
    return PaperExecutor(config, web3_client, pancake, database, logger)


__all__ = ["PaperExecutor", "LiveExecutor", "get_executor"]
