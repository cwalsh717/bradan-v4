from app.services.fred import FredClient
from app.services.twelvedata import TwelveDataClient

twelvedata_client: TwelveDataClient = None
fred_client: FredClient = None


def get_twelvedata() -> TwelveDataClient:
    return twelvedata_client


def get_fred() -> FredClient:
    return fred_client
