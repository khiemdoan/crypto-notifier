__author__ = 'Khiem Doan'
__github__ = 'https://github.com/khiemdoan'
__email__ = 'doankhiem.crazy@gmail.com'

import asyncio
import logging
from datetime import datetime
from math import floor, log

import httpx
import pandas as pd
from fp.fp import FreeProxy
from prettytable import PrettyTable
from pytz import timezone
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from dtos import Ticker
from messenger import send_message
from templates import render

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@retry(
    wait=wait_fixed(1),
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(5),
    reraise=True,
)
def _fetch() -> list[Ticker]:
    proxy = FreeProxy(country_id=['JP'], anonym=True, timeout=60).get()
    with httpx.Client(base_url='https://fapi.binance.com', proxy=proxy, http2=True, verify=False, timeout=60) as client:
        resp = client.get('/fapi/v1/ticker/24hr')
        if resp.is_error:
            raise Exception(resp.content)
        data = resp.json()
        return [Ticker(**d) for d in data]


def main() -> None:
    logger.info('Start collect data')

    now = datetime.now(tz=timezone('Asia/Ho_Chi_Minh'))

    tickers = _fetch()
    tickers = pd.DataFrame([t.model_dump() for t in tickers])

    # Top gainers
    tops = tickers[['symbol', 'price_change_percent']].sort_values(by='price_change_percent', ascending=False)
    tops = tops.iloc[:10, :]
    logger.info(f'Top gainer: {tops.iloc[0, 0]} {tops.iloc[0, 1]}%')

    symbols = tops['symbol'].to_list()
    table = _craft_table(['Symbol', 'Change'], tops)
    message = render('top.j2', context={'title': 'Top gainers', 'time': now, 'symbols': symbols, 'table': table})
    asyncio.run(send_message(message))

    # Top losers
    tops = tickers[['symbol', 'price_change_percent']].sort_values(by='price_change_percent')
    tops = tops.iloc[:10, :]
    logger.info(f'Top loser: {tops.iloc[0, 0]} {tops.iloc[0, 1]}%')

    symbols = tops['symbol'].to_list()
    table = _craft_table(['Symbol', 'Change'], tops)
    message = render('top.j2', context={'title': 'Top losers', 'time': now, 'symbols': symbols, 'table': table})
    asyncio.run(send_message(message))

    # Top tradings
    tops = tickers[['symbol', 'count']].sort_values(by='count', ascending=False)
    tops = tops.iloc[:10, :]
    logger.info(f'Top tradings: {tops.iloc[0, 0]} {tops.iloc[0, 1]}')

    symbols = tops['symbol'].to_list()
    table = _craft_table(['Symbol', 'Trade'], tops)
    message = render('top.j2', context={'title': 'Top tradings', 'time': now, 'symbols': symbols, 'table': table})
    asyncio.run(send_message(message))

    # Top volumes
    tops = tickers[['symbol', 'quote_volume']].sort_values(by='quote_volume', ascending=False)
    tops = tops.iloc[:10, :]
    tops['quote_volume'] = tops['quote_volume'].apply(_format_volume)
    logger.info(f'Top volumes: {tops.iloc[0, 0]} ${tops.iloc[0, 1]}')

    symbols = tops['symbol'].to_list()
    table = _craft_table(['Symbol', 'Volume'], tops)
    message = render('top.j2', context={'title': 'Top volumes', 'time': now, 'symbols': symbols, 'table': table})
    asyncio.run(send_message(message))


def _craft_table(fields: list[str], data: pd.DataFrame) -> str:
    table = PrettyTable()
    table.field_names = fields
    table.align = 'r'
    for _, row in data.iterrows():
        table.add_row([row.iloc[0], row.iloc[1]])

    return str(table)


def _format_volume(number) -> str:
    units = ['', 'K', 'M', 'B', 'T', 'Q']
    k = 1000.0
    magnitude = int(floor(log(number, k)))
    return f'{(number / k**magnitude):.2f}{units[magnitude]}'


if __name__ == '__main__':
    main()
