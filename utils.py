import pandas as pd


def create_trade(open_order, close_order, trade, type):
    type_multiplier = -1 if type == 'short' else 1
    return {
        'type': type,
        'ticker': open_order.ticker,
        'entry_date': open_order.idx,
        'exit_date': close_order.idx,
        'entry_price': open_order.price,
        'exit_price': close_order.price,
        'size': trade,
        'return_pct': type_multiplier * (close_order.price - open_order.price)/open_order.price,
        'pnl': type_multiplier * (close_order.price - open_order.price)*trade
    }


def create_trade_log(trades):
    trades = [t.__dict__ for t in trades]
    df_trades = pd.DataFrame(trades)
    all_orders = df_trades.copy()
    all_orders.reset_index(inplace=True)
    trades = []
    for ticker in all_orders.ticker.unique():
        orders = all_orders[all_orders.ticker == ticker]
        # First iterate through long orderprints
        for idx, o in orders.iterrows():
            if o.side == 'sell':
                rem_qty = o['size']

                while rem_qty < 0:
                    # while rem_qty != 0:
                    opening_orders = orders[(
                        orders.index < idx) & (orders['size'] > 0)]
                    if not opening_orders.empty:
                        opening_order = opening_orders.iloc[0]
                        if opening_order['size'] > -rem_qty:
                            trade_size = - rem_qty
                        else:
                            trade_size = opening_order['size']
                        if trade_size <= 0:
                            break
                        orders.loc[opening_order.name, 'size'] -= trade_size
                        orders.loc[idx, 'size'] += trade_size
                        rem_qty += trade_size
                        trades.append(create_trade(
                            opening_order, o, trade_size, 'long'))

                    else:
                        break
        # Now check if we can create short orders with remaining quantities
        for idx, o in orders.iterrows():
            if o.side == 'buy':
                rem_qty = o['size']
                while rem_qty > 0:
                    # while rem_qty != 0:
                    opening_orders = orders[(
                        orders.index < idx) & (orders['size'] < 0)]
                    if not opening_orders.empty:
                        opening_order = opening_orders.iloc[0]
                        if - opening_order['size'] > rem_qty:
                            trade_size = rem_qty
                        else:
                            trade_size = - opening_order['size']
                        if trade_size <= 0:
                            break
                        orders.loc[opening_order.name, 'size'] += trade_size
                        orders.loc[idx, 'size'] -= trade_size
                        rem_qty -= trade_size
                        trades.append(create_trade(
                            opening_order, o, trade_size, 'short'))

                    else:
                        break
    log = pd.DataFrame(trades)
    if not log.empty:
        log['return_pct'] = log['return_pct'] * 100
        log['holding_time'] = log['exit_date'] - log['entry_date']
        # log.to_csv('trades.csv')
    return log
