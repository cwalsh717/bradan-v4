"""Twelve Data WebSocket manager.

Maintains a single persistent websocket connection to Twelve Data and fans
out live price updates to in-memory storage.  Frontend-facing websocket
endpoints read from the in-memory price dict — they never talk to Twelve
Data directly.
"""

import asyncio
import json
import logging
import time
from typing import Optional

import websockets

logger = logging.getLogger(__name__)

WS_BASE_URL = "wss://ws.twelvedata.com/v1/quotes/price"

# Reconnection backoff parameters
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 60.0
BACKOFF_FACTOR = 2.0

# Cleanup parameters
CLEANUP_INTERVAL_S = 30.0
PROFILE_SYMBOL_TTL_S = 60.0


class TwelveDataWSManager:
    """Manages a single upstream websocket connection to Twelve Data and
    tracks live prices in memory.

    Two categories of subscriptions:
      - **dashboard_symbols**: persistent; survive cleanup.
      - **profile_symbols**: dynamic; cleaned up when idle > 60 s.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._ws = None
        self._reader_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        # Subscription tracking
        self.dashboard_symbols: set[str] = set()
        self.profile_symbols: dict[str, float] = {}  # symbol → last_active monotonic ts

        # Latest price per symbol
        self.prices: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the upstream websocket connection and background tasks."""
        if self._running:
            logger.warning("WSManager already running — ignoring start()")
            return
        self._running = True
        self._reader_task = asyncio.create_task(self._connection_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("TwelveDataWSManager started")

    async def stop(self) -> None:
        """Gracefully shut down the connection and background tasks."""
        self._running = False

        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        if self._ws is not None:
            await self._ws.close()
            self._ws = None

        logger.info("TwelveDataWSManager stopped")

    # ------------------------------------------------------------------
    # Connection loop with exponential backoff
    # ------------------------------------------------------------------

    async def _connection_loop(self) -> None:
        """Maintain a persistent upstream websocket connection, reconnecting
        with exponential backoff on failure."""
        backoff = INITIAL_BACKOFF_S
        url = f"{WS_BASE_URL}?apikey={self._api_key}"

        while self._running:
            try:
                async with websockets.connect(url) as ws:
                    self._ws = ws
                    backoff = INITIAL_BACKOFF_S  # reset on successful connect
                    logger.info("Connected to Twelve Data WebSocket")

                    # Re-subscribe to all active symbols after reconnect
                    await self._resubscribe_all()

                    await self._read_messages(ws)

            except asyncio.CancelledError:
                raise
            except Exception:
                self._ws = None
                if not self._running:
                    break
                logger.exception(
                    "Twelve Data WS disconnected — reconnecting in %.1fs",
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * BACKOFF_FACTOR, MAX_BACKOFF_S)

    async def _read_messages(self, ws) -> None:
        """Read messages from the upstream websocket until it closes."""
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Malformed WS message: %s", raw)
                continue

            event = msg.get("event")

            if event == "price":
                self._handle_price(msg)
            elif event == "subscribe-status":
                self._handle_subscribe_status(msg)
            elif event == "unsubscribe-status":
                self._handle_unsubscribe_status(msg)
            elif event == "heartbeat":
                logger.debug("Twelve Data heartbeat received")
            else:
                logger.debug("Unhandled WS event: %s", event)

    # ------------------------------------------------------------------
    # Message handlers
    # ------------------------------------------------------------------

    def _handle_price(self, msg: dict) -> None:
        symbol = msg.get("symbol")
        if not symbol:
            logger.warning("Price message missing symbol: %s", msg)
            return
        self.prices[symbol] = {
            "symbol": symbol,
            "price": msg.get("price"),
            "timestamp": msg.get("timestamp"),
            "change": msg.get("day_change"),
            "percent_change": msg.get("day_change_percent"),
        }

    def _handle_subscribe_status(self, msg: dict) -> None:
        status = msg.get("status")
        if status == "ok":
            symbols = [s.get("symbol", "?") for s in msg.get("success", [])]
            logger.info("Subscribed: %s", ", ".join(symbols))
        else:
            logger.warning("Subscribe failed: %s", msg)

    def _handle_unsubscribe_status(self, msg: dict) -> None:
        status = msg.get("status")
        if status == "ok":
            logger.info("Unsubscribe confirmed: %s", msg)
        else:
            logger.warning("Unsubscribe issue: %s", msg)

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to price updates for the given symbols."""
        if not symbols:
            return
        payload = {
            "action": "subscribe",
            "params": {"symbols": ",".join(symbols)},
        }
        await self._send(payload)

    async def unsubscribe(self, symbols: list[str]) -> None:
        """Unsubscribe from price updates for the given symbols."""
        if not symbols:
            return
        # Never unsubscribe a symbol that is still needed elsewhere
        still_needed = self.dashboard_symbols | set(self.profile_symbols.keys())
        to_unsub = [s for s in symbols if s not in still_needed]
        if not to_unsub:
            return
        payload = {
            "action": "unsubscribe",
            "params": {"symbols": ",".join(to_unsub)},
        }
        await self._send(payload)

    async def _send(self, payload: dict) -> None:
        """Send a JSON message to the upstream websocket."""
        if self._ws is None:
            logger.warning("Cannot send — WS not connected: %s", payload)
            return
        try:
            await self._ws.send(json.dumps(payload))
        except Exception:
            logger.exception("Failed to send WS message: %s", payload)

    async def _resubscribe_all(self) -> None:
        """Re-subscribe to all tracked symbols after a reconnect."""
        all_symbols = list(self.dashboard_symbols | set(self.profile_symbols.keys()))
        if all_symbols:
            logger.info("Re-subscribing to %d symbols", len(all_symbols))
            await self.subscribe(all_symbols)

    # ------------------------------------------------------------------
    # Dashboard helpers
    # ------------------------------------------------------------------

    async def set_dashboard_symbols(self, symbols: set[str]) -> None:
        """Replace the full set of dashboard symbols and sync subscriptions."""
        new = symbols - self.dashboard_symbols
        removed = self.dashboard_symbols - symbols
        self.dashboard_symbols = set(symbols)

        if new:
            await self.subscribe(list(new))
        if removed:
            await self.unsubscribe(list(removed))

    # ------------------------------------------------------------------
    # Profile listener management
    # ------------------------------------------------------------------

    async def register_profile_listener(self, symbol: str) -> None:
        """Called when a frontend client opens a stock-profile websocket."""
        self.profile_symbols[symbol] = time.monotonic()
        already_subscribed = symbol in self.dashboard_symbols or symbol in self.prices
        if not already_subscribed:
            await self.subscribe([symbol])

    async def unregister_profile_listener(self, symbol: str) -> None:
        """Called when a frontend client closes a stock-profile websocket.

        Does NOT immediately unsubscribe — the cleanup loop will handle it
        after the TTL expires, giving other clients a chance to reconnect.
        """
        # Just leave it in profile_symbols; cleanup loop handles expiry.
        logger.debug("Profile listener unregistered for %s", symbol)

    def heartbeat_profile(self, symbol: str) -> None:
        """Refresh the last_active timestamp for a profile symbol."""
        if symbol in self.profile_symbols:
            self.profile_symbols[symbol] = time.monotonic()

    # ------------------------------------------------------------------
    # Price accessors
    # ------------------------------------------------------------------

    def get_price(self, symbol: str) -> Optional[dict]:
        """Return the latest cached price for *symbol*, or ``None``."""
        return self.prices.get(symbol)

    def get_all_prices(self) -> dict[str, dict]:
        """Return a copy of all cached prices."""
        return dict(self.prices)

    # ------------------------------------------------------------------
    # Cleanup loop
    # ------------------------------------------------------------------

    async def _cleanup_loop(self) -> None:
        """Periodically remove idle profile subscriptions."""
        while self._running:
            await asyncio.sleep(CLEANUP_INTERVAL_S)
            try:
                await self._cleanup_stale_profiles()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in profile cleanup loop")

    async def _cleanup_stale_profiles(self) -> None:
        """Unsubscribe from profile symbols that have been idle too long."""
        now = time.monotonic()
        stale: list[str] = []
        for symbol, last_active in list(self.profile_symbols.items()):
            if now - last_active > PROFILE_SYMBOL_TTL_S:
                stale.append(symbol)

        for symbol in stale:
            del self.profile_symbols[symbol]
            logger.info("Profile symbol expired: %s", symbol)

        if stale:
            await self.unsubscribe(stale)
