from AlgoAPI import AlgoAPIUtil, AlgoAPI_Backtest
from datetime import datetime, timedelta

class AlgoEvent:
    def __init__(self, timeinforce=86400):
        self.price_changes = []
        self.volumes = []
        self.close_prices = []
        self.trend_labels = []  # list of (timestamp, trend_value, close_price)
        self.buyPrice = None
        self.sellPrice = None
        self.lows_base_count = 0
        self.lows_peak_count = 0
        self.prev_peak_count = None  # for sell signal detection
        self.buySignal_active = False  # flag to control sell logic
        self.volume_spike_signals = []
        self.buy_with_volume_signals = []
        self.initial_capital = 100000.0
        self.available_capital = 100000.0
        self.timeinforce = timeinforce
        self.net_volume = 0
        self.successful_buys = []  # list of (tradeID, price, volume)
        self.anchor_prices = []  # list of (price, volume)
        self.highest_high = 0
        self.highest_low = 0

    def start(self, mEvt):
        self.evt = AlgoAPI_Backtest.AlgoEvtHandler(self, mEvt)
        self.myinstrument = mEvt['subscribeList'][0]
        self.lastprice = None
        self.evt.start()

    def detect_downtrend(self, prices):
        if len(prices) < 2:
            return False
        highs, lows = [], []
        if prices[0] <= prices[1]:
            lows.append(prices[0])
            highs.append(prices[1])
        else:
            lows.append(prices[1])
            highs.append(prices[0])
        for value in prices[2:]:
            if value < lows[-1]:
                lows.append(value)
            elif value < highs[-1]:
                highs.append(value)
            else:
                return False
        return True

    def detect_uptrend(self, prices):
        if len(prices) < 2:
            return False
        highs, lows = [], []
        if prices[0] >= prices[1]:
            highs.append(prices[0])
            lows.append(prices[1])
        else:
            highs.append(prices[1])
            lows.append(prices[0])
        for value in prices[2:]:
            if value > highs[-1]:
                highs.append(value)
            elif value > lows[-1]:
                lows.append(value)
            else:
                return False
        return True

    def get_macro_uptrend_lows(self):
        breakpoints = []
        i = len(self.trend_labels) - 1
        current_breakpoint = None
        while i >= 0:
            if self.trend_labels[i][1] == 1:
                i -= 1
                continue
            temp_segment = []
            while i >= 0 and self.trend_labels[i][1] in [0, -1]:
                price = self.trend_labels[i][2]
                timestamp = self.trend_labels[i][0]
                temp_segment.append((price, timestamp))
                i -= 1
            if not temp_segment:
                continue
            lowest_price, low_timestamp = min(temp_segment, key=lambda x: x[0])
            if current_breakpoint is None or lowest_price <= current_breakpoint[0]:
                current_breakpoint = (lowest_price, low_timestamp)
                breakpoints.append(current_breakpoint)
        return breakpoints[::-1]

    def get_macro_uptrend_highs(self):
        highs = []
        i = len(self.trend_labels) - 1
        current_high = None
        while i >= 0:
            temp_segment = []
            uptrend_count = 0
            expect_uptrend = False
            while i >= 0:
                label = self.trend_labels[i][1]
                price = self.trend_labels[i][2]
                timestamp = self.trend_labels[i][0]
                if label in [-1, 0]:
                    if uptrend_count > 0:
                        temp_segment.append((price, timestamp))
                        i -= 1
                        break
                    else:
                        temp_segment.append((price, timestamp))
                        i -= 1
                        expect_uptrend = True
                        continue
                if label == 1:
                    if expect_uptrend:
                        temp_segment.append((price, timestamp))
                        if uptrend_count > 0:
                            break
                        uptrend_count += 1
                        i -= 1
                    else:
                        if uptrend_count > 0:
                            break
                        i -= 1
            if not temp_segment:
                continue
            highest_price, high_timestamp = max(temp_segment, key=lambda x: x[0])
            if current_high is None or highest_price <= current_high[0]:
                current_high = (highest_price, high_timestamp)
                highs.append(current_high)
            else:
                break
        return highs[::-1]

    def calculate_anchored_vwap(self):
        if not self.anchor_prices:
            return None
        total_pv = sum(price * volume for price, volume in self.anchor_prices)
        total_volume = sum(volume for _, volume in self.anchor_prices)
        return total_pv / total_volume if total_volume != 0 else None

    def check_buy_pattern(self, lows, highs, current_price, current_volume):
        if self.successful_buys:
            avg_price = round(sum(price for _, price, _ in self.successful_buys) / len(self.successful_buys), 4)
        else:
            avg_price = 0

        # Compute highest high and highest low from lists
        if highs:
            max_high = max(price for price, _ in highs)
            if self.highest_high < max_high:
                self.highest_high = max_high
        if lows:
            max_low = max(price for price, _ in lows)
            if self.highest_low < max_low:
                 self.highest_low = max_low

        # Check if current price fell below the band (i.e., below highest low)
        if self.highest_low != 0 and current_price < self.highest_low:
            self.anchor_prices.append((current_price, current_volume))
            anchored_vwap = self.calculate_anchored_vwap()
            if anchored_vwap and current_price > 1.05 * anchored_vwap:
                self.evt.consoleLog(f"---ABOVE ANCHOR------------")
                if len(lows) >= 3 and len(highs) >= 2:
                    l1, l2, l3 = lows[-3:]
                    h1, h2 = highs[-2:]

                    delta1 = (l2[1] - l1[1]).total_seconds()
                    delta2 = (l3[1] - l2[1]).total_seconds()

                    slope1 = (l2[0] - l1[0]) / delta1 if delta1 != 0 else 0
                    slope2 = (l3[0] - l2[0]) / delta2 if delta2 != 0 else 0

                    if 0.8 * slope1 < slope2 and l1[1] < h1[1] < l2[1] < h2[1] < l3[1]:
                        self.evt.consoleLog(f"---ABOVE ANCHOR UPTREND------------")
                        return True
        elif  self.highest_low != 0  and  self.highest_high != 0:
            # Within the band
            self.anchor_prices.clear()
            self.evt.consoleLog(f"---WITHIN BAND------------")
            if len(lows) >= 3 and len(highs) >= 2:
                
                l1, l2, l3 = lows[-3:]
                h1, h2 = highs[-2:]

                delta1 = (l2[1] - l1[1]).total_seconds()
                delta2 = (l3[1] - l2[1]).total_seconds()

                slope1 = (l2[0] - l1[0]) / delta1 if delta1 != 0 else 0
                slope2 = (l3[0] - l2[0]) / delta2 if delta2 != 0 else 0

                if 0.8 * slope1 < slope2 and l1[1] < h1[1] < l2[1] < h2[1] < l3[1]:
                    self.evt.consoleLog(f"---WITHIN BAND UPTREND------------")
                    return True

        # Fallback if not enough lows/highs but current price > avg price
        
        if  self.highest_low is  None and  self.highest_high is  None and current_price > avg_price:
            self.evt.consoleLog(f"---ABOVE AVERAGE PRICE & INITIAL CAPITAL------------")
            capital_to_use = 0.03 * self.available_capital
            volume_to_buy = round(capital_to_use / current_price)
            stop_loss = round(current_price * 0.95, 4)

            order = AlgoAPIUtil.OrderObject()
            order.instrument = self.myinstrument
            order.orderRef = int(datetime.now().timestamp())
            order.openclose = 'open'
            order.buysell = 1
            order.ordertype = 2
            order.price = current_price
            order.volume = volume_to_buy
            order.stopLossLevel = stop_loss
            order.timeinforce = self.timeinforce

            self.evt.sendOrder(order)
            self.buy_with_volume_signals.append((datetime.now(), current_price))
            self.evt.consoleLog(f"Initial STOP ORDER: {volume_to_buy:.0f} units @ {current_price:.4f}, Stop Loss: {stop_loss:.4f}")

        return False


    def check_sell_signal(self, current_price, highs):
        if len(highs) >= 3:
            (x1_price, x1_time), (x2_price, x2_time), (x3_price, x3_time) = highs[-3:]

            delta1 = (x2_time - x1_time).total_seconds()
            delta2 = (x3_time - x2_time).total_seconds()

            slope1 = (x2_price - x1_price) / delta1 if delta1 != 0 else 0
            slope2 = (x3_price - x2_price) / delta2 if delta2 != 0 else 0

            if slope1 * 0.7 > slope2:
                should_close = False
                for tradeID, buy_price, volume in self.successful_buys:
                    if current_price > round(1.08 * buy_price, 4):
                        should_close = True
                        order = AlgoAPIUtil.OrderObject()
                        order.orderRef = f"close_{tradeID}"
                        order.tradeID = tradeID
                        order.openclose = 'close'
                        order.volume = volume
                        self.evt.consoleLog(f"CLOSING TRADE: TradeID={tradeID}, Volume={volume}, BuyPrice={buy_price}, CurrentPrice={current_price}")
                        self.evt.sendOrder(order)
                if should_close:
                    return True
        return False

    def can_buy_with_volume(self, current_price, current_volume, lows, highs, open_price, high_price, low_price):
        if not self.check_buy_pattern(lows, highs, current_price, current_volume):
            return 0

   
         #   return 0

        avg_price = 0
        capital_to_use = 0

        if self.successful_buys:
            avg_price = round(sum(price for _, price, _ in self.successful_buys) / len(self.successful_buys), 4)
            if current_price * 1.03 < avg_price:
                capital_to_use = 0.30 * self.available_capital
                self.evt.consoleLog(f"--30%-- (Avg Buy Price: {avg_price:.4f})")
            else:
                capital_to_use = 0.20 * self.available_capital
                self.evt.consoleLog(f"--20%-- (Avg Buy Price: {avg_price:.4f})")
                
        else:
            capital_to_use = 0.20 * self.available_capital
            self.evt.consoleLog(f"--20%-- (Avg Buy Price: {avg_price:.4f})")

        self.evt.consoleLog(f"Avg price: {avg_price:.4f} current price: {current_price}")

        volume_to_buy = round(capital_to_use / current_price)

        eight_percent_price = 0.08 * current_price
        second_last_low = lows[-2][0] if len(lows) >= 2 else 0
        stop_loss = current_price - max(eight_percent_price, current_price - second_last_low)

        order = AlgoAPIUtil.OrderObject()
        order.instrument = self.myinstrument
        order.orderRef = int(datetime.now().timestamp())
        order.openclose = 'open'
        order.buysell = 1
        order.ordertype = 2  #stop order
        order.price = current_price
        order.volume = volume_to_buy
        order.stopLossLevel = stop_loss
        order.timeinforce = self.timeinforce

        self.evt.sendOrder(order)
        self.buy_with_volume_signals.append((self.trend_labels[-1][0], current_price))

        self.evt.consoleLog(f"STOP ORDER: {volume_to_buy:.0f} units @ {current_price}, Stop Loss: {stop_loss:.2f}")
        return volume_to_buy

    def on_bulkdatafeed(self, isSync, bd, ab):
        if self.myinstrument not in bd:
            return

        timestamp = bd[self.myinstrument]['timestamp']
        current_price = bd[self.myinstrument]['lastPrice']
        current_volume = bd[self.myinstrument]['volume']
        openPrice = bd[self.myinstrument]['openPrice']
        highPrice = bd[self.myinstrument]['highPrice']
        lowPrice = bd[self.myinstrument]['lowPrice']

        self.available_capital = ab['availableBalance']

        if self.successful_buys:
            avg_price = round(sum(price for _, price, _ in self.successful_buys) / len(self.successful_buys), 4)
        else:
            avg_price = 0

        self.evt.consoleLog(
            f"{timestamp}: Open = {openPrice:.2f} | Close = {current_price:.2f} | High = {highPrice:.2f} | Low = {lowPrice:.2f} | Volume: {current_volume} | Avg Buy Cost: {avg_price:.4f}"
        )

        if self.lastprice is not None:
            diff = current_price - self.lastprice
            self.price_changes.append(diff)
            self.volumes.append(current_volume)
            self.close_prices.append(current_price)

            if len(self.close_prices) >= 4:
                trend_window = self.close_prices[-4:]
                if self.detect_uptrend(trend_window):
                    self.trend_labels.append((timestamp, 1, current_price))
                elif self.detect_downtrend(trend_window):
                    self.trend_labels.append((timestamp, 0, current_price))
                else:
                    self.trend_labels.append((timestamp, -1, current_price))

            lows = self.get_macro_uptrend_lows()
            highs = self.get_macro_uptrend_highs()

            current_low_count = len(lows)

            if current_low_count > self.lows_peak_count:
                self.prev_peak_count = self.lows_peak_count
                self.lows_peak_count = current_low_count

            if self.prev_peak_count is not None and current_low_count - self.prev_peak_count <= -2:
                self.sellPrice = current_price
                self.buySignal_active = False
                self.evt.consoleLog("SELL ALL")
                if self.net_volume > 0:
                    for tradeID, _, volume in self.successful_buys:
                        order = AlgoAPIUtil.OrderObject()
                        order.orderRef = f"close_{tradeID}"
                        order.tradeID = tradeID
                        order.openclose = 'close'
                        order.volume = volume
                        self.evt.sendOrder(order)
                        self.evt.consoleLog(f"CLOSING TRADE: TradeID={tradeID}, Volume={volume}")
                self.prev_peak_count = current_low_count

            #if self.check_volume_spike_sell_signal(current_volume, openPrice, current_price, highPrice, lowPrice) and self.buySignal_active:
            #    self.sellPrice = current_price
            #    self.buySignal_active = False
            #    self.evt.consoleLog(f"Volume spike SELL SIGNAL at Price = {current_price}")

            if self.check_sell_signal(current_price, highs):
                self.volume_spike_signals.append((self.trend_labels[-1][0], current_price))
                
            self.can_buy_with_volume(current_price, current_volume, lows, highs, openPrice, highPrice, lowPrice)

        self.lastprice = current_price

    def on_marketdatafeed(self, md, ab):
        pass
    def on_newsdatafeed(self, nd):
        pass
    def on_weatherdatafeed(self, wd):
        pass
    def on_econsdatafeed(self, ed):
        pass
    def on_corpAnnouncement(self, ca):
        pass
    
    def on_orderfeed(self, of):
        if of.instrument == self.myinstrument and of.buysell == 1 and of.status == 'success':
            tradeID = of.tradeID
            price = of.fill_price
            volume = of.fill_volume
            self.successful_buys.append((tradeID, price, volume))
            #self.evt.consoleLog(f"BUY FILLED: TradeID={tradeID}, Price={price}, Volume={volume}")
            #summary_lines = [f"Trade Summary ({len(self.successful_buys)} total):"]
            #total_volume = 0
            #for tid, p, v in self.successful_buys:
            #    summary_lines.append(f"- TradeID: {tid}, Price: {p}, Volume: {v}")
            #    total_volume += v
            #summary_lines.append(f"Net Volume (from buys) = {total_volume}")
            #summary_lines.append(f"Net Volume (from position feed) = {self.net_volume}")
            #self.evt.consoleLog("\n".join(summary_lines))
    
        if of.instrument == self.myinstrument and of.openclose == 'close' and of.status == 'success':
            tradeID = of.tradeID
            price = of.fill_price
            volume = of.fill_volume
            #self.evt.consoleLog(f"CLOSE FILLED: TradeID={tradeID}, Price={price}, Volume={volume}")
            self.successful_buys = [(tid, p, v) for tid, p, v in self.successful_buys if tid != tradeID]
            
    def on_dailyPLfeed(self, pl):
        pass
    def on_openPositionfeed(self, op, oo, uo):
        if self.myinstrument in op:
            self.net_volume = op[self.myinstrument]['netVolume']








