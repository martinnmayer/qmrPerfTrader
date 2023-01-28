from tqdm import tqdm
import pandas as pd
import numpy as np
from utils import create_trade_log

class Strategy():
    def __init__(self):
        self.idx = None
        self.ohlc = None
        self.indicators = {}
        self._broker = Broker()
        self._positions = {}

    def buy(self,ticker,size=1):
        self._broker.orders.append(
            Order(
                ticker = ticker,
                side = 'buy',
                size = size,
                idx = self.idx
            ))
                
    def sell(self,ticker,size=1):
        self._broker.orders.append(
            Order(
                ticker = ticker,
                side = 'sell',
                size = -size,
                idx = self.idx
            ))


    def position_size(self,ticker):
        return self._positions[ticker]
    
    def indicator(self, ticker, name):
        return self.indicators[ticker][name].loc[:self.idx]
    
    @property
    def tickers(self):
        return list(self.ohlc.keys())
    def next(self):
        pass
    
class Order():
    def __init__(self, ticker, size, side, idx):
        self.ticker = ticker
        self.side = side
        self.size = size
        self.type = 'market'
        self.idx = idx
        
class Trade():
    def __init__(self, ticker,side,size,price,type,idx):
        self.ticker = ticker
        self.side = side
        self.price = price
        self.size = size
        self.type = type
        self.idx = idx

    
    def __repr__(self):
        return f'<Trade: {self.idx} {self.ticker} {self.size}@{self.price}>'
        
    def __str__(self):
        return f'<Trade: {self.idx} {self.ticker} {self.size}@{self.price}>'
    
class Broker():
    def __init__(self):
        self.orders = []
        self.trades = []

class Engine():
    def __init__(self, strategy:Strategy, cash:float=10_000, risk_free_rate:float=0):
        self.strategy = strategy()
        self.ohlc = {}
        self._iterators = {}
        self.current_prices = {}
        self.current_indicators = {}
        self.indexes = None
        self.cash = cash
        self.cash_series = {}
        self.output = {}
        self.indicator_functions = {}
        self.risk_free_rate = risk_free_rate
    
    def set_cash(self, amount:float):
        self.cash = amount

    def add_bardata(self, name, data):
        self.ohlc[name] = data
        self._iterators[name] = data.iterrows()
        if self.indexes is None:
            self.indexes = data.index.to_numpy()
            
    def add_indicator(self, name, function, *args):
        self.indicator_functions[name] = [function,*args]
        
    def run(self):
        self.strategy.ohlc = self.ohlc
        self._prepare_indicators()
        for t in self.strategy.tickers:
            self.strategy._positions[t] = 0
        for i in tqdm(self.indexes):
            for t in self.strategy.tickers:
                self.current_prices[t] = next(self._iterators[t])[1]
                
            self.strategy.idx = i
            self._fill_orders()
            self.cash_series[i] = self.cash 
            self.strategy.next()
        self._close_all_positions()
        self.cash_series[i] = self.cash

        self._prepare_output()
        return self.output
    
    def _prepare_indicators(self):
        for ticker in self.strategy.tickers:
            self.strategy.indicators[ticker] = {}
            for name, logic in self.indicator_functions.items():
                self.strategy.indicators[ticker][name] = logic[0](self.strategy.ohlc[ticker], logic[1])
                
    def _prepare_output(self):
        self.cash_series = pd.Series(self.cash_series)
        df_trades = pd.DataFrame(index=self.cash_series .index)
        for t in self.strategy._broker.trades:
            df_trades.loc[t.idx, t.ticker] = t.size
        df_positions = df_trades.fillna(0).cumsum()

        prices = pd.DataFrame(index=self.cash_series.index)
        for ticker in self.strategy.tickers:
            prices[ticker] = self.strategy.ohlc[ticker]['Close']
        df_portfolio = df_positions * prices
        df_portfolio['cash'] = self.cash_series
        df_portfolio['total'] = df_portfolio.sum(axis=1)
        self.output['portfolio'] = df_portfolio
        self.output['positions'] = df_positions
        self.output['trades'] = create_trade_log(self.strategy._broker.trades)

        # TODO: RESAMPLE TO DAILY IN CASE WE'RE USING OTHER TIMEFRAMES
        p = df_portfolio.total
        statistics = pd.DataFrame(
            index=['return_total','return_ann', 'volatility_ann', 'sharpe_ratio'])
        statistics.loc['return_ann', 'value'] = (
            (p.iloc[-1] / p.iloc[0]) ** (1 / ((p.index[-1] - p.index[0]).days / 365)) - 1) * 100
        
        # TODO: STOCKS IS 252 AND CRYPTO IS 365 (WEEKEND TRADING). WE NEED TO ACCOUNT FOR THAT HERE.
        statistics.loc['volatility_ann',
                       'value'] = p.pct_change().std() * np.sqrt(252) * 100
        statistics.loc['sharpe_ratio', 'value'] = (
            statistics.value.return_ann - self.risk_free_rate) / statistics.value.volatility_ann
        statistics.loc['return_total', 'value'] = (p.iloc[-1] / p.iloc[0] - 1) * 100
        self.output['statistics'] = statistics
    
    def _close_all_positions(self):
        for ticker in self.strategy.tickers:
            position = self.strategy.position_size(ticker)
            if  position !=0:
                t = Trade(
                    ticker = ticker,
                    side = 'sell' if position > 0 else 'buy',
                    price= self.current_prices[ticker]['Close'],
                    size = -position,
                    type = 'market',
                    idx = self.strategy.idx)
                self.strategy._positions[ticker] += t.size
                self.strategy._broker.trades.append(t)
                self.cash -= t.price * t.size
    
    def _fill_orders(self):
        for order in self.strategy._broker.orders:
            can_fill = False
            if order.side == 'buy' and self.cash >= self.current_prices[order.ticker]['Open'] * order.size:
                    can_fill = True 
            elif order.side == 'sell' and self.strategy._positions[order.ticker] >= order.size:
                    can_fill = True

            if can_fill:
                t = Trade(
                    ticker = order.ticker,
                    side = order.side,
                    price= self.current_prices[order.ticker]['Open'],
                    size = order.size,
                    type = order.type,
                    idx = self.strategy.idx)
                self.strategy._positions[order.ticker] += order.size
                # print(self.strategy._positions)
                self.strategy._broker.trades.append(t)
                self.cash -= t.price * t.size
        self.strategy._broker.orders = []
        

                