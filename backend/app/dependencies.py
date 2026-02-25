from app.services.fred import FredClient
from app.services.fred_scheduler import FredScheduler
from app.services.twelvedata import TwelveDataClient
from app.services.ws_manager import TwelveDataWSManager

twelvedata_client: TwelveDataClient = None
fred_client: FredClient = None
ws_manager: TwelveDataWSManager = None
fred_scheduler: FredScheduler = None


def get_twelvedata() -> TwelveDataClient:
    return twelvedata_client


def get_fred() -> FredClient:
    return fred_client


def get_ws_manager() -> TwelveDataWSManager:
    return ws_manager


def get_fred_scheduler() -> FredScheduler:
    return fred_scheduler
