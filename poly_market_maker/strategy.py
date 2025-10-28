from enum import Enum
import json
import logging
from typing import Optional

from poly_market_maker.orderbook import OrderBookManager
from poly_market_maker.price_feed import PriceFeed
from poly_market_maker.token import Token, Collateral
from poly_market_maker.constants import MAX_DECIMALS

from poly_market_maker.strategies.base_strategy import BaseStrategy
from poly_market_maker.strategies.amm_strategy import AMMStrategy
from poly_market_maker.strategies.bands_strategy import BandsStrategy
from poly_market_maker.plan_provider import PlanProvider


class Strategy(Enum):
    AMM = "amm"
    BANDS = "bands"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for strategy in Strategy:
                if value.lower() == strategy.value.lower():
                    return strategy
        return super()._missing_(value)


class StrategyManager:
    def __init__(
        self,
        strategy: str,
        config_path: str,
        price_feed: PriceFeed,
        order_book_manager: OrderBookManager,
        plan_provider: Optional[PlanProvider] = None,
    ) -> BaseStrategy:
        self.logger = logging.getLogger(self.__class__.__name__)

        with open(config_path) as fh:
            config = json.load(fh)

        self.price_feed = price_feed
        self.order_book_manager = order_book_manager
        self.plan_provider = plan_provider

        match Strategy(strategy):
            case Strategy.AMM:
                self.strategy = AMMStrategy(config)
            case Strategy.BANDS:
                self.strategy = BandsStrategy(config)
            case _:
                raise Exception("Invalid strategy")

    def synchronize(self):
        self.logger.debug("Synchronizing strategy...")

        try:
            orderbook = self.get_order_book()
        except Exception as e:
            self.logger.error(f"{e}")
            return

        if self.plan_provider is not None:
            plan = self.plan_provider.current()
            if plan is None:
                self.logger.warning(
                    "No allocator plan available for market %s", self.plan_provider.market_id
                )
            elif hasattr(self.strategy, "update_plan"):
                self.logger.debug(
                    "Applying allocator plan target %.2f (tilt=%s, confidence=%.2f)",
                    plan.target_notional_usd,
                    plan.tilt_bias,
                    plan.tilt_confidence,
                )
                self.strategy.update_plan(plan)

        token_prices = self.get_token_prices()
        self.logger.debug(f"{token_prices}")
        (orders_to_cancel, orders_to_place) = self.strategy.get_orders(
            orderbook, token_prices
        )

        self.logger.debug(f"order to cancel: {len(orders_to_cancel)}")
        self.logger.debug(f"order to place: {len(orders_to_place)}")

        self.cancel_orders(orders_to_cancel)
        self.place_orders(orders_to_place)

        self.logger.debug("Synchronized strategy!")

    def get_order_book(self):
        orderbook = self.order_book_manager.get_order_book()

        if None in orderbook.balances.values():
            self.logger.debug("Balances invalid/non-existent")
            raise Exception("Balances invalid/non-existent")

        if sum(orderbook.balances.values()) == 0:
            self.logger.debug("Wallet has no balances for this market")
            raise Exception("Zero Balances")

        return orderbook

    def get_token_prices(self):
        price_a = round(
            self.price_feed.get_price(Token.A),
            MAX_DECIMALS,
        )
        price_b = round(1 - price_a, MAX_DECIMALS)
        return {Token.A: price_a, Token.B: price_b}

    def cancel_orders(self, orders_to_cancel):
        if len(orders_to_cancel) > 0:
            self.logger.info(
                f"About to cancel {len(orders_to_cancel)} existing orders!"
            )
            self.order_book_manager.cancel_orders(orders_to_cancel)

    def place_orders(self, orders_to_place):
        if len(orders_to_place) > 0:
            self.logger.info(f"About to place {len(orders_to_place)} new orders!")
            self.order_book_manager.place_orders(orders_to_place)
