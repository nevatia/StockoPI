"""
Stocko stock trading api wrapper.
Original creater Algo2t for Sasonline.
Modified By Sanju for Stocko on 01-01-2025.
"""
import csv
import ast
import os
import json
import requests
import threading
import websocket
import logging
import enum
from datetime import datetime, timedelta, date
from time import sleep
from collections import OrderedDict
from stocko.protlib import CUInt, CStruct, CLong, CULong , CUChar, CArray, CUShort, CString
from collections import namedtuple
import pandas as pd
import pytz
import stocko.exceptions as ex
import sys
from stocko.connect import Connect
import zipfile
from pathlib import Path
import shutil

Instrument = namedtuple('Instrument', ['exchange', 'token', 'symbol',
                                       'name', 'expiry', 'lot_size'])
logger = logging.getLogger(__name__)


class Requests(enum.Enum):
    PUT = 1
    DELETE = 2
    GET = 3
    POST = 4


class TransactionType(enum.Enum):
    Buy = 'BUY'
    Sell = 'SELL'


class OrderType(enum.Enum):
    Market = 'MARKET'
    Limit = 'LIMIT'
    StopLossLimit = 'SL'
    StopLossMarket = 'SL-M'


class ProductType(enum.Enum):
    Intraday = 'I'
    Delivery = 'D'
    CoverOrder = 'CO'
    BracketOrder = 'BO'


class LiveFeedType(enum.Enum):
    MARKET_DATA = 1
    COMPACT = 2
    SNAPQUOTE = 3
    FULL_SNAPQUOTE = 4
    #OI = 8

class WsFrameMode(enum.IntEnum):
    MARKETDATA = 1
    COMPACT_MARKETDATA = 2
    SNAPQUOTE = 3
    FULL_SNAPQUOTE = 4
    SPREADDATA = 5
    SPREAD_SNAPQUOTE = 6
    DPR = 7
    OI = 8
    MARKET_STATUS = 9
    EXCHANGE_MESSAGES = 10
    ORDERUPDATE = 11 #50
    

class MarketData(CStruct):
    exchange = CUChar()
    token = CUInt()
    ltp = CUInt()
    ltt = CUInt()
    ltq = CUInt()
    volume = CUInt()
    best_bid_price = CUInt()
    best_bid_quantity = CUInt()
    best_ask_price = CUInt()
    best_ask_quantity = CUInt()
    total_buy_quantity = CULong()
    total_sell_quantity = CULong()
    atp = CUInt()
    exchange_time_stamp = CUInt()
    open = CUInt()
    high = CUInt()
    low = CUInt()
    close = CUInt()
    yearly_high = CUInt()
    yearly_low = CUInt()
    low_dpr = CUInt()
    high_dpr = CUInt()
    current_oi = CUInt()
    initial_oi = CUInt()
    
class CompactDataoz(CStruct):
    exchange = CUChar()
    token = CUInt()
    ltp = CUInt()
    change = CUInt()
    exchange_time_stamp = CUInt()
    volume = CUInt()


class CompactData(CStruct):
    exchange = CUChar()
    token = CUInt()
    ltp = CUInt()
    change = CUInt()
    exchange_time_stamp = CUInt()
    low_dpr = CUInt()
    high_dpr = CUInt()
    current_oi = CUInt()
    initial_oi = CUInt()
    best_bid_price = CUInt()
    best_ask_price = CUInt()



class SnapQuote(CStruct):
    exchange = CUChar()
    token = CUInt()
    buyers = CArray(5, CUInt)
    bid_prices = CArray(5, CUInt)
    bid_quantities = CArray(5, CUInt)
    sellers = CArray(5, CUInt)
    ask_prices = CArray(5, CUInt)
    ask_quantities = CArray(5, CUInt)
    exchange_time_stamp = CUInt()


class FullSnapQuote(CStruct):
    exchange = CUChar()
    token = CUInt()
    buyers = CArray(5, CUInt)
    bid_prices = CArray(5, CUInt)
    bid_quantities = CArray(5, CUInt)
    sellers = CArray(5, CUInt)
    ask_prices = CArray(5, CUInt)
    ask_quantities = CArray(5, CUInt)
    atp = CUInt()
    open = CUInt()
    high = CUInt()
    low = CUInt()
    close = CUInt()
    total_buy_quantity = CULong()
    total_sell_quantity = CULong()
    volume = CUInt()

class ExchangeMessage(CStruct):
    exchange = CUChar()
    length = CUShort()
    message = CString(length="length")
    exchange_time_stamp = CUInt()


class MarketStatus(CStruct):
    exchange = CUChar()
    length_of_market_type = CUShort()
    market_type = CString(length="length_of_market_type")
    length_of_status = CUShort()
    status = CString(length="length_of_status")

class AlphaTrade(Connect):
    # dictionary object to hold settings
    __service_config = {
        'host': 'https://web.stocko.in',
        'routes': {
            'login': '/api/v3/user/login',
            'profile': '/api/v1/user/profile',
            'master_contract':'/api/v1/contract/Compact?info=download',
            'holdings': '/api/v1/holdings?client_id={client_id}',
            'cashPositions': '/api/v1/funds/view?client_id={client_id}&type=all',
            #'cashPositionsV2': '/api/v2/funds/view?client_id={client_id}&type=all', 
            'place_order': '/api/v1/orders',
            'place_amo': '/api/v2/amo',
            'place_bracket_order': '/api/v1/orders/bracket',
            'place_basket_order': '/api/v2/basketorder',
            'modify_order':'/api/v1/orders', 
            'cancelNormalOrder':'/api/v1/orders/{oms_order_id}?client_id={client_id}', 
            'exitBracketOrder': '/v1/orders/bracket',
            'exitCoverOrder': '/v1/orders/cover',
            'positionBook':'/api/v1/positions?type={type}&client_id={client_id}', 
            'trade_book': '/api/v1/trades?client_id={client_id}',
            'order_book':'/api/v1/orders?type={type}&client_id={client_id}', 
            'orderHistory': '/api/v1/order/{oms_order_id}/history?client_id={client_id}',
            'scripInfo': '/api/v1/contract/{exchange}?info=scrip&token={token}', 
            'searchScript':'/api/v1/search?key={keyword}',
            'optionchain':'/api/v1/optionchain/NFO?token={Token}&num={strikes}&price={price}',
        },
        'socket_endpoint': 'wss://api.stocko.in/ws/v1/feeds?login_id={client_id}&access_token={access_token}'
    }

    _candletype = {1: 1, 2: 1, 3: 1, 5: 1, 10: 1, 15: 1,
                   30: 1, 45: 1, '1H': 2, '2H': 2, '3H': 2, '4H': 2, '1D': 3, 'D': 3, 'W': 3, 'M': 3}

    _data_duration = {1: 1, 2: 2, 3: 3, 5: 5, 10: 10, 15: 15,
                      30: 30, 45: 45, '1H': None, '2H': 2, '3H': 2, '4H': 2, '1D': None, 'D': None, 'W': None, 'M': None}

    def __init__(self, login_id, password, totp, client_secret, access_token=None, master_contracts_to_download=None):
        super().__init__( "SAS-CLIENT1", client_secret, "http://127.0.0.1/" , "https://api.stocko.in", login_id, password, totp)
        """ logs in and gets enabled exchanges and products for user """
        self.__access_token = access_token
        self.__login_id = login_id
        self.__password = password
        self.__totp = totp #self.__twofa = twofa
        self.__client_secret = client_secret
        self.__websocket = None
        self.__websocket_connected = False
        self.__ws_mutex = threading.Lock()
        self.__on_error = None
        self.__on_disconnect = None
        self.__on_open = None
        self.__subscribe_callback = None
        self.__order_update_callback = None
        self.__market_status_messages_callback = None
        self.__exchange_messages_callback = None
        self.__oi_callback = None
        self.__dpr_callback = None
        self.__subscribers = {}
        self.__market_status_messages = []
        self.__exchange_messages = []
        self.__exchange_codes = {'NSE': 1,
                                 'NFO': 2,
                                 'CDS': 3,
                                 'MCX': 4,
                                 'BSE': 6,
                                 'BFO': 7}
        self.__exchange_price_multipliers = {1: 100,
                                             2: 100,
                                             3: 10000000,
                                             4: 100,
                                             6: 100,
                                             7: 100}


        self.__headers = {
            'Content-type': 'application/json',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
        }

        self.__set_access_token()
        self.check_masters()
        self.__master_contracts_by_token = {}
        self.__master_contracts_by_symbol = {}
        [ self.__get_master_contract(e) for e in master_contracts_to_download ]

    def __set_access_token(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            token_file_path = os.path.join(script_dir, 'token.json')
            with open(token_file_path, 'r') as f:
                data = json.load(f)
                self.__access_token = data['access_token']
                self.__headers['Authorization'] = f'Bearer {self.__access_token}' 
                profile = self.get_profile()
        except:
            print(f"Couldn't get profile info ")
            print(f"Creating fresh token..")
            self.__access_token = super().get_access_token('true')
            self.__headers['Authorization'] = f'Bearer {self.__access_token}' 
            
        try:
            profile = self.get_profile()
        except Exception as e:
            raise ex.PermissionException(
                f"Couldn't get profile info with credentials provided '{e}'")
        if(profile['status'] == 'error'):
            # Don't know why this error comes, but it safe to proceed further.
            if(profile['message'] == 'Not able to retrieve AccountInfoService'):
                logger.warning(
                    "Couldn't get profile info - 'Not able to retrieve AccountInfoService'")
            else:
                raise ex.PermissionException(
                    f"Couldn't get profile info '{profile['message']}'")

    def __convert_prices(self, dictionary, multiplier):
        keys = ['ltp',
                'best_bid_price',
                'best_ask_price',
                'atp',
                'open',
                'high',
                'low',
                'close',
                'yearly_high',
                'yearly_low',
                "low_dpr",
                "high_dpr",
                ]
        for key in keys:
            if(key in dictionary):
                dictionary[key] = dictionary[key]/multiplier
        multiple_value_keys = ['bid_prices', 'ask_prices']
        for key in multiple_value_keys:
            if(key in dictionary):
                new_values = []
                for value in dictionary[key]:
                    new_values.append(value/multiplier)
                dictionary[key] = new_values
        return dictionary

    def __format_candles(self, data, divider=1):
        records = data['data']['candles']
        df = pd.DataFrame(records, columns=[
            'date', 'open', 'high', 'low', 'close', 'volume'])  # , index=0)
        df['date'] = df['date'].apply(
            pd.Timestamp, unit='s', tzinfo=pytz.timezone('Asia/Kolkata'))
        # df['datetime'] = df['datetime'].astype(str).str[:-6]
        df[['open', 'high', 'low', 'close']] = df[[
            'open', 'high', 'low', 'close']].astype(float).div(divider)
        df['volume'] = df['volume'].astype(int)
        df.set_index('date', inplace=True)
        return df

    def __convert_oi(self, dictionary):
        if('instrument' in dictionary):
            dictionary['current_oi'] = int(dictionary['current_oi']/dictionary['instrument'].lot_size)
            dictionary['initial_oi'] = int(dictionary['initial_oi']/ dictionary['instrument'].lot_size)
        return dictionary

    def __convert_exchanges(self, dictionary):
        if('exchange' in dictionary):
            d = self.__exchange_codes
            dictionary['exchange'] = list(d.keys())[list(
                d.values()).index(dictionary['exchange'])]
        return dictionary

    def __convert_instrument(self, dictionary):
        if('exchange' in dictionary) and ('token' in dictionary):
            dictionary['instrument'] = self.get_instrument_by_token(
                dictionary['exchange'], dictionary['token'])
        return dictionary

    def __modify_human_readable_values(self, dictionary):
        dictionary = self.__convert_prices(
            dictionary, self.__exchange_price_multipliers[dictionary['exchange']])
        dictionary = self.__convert_exchanges(dictionary)
        dictionary = self.__convert_instrument(dictionary)
        #dictionary = self.__convert_oi(dictionary)
        return dictionary

    def __on_data_callback(self, ws=None, message=None, data_type=None, continue_flag=None):        
        if(type(ws) is not websocket.WebSocketApp):  # This workaround is to solve the websocket_client's compatibility issue of older versions. ie.0.40.0 which is used in upstox. Now this will work in both 0.40.0 & newer version of websocket_client
            message = ws  
        if(message[0] == WsFrameMode.MARKETDATA):
            p = MarketData.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            if(self.__subscribe_callback is not None):
                self.__subscribe_callback(res)
        elif(message[0] == WsFrameMode.COMPACT_MARKETDATA):
            p = CompactData.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            if(self.__subscribe_callback is not None):
                self.__subscribe_callback(res)
        elif(message[0] == WsFrameMode.SNAPQUOTE):
            p = SnapQuote.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            if(self.__subscribe_callback is not None):
                self.__subscribe_callback(res)
        elif(message[0] == WsFrameMode.FULL_SNAPQUOTE):
            p = FullSnapQuote.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            if(self.__subscribe_callback is not None):
                self.__subscribe_callback(res)
        elif(message[0] == WsFrameMode.MARKET_STATUS):
            res = MarketStatus.parse(message[1:]).__dict__
            res["market_type"] = res["market_type"].decode('ascii')
            res["status"] = res["status"].decode('ascii')
            self.__market_status_messages.append(res)
            if(self.__market_status_messages_callback is not None):
                self.__market_status_messages_callback(res)
        elif(message[0] == WsFrameMode.EXCHANGE_MESSAGES):
            res = ExchangeMessage.parse(message[1:]).__dict__
            res["message"] = res["message"].decode('ascii')
            self.__exchange_messages.append(res)
            if(self.__exchange_messages_callback is not None):
                self.__exchange_messages_callback(res)
        elif(message[0] == WsFrameMode.ORDERUPDATE):
            p= json.loads(message[5:])
            if(self.__subscribe_callback is not None):
                self.__order_update_callback(p)
        
    def __on_close_callback(self, ws=None):
        self.__websocket_connected = False
        if self.__on_disconnect:
            self.__on_disconnect()

    def __on_open_callback(self, ws=None):
        self.__websocket_connected = True
        self.__resubscribe()
        if self.__on_open:
            self.__on_open()

    def __on_error_callback(self, ws=None, error=None):
        if(type(ws) is not websocket.WebSocketApp):  # This workaround is to solve the websocket_client's compatibility issue of older versions. ie.0.40.0 which is used in upstox. Now this will work in both 0.40.0 & newer version of websocket_client
            error = ws
        if self.__on_error:
            self.__on_error(error)

    def __send_heartbeat(self):
        heart_beat = {"a": "h", "v": [], "m": ""}
        while True:
            sleep(5)
            self.__ws_send(json.dumps(heart_beat),
                           opcode=websocket._abnf.ABNF.OPCODE_PING)

    def __ws_run_forever(self):
        while True:
            try:
                self.__websocket.run_forever()
            except Exception as e:
                logger.warning(
                    f"websocket run forever ended in exception, {e}")
            sleep(0.1)  # Sleep for 100ms between reconnection.

    def __ws_send(self, *args, **kwargs):
        while self.__websocket_connected == False:
            # sleep for 50ms if websocket is not connected, wait for reconnection
            sleep(0.05)
        with self.__ws_mutex:
            self.__websocket.send(*args, **kwargs)

    def start_websocket(self, subscribe_callback=None,
                        order_update_callback=None,
                        socket_open_callback=None,
                        socket_close_callback=None,
                        socket_error_callback=None,
                        run_in_background=False,
                        market_status_messages_callback=None,
                        exchange_messages_callback=None,
                        oi_callback=None,
                        dpr_callback=None):
        """ Start a websocket connection for getting live data """
        self.__on_open = socket_open_callback
        self.__on_disconnect = socket_close_callback
        self.__on_error = socket_error_callback
        self.__subscribe_callback = subscribe_callback
        self.__order_update_callback = order_update_callback
        self.__market_status_messages_callback = market_status_messages_callback
        self.__exchange_messages_callback = exchange_messages_callback
        self.__oi_callback = oi_callback
        self.__dpr_callback = dpr_callback

        url = self.__service_config['socket_endpoint'].format(client_id = self.__login_id,access_token=self.__access_token)
        self.__websocket = websocket.WebSocketApp(url,
                                                  on_data=self.__on_data_callback,
                                                  on_error=self.__on_error_callback,
                                                  on_close=self.__on_close_callback,
                                                  on_open=self.__on_open_callback)
        th = threading.Thread(target=self.__send_heartbeat)
        th.daemon = True
        th.start()
        if run_in_background is True:
            self.__ws_thread = threading.Thread(target=self.__ws_run_forever)
            self.__ws_thread.daemon = True
            self.__ws_thread.start()
        else:
            self.__ws_run_forever()

    def get_profile(self):
        """ Get profile """
        return self.__api_call_helper('profile', Requests.GET, {'client_id': self.__login_id}, None)

    def get_balance(self):
        """ Get balance/margins """
        return self.__api_call_helper('cashPositions', Requests.GET, {'client_id': self.__login_id}, None)
    
    def get_optionchain(self,Token,strikes,price):
        """ optionchain"""
        params = {'Token':Token.token,'strikes':strikes,'price':price}
        return self.__api_call_helper('optionchain', Requests.GET, params , None)
  
    def get_balanceV2(self):
        """ Get balance/margins """
        return self.__api_call_helper('cashPositionsV2', Requests.GET, {'client_id': self.__login_id}, None)

    def get_daywise_positions(self):
        """ Get daywise positions """
        return self.__api_call_helper('positions_daywise', Requests.GET, None, None)

    def get_netwise_positions(self):
        """ Get netwise positions """
        return self.__api_call_helper('positions_netwise', Requests.GET, None, None)

    def get_dematholdings(self):
        """ Get Demat holdings """
        return self.__api_call_helper('holdings', Requests.GET, {'client_id': self.__login_id}, None)

    def fetch_live_positions(self):
        """ Get live positions """
        return self.__api_call_helper('positionBook', Requests.GET, {'client_id': self.__login_id, 'type': 'live'}, None)

    def fetch_netwise_positions(self):
        """ Get historical positions """
        return self.__api_call_helper('positionBook', Requests.GET, {'client_id': self.__login_id, 'type': 'historical'}, None)
    
    def get_orderbook(self, pending = True):
        """ leave pending to get completed order history """
        if pending :
            return self.__api_call_helper('order_book', Requests.GET, {'client_id': self.__login_id, 'type':'pending'}, None)
        else:
            return self.__api_call_helper('order_book', Requests.GET, {'client_id': self.__login_id, 'type':'completed'}, None)

    def get_order_history(self, order_id=None, pending = True):
        return self.__api_call_helper('orderHistory', Requests.GET, {'oms_order_id': order_id, 'client_id': self.__login_id,}, None)

    def get_scrip_info(self, instrument):
        """ Get scrip information """
        params = {'exchange': instrument.exchange, 'token': instrument.token}
        return self.__api_call_helper('scripInfo', Requests.GET, params, None)

    def get_tradebook(self):
        """ get all trades """
        return self.__api_call_helper('trade_book', Requests.GET, None, None)

    def get_exchanges(self):
        """ Get enabled exchanges """
        profile = self.__api_call_helper('profile', Requests.GET, None, None)
        if(profile['status'] != 'error'):
            self.__enabled_exchanges = profile['data']['exchanges_subscribed']
        return self.__enabled_exchanges

    def __get_product_type_str(self, product_type, exchange):
        prod_type = None
        if (product_type == ProductType.Intraday):
            prod_type = 'MIS'
        elif product_type == ProductType.Delivery:
            prod_type = 'NRML' if exchange in ['NFO', 'MCX', 'CDS'] else 'CNC'
        elif(product_type == ProductType.CoverOrder):
            prod_type = 'CO'
        elif(product_type == ProductType.BracketOrder):
            prod_type = None
        return prod_type

    def place_order(self,  instrument,   order_type,  quantity, product_type,  transaction_type, is_amo=False,  price=0.0, 
        trigger_price=0.0,
        stop_loss=None, 
        square_off=None, 
        trailing_sl=None,
        is_trailing = False,
        order_tag='python'):
        """ placing an order, many fields are optional and are not required
            for all order types
        """
        if transaction_type is None:
            raise TypeError(
                "Required parameter transaction_type not of type TransactionType")

        if not isinstance(instrument, Instrument):
            raise TypeError(
                "Required parameter instrument not of type Instrument")

        if not isinstance(quantity, int):
            raise TypeError("Required parameter quantity not of type int")

        if order_type is None:
            raise TypeError(
                "Required parameter order_type not of type OrderType")

        if product_type is None:
            raise TypeError(
                "Required parameter product_type not of type ProductType")

        if price is not None and not isinstance(price, float):
            raise TypeError("Optional parameter price not of type float")

        if trigger_price is not None and not isinstance(trigger_price, float):
            raise TypeError(
                "Optional parameter trigger_price not of type float")

        prod_type = self.__get_product_type_str(product_type, instrument.exchange)
        # construct order object after all required parameters are met
        order = {'exchange': instrument.exchange,
                 "order_side": transaction_type.value,
                 "order_type": order_type.value, 
                 'instrument_token': instrument.token,
                 'quantity': quantity,
                 'disclosed_quantity': 0,
                 'price': price,
                 'trigger_price': 0 , 
                 'validity': 'DAY',
                 'product': prod_type,
                 'device': 'api', 
                 'user_order_id': 100786, 
                 'execution_type': 'REGULAR',
                 'amo': is_amo,
                 'trigger_price': trigger_price,
                 #"market_protection_percentage": 10, #Optional
                 }
        

        if stop_loss is not None:
            if isinstance(stop_loss, float):
                order['stop_loss_value'] = stop_loss
            else:
                raise TypeError(
                    "Optional parameter stop_loss not of type float")
        if square_off is not None:
            if isinstance(square_off, float):
                order['square_off_value'] = square_off
            else:
                raise TypeError(
                    "Optional parameter square_off not of type float")
        if trailing_sl is not None:
            if not isinstance(trailing_sl, int):
                raise TypeError(
                    "Optional parameter trailing_sl not of type int")
            else:
                order['trailing_stop_loss'] = trailing_sl

        if product_type is ProductType.CoverOrder and not isinstance(
            trigger_price, float
        ):
            raise TypeError(
                "Required parameter trigger_price not of type float")

        helper = 'place_order'
        if product_type is ProductType.BracketOrder:
            helper = 'place_bracket_order'
            #del order['product']
            if not isinstance(stop_loss, float):
                raise TypeError(
                    "Required parameter stop_loss not of type float")

            if not isinstance(square_off, float):
                raise TypeError(
                    "Required parameter square_off not of type float")
            order["is_trailing"]=  is_trailing #// Optional: true or false
        return self.__api_call_helper(helper, Requests.POST, None, order)

    def place_basket_order(self, orders):  ############### work pending
        """ placing a basket order, 
            Argument orders should be a list of all orders that should be sent
            each element in order should be a dictionary containing the following key.
            "instrument", "order_type", "quantity", "price" (only if its a limit order), 
            "transaction_type", "product_type"
        """
        keys = {"instrument": Instrument,
                "order_type": OrderType,
                "quantity": int,
                "transaction_type": TransactionType,
                "product_type": ProductType}
        if not isinstance(orders, list):
            raise TypeError("Required parameter orders is not of type list")

        if len(orders) <= 0:
            raise TypeError("Length of orders should be greater than 0")

        for i in orders:
            if not isinstance(i, dict):
                raise TypeError(
                    "Each element in orders should be of type dict")
            for s, value in keys.items():
                if s not in i:
                    raise TypeError(
                        f"Each element in orders should have key {s}")
                if type(i[s]) is not value:
                    raise TypeError(
                        f"Element '{s}' in orders should be of type {keys[s]}")
            if i['order_type'] == OrderType.Limit:
                if "price" not in i:
                    raise TypeError(
                        "Each element in orders should have key 'price' if its a limit order ")
                if not isinstance(i['price'], float):
                    raise TypeError(
                        "Element price in orders should be of type float")
            else:
                i['price'] = 0.00
            if i['order_type'] in [
                OrderType.StopLossLimit,
                OrderType.StopLossMarket,
            ]:
                if 'trigger_price' not in i:
                    raise TypeError(
                        f"Each element in orders should have key 'trigger_price' if it is an {i['order_type']} order")
                if not isinstance(i['trigger_price'], float):
                    raise TypeError(
                        "Element trigger_price in orders should be of type float")
            else:
                i['trigger_price'] = 0.00
            if (i['product_type'] == ProductType.Intraday):
                i['product_type'] = 'MIS'
            elif i['product_type'] == ProductType.Delivery:
                i['product_type'] = 'NRML' if (
                    i['instrument'].exchange == 'NFO') else 'CNC'
            elif i['product_type'] in [
                ProductType.CoverOrder,
                ProductType.BracketOrder,
            ]:
                raise TypeError(
                    "Product Type BO or CO is not supported in basket order")
            if i['quantity'] <= 0:
                raise TypeError("Quantity should be greater than 0")

        data = {'source': 'web',
                'orders': []}
        for i in orders:
            # construct order object after all required parameters are met
            data['orders'].append({'exchange': i['instrument'].exchange,
                                   'order_type': i['order_type'].value,
                                   'instrument_token': i['instrument'].token,
                                   'quantity': i['quantity'],
                                   'price': i['price'],
                                   'disclosed_quantity': 0,                                   
                                   'transaction_type': i['transaction_type'].value,
                                   'trigger_price': i['trigger_price'],
                                   'validity': 'DAY',
                                   'product': i['product_type']}) 

        helper = 'place_basket_order'
        print(data)
        return self.__api_call_helper(helper, Requests.POST, None, data)

    def modify_order(self, transaction_type, instrument, product_type, order_id, order_type, quantity=None, price=0.0,
                     trigger_price=0.0):
        """ modify an order, transaction_type, instrument, product_type, order_id & order_type is required,
            rest are optional, use only when when you want to change that attribute.
        """
        if not isinstance(instrument, Instrument):
            raise TypeError(
                "Required parameter instrument not of type Instrument")

        if not isinstance(order_id, str):
            raise TypeError("Required parameter order_id not of type str")

        if quantity is not None and not isinstance(quantity, int):
            raise TypeError("Optional parameter quantity not of type int")

        if type(order_type) is not OrderType:
            raise TypeError(
                "Optional parameter order_type not of type OrderType")

        if ProductType is None:
            raise TypeError(
                "Required parameter product_type not of type ProductType")

        if price is not None and not isinstance(price, float):
            raise TypeError("Optional parameter price not of type float")

        if trigger_price is not None and not isinstance(trigger_price, float):
            raise TypeError(
                "Optional parameter trigger_price not of type float")

        if (product_type == ProductType.Intraday):
            product_type = 'MIS'
        elif product_type == ProductType.Delivery:
            product_type = 'NRML' if (instrument.exchange == 'NFO') else 'CNC'
        elif(product_type == ProductType.CoverOrder):
            product_type = 'CO'
        elif(product_type == ProductType.BracketOrder):
            product_type = None
        # construct order object with order id
        order = {'oms_order_id': str(order_id),
                 'instrument_token': int(instrument.token),
                 'exchange': instrument.exchange,
                 'order_side': transaction_type.value,
                 'product': product_type,
                 'validity': 'DAY',
                 'order_type': order_type.value,
                 'price': price,
                 'trigger_price': 0, #trigger_price,
                 'quantity': quantity,
                 'disclosed_quantity': 0,
                 "execution_type": "REGULAR"
                 }
        return self.__api_call_helper('modify_order', Requests.PUT, None, order)

    def cancel_order(self, order_id, leg_order_id=None, is_co=False):
        """ Cancel single order """
        if (is_co == False):
            if leg_order_id is None:
                ret = self.__api_call_helper('cancelNormalOrder', Requests.DELETE, {'oms_order_id' : order_id,'client_id': self.__login_id,'execution_type': 'REGULAR'}, None)
            else:
                ret = self.__api_call_helper('exitBracketOrder', Requests.DELETE, {
                                             'oms_order_id': order_id, 'leg_order_indicator': leg_order_id,'execution_type': 'REGULAR','client_id': self.__login_id}, None)
        else:
            ret = self.__api_call_helper('exitCoverOrder', Requests.DELETE, {
                                         'oms_order_id': order_id, 'leg_order_indicator': leg_order_id,'execution_type': 'REGULAR','client_id': self.__login_id}, None)
        return ret
        
    def cancel_all_orders(self):  ################## PENDING work
        """ Cancel all orders """
        ret = []
        orders = self.get_order_history()['data']
        if not orders:
            return
        for c_order in orders['pending_orders']:
            if(c_order['product'] == 'BO' and c_order['leg_order_indicator']):
                r = self.cancel_order(
                    c_order['leg_order_indicator'], leg_order_id=c_order['leg_order_indicator'])
            elif(c_order['product'] == 'CO'):
                r = self.cancel_order(
                    c_order['oms_order_id'], leg_order_id=c_order['leg_order_indicator'], is_co=True)
            else:
                r = self.cancel_order(c_order['oms_order_id'])
            ret.append(r)
        return ret

    def subscribe_market_status_messages(self):
        """ Subscribe to market messages """
        return self.__ws_send(json.dumps({"a": "subscribe", "v": [1, 2, 3, 4, 6], "m": "market_status"}))

    def get_market_status_messages(self):
        """ Get market messages """
        return self.__market_status_messages

    def subscribe_exchange_messages(self):
        """ Subscribe to exchange messages """
        return self.__ws_send(json.dumps({"a": "subscribe", "v": [1, 2, 3, 4, 6], "m": "exchange_messages"}))

    def get_exchange_messages(self):
        """ Get stored exchange messages """
        return self.__exchange_messages
    # Manual insert
    def subscribe_open_interest(self,instrument):
        """ Subscribe to exchange messages """
        exchange = self.__exchange_codes[instrument.exchange]
        arr = [[exchange, int(instrument.token)]]
        return self.__ws_send(json.dumps({"a": "subscribe", "v": arr, "m": "open_interest"}))

    def get_open_interest(self):
        """ Get stored exchange messages """
        return self.__open_interest
    
    # Manual Add completed
    def subscribe_order_update(self):
        payload = [self.__login_id, "web"]
        data = json.dumps({'a': 'subscribe', 'v': payload, 'm': "updates"})
        return self.__ws_send(data)
    
    def unsubscribe_order_update(self):
        payload = [self.__login_id, "web"]
        data = json.dumps({'a': 'unsubscribe', 'v': payload, 'm': "updates"})
        return self.__ws_send(data)
        
    def subscribe_position_update(self):
        payload = [self.__login_id, "web"]
        data = json.dumps({'a': 'subscribe', 'v': payload, 'm': "position_updates"})
        return self.__ws_send(data)

    def unsubscribe_position_update(self):
        payload = [self.__login_id, "web"]
        data = json.dumps({'a': 'unsubscribe', 'v': payload, 'm': "position_updates"})
        return self.__ws_send(data)

    def subscribe(self, instrument, live_feed_type):
        """ subscribe to the current feed of an instrument """
        if(type(live_feed_type) is not LiveFeedType):
            raise TypeError(
                "Required parameter live_feed_type not of type LiveFeedType")
        arr = []
        if (isinstance(instrument, list)):
            for _instrument in instrument:
                if not isinstance(_instrument, Instrument):
                    raise TypeError(
                        "Required parameter instrument not of type Instrument")
                exchange = self.__exchange_codes[_instrument.exchange]
                arr.append([exchange, int(_instrument.token)])
                self.__subscribers[_instrument] = live_feed_type
        else:
            if not isinstance(instrument, Instrument):
                raise TypeError(
                    "Required parameter instrument not of type Instrument")
            exchange = self.__exchange_codes[instrument.exchange]
            arr = [[exchange, int(instrument.token)]]
            self.__subscribers[instrument] = live_feed_type
        if(live_feed_type == LiveFeedType.MARKET_DATA):
            mode = 'marketdata'
        elif(live_feed_type == LiveFeedType.COMPACT):
            mode = 'compact_marketdata'
        elif(live_feed_type == LiveFeedType.SNAPQUOTE):
            mode = 'snapquote'
        elif(live_feed_type == LiveFeedType.FULL_SNAPQUOTE):
            mode = 'full_snapquote'
        elif(live_feed_type == LiveFeedType.OI):
            mode = 'open_interest'
        elif(message[0] == WsFrameMode.MARKET_STATUS):
            p = MarketStatus.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            self.__market_status_messages.append(res)
            if(self.__market_status_messages_callback is not None):
                self.__market_status_messages_callback(res)
        elif(message[0] == WsFrameMode.EXCHANGE_MESSAGES):
            p = ExchangeMessage.parse(message[1:]).__dict__
            res = self.__modify_human_readable_values(p)
            self.__exchange_messages.append(res)
            if(self.__exchange_messages_callback is not None):
                self.__exchange_messages_callback(res)
        elif(live_feed_type == LiveFeedType.ORDERUPDATE): # message_type == "OrderUpdateMessage":
                arr = "OrderUpdateMessage"
                mode = "updates"
        data = json.dumps({'a': 'subscribe', 'v': arr, 'm': mode})
        return self.__ws_send(data)

    def unsubscribe(self, instrument, live_feed_type):
        """ unsubscribe to the current feed of an instrument """
        if(type(live_feed_type) is not LiveFeedType):
            raise TypeError(
                "Required parameter live_feed_type not of type LiveFeedType")
        arr = []
        if (isinstance(instrument, list)):
            for _instrument in instrument:
                if not isinstance(_instrument, Instrument):
                    raise TypeError(
                        "Required parameter instrument not of type Instrument")
                exchange = self.__exchange_codes[_instrument.exchange]
                arr.append([exchange, int(_instrument.token)])
                if(_instrument in self.__subscribers):
                    del self.__subscribers[_instrument]
        else:
            if not isinstance(instrument, Instrument):
                raise TypeError(
                    "Required parameter instrument not of type Instrument")
            exchange = self.__exchange_codes[instrument.exchange]
            arr = [[exchange, int(instrument.token)]]
            if(instrument in self.__subscribers):
                del self.__subscribers[instrument]
        if(live_feed_type == LiveFeedType.MARKET_DATA):
            mode = 'marketdata'
        elif(live_feed_type == LiveFeedType.COMPACT):
            mode = 'compact_marketdata'
        elif(live_feed_type == LiveFeedType.SNAPQUOTE):
            mode = 'snapquote'
        elif(live_feed_type == LiveFeedType.FULL_SNAPQUOTE):
            mode = 'full_snapquote'
        elif(live_feed_type == LiveFeedType.OI):
            mode = 'open_interest'
        
        data = json.dumps({'a': 'unsubscribe', 'v': arr, 'm': mode})
        return self.__ws_send(data)

    def get_all_subscriptions(self):
        """ get the all subscribed instruments """
        return self.__subscribers

    def __resubscribe(self):
        market = []
        compact = []
        snap = []
        full = []
        for key, value in self.get_all_subscriptions().items():
            if(value == LiveFeedType.MARKET_DATA):
                market.append(key)
            elif(value == LiveFeedType.COMPACT):
                compact.append(key)
            elif(value == LiveFeedType.SNAPQUOTE):
                snap.append(key)
            elif(value == LiveFeedType.FULL_SNAPQUOTE):
                full.append(key)
        if market:
            self.subscribe(market, LiveFeedType.MARKET_DATA)
        if compact:
            self.subscribe(compact, LiveFeedType.COMPACT)
        if snap:
            self.subscribe(snap, LiveFeedType.SNAPQUOTE)
        if full:
            self.subscribe(full, LiveFeedType.FULL_SNAPQUOTE)

    def get_instrument_by_symbol(self, exchange, symbol):
        """ get instrument by providing symbol """
        # get instrument given exchange and symbol
        exchange = exchange.upper()
        # check if master contract exists
        if exchange not in self.__master_contracts_by_symbol:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_symbol[exchange]
        if symbol not in master_contract:
            logger.warning(
                f"Cannot find symbol {exchange} {symbol} in master contract")
            return None
        return master_contract[symbol]

    def get_instrument_for_fno(self, symbol, expiry_date, is_fut=False, strike=None, is_call=False, exchange='NFO'): ###pending work
        """ get instrument for FNO """
        res = self.search_instruments(exchange, symbol)
        if(res == None):
            return
        matches = []
        for i in res:
            sp = i.symbol.split(' ')
            if(sp[0] == symbol):
                if(i.expiry == expiry_date):
                    matches.append(i)
        for i in matches:
            if(is_fut == True):
                if('FUT' in i.symbol):
                    return i
            else:
                sp = i.symbol.split(' ')
                if((sp[-1] == 'CE') or (sp[-1] == 'PE')):           # Only option scrips
                    if(float(sp[-2]) == float(strike)):
                        if(is_call == True):
                            if(sp[-1] == 'CE'):
                                return i
                        else:
                            if(sp[-1] == 'PE'):
                                return i

    def search_instruments(self, exchange, symbol):
        """ Search instrument by symbol match """
        # search instrument given exchange and symbol
        exchange = exchange.upper()
        matches = []
        #print(self.__master_contracts_by_token)
        # check if master contract exists
        if exchange not in self.__master_contracts_by_token:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_token[exchange]
        for contract in master_contract:
            if (isinstance(symbol, list)):
                for sym in symbol:
                    if sym.lower() in master_contract[contract].symbol.split(' ')[0].lower():
                        matches.append(master_contract[contract])
            else:
                if symbol.lower() in master_contract[contract].symbol.split(' ')[0].lower():
                    matches.append(master_contract[contract])
        return matches

    def get_instrument_by_token(self, exchange, token):
        """ Get instrument by providing token """
        # get instrument given exchange and token
        exchange = exchange.upper()
        token = int(token)
        # check if master contract exists
        if exchange not in self.__master_contracts_by_symbol:
            logger.warning(f"Cannot find exchange {exchange} in master contract. "
                           "Please ensure if that exchange is enabled in your profile and downloaded the master contract for the same")
            return None
        master_contract = self.__master_contracts_by_token[exchange]
        if token not in master_contract:
            logger.warning(
                f"Cannot find symbol {exchange} {token} in master contract")
            return None
        return master_contract[token]

    def get_master_contract(self, exchange):
        """ Get master contract """
        return self.__master_contracts_by_symbol[exchange]

    def __get_master_contract(self, exchange):
        """ returns all the tradable contracts of an exchange
            placed in an OrderedDict and the key is the token
        """
        body = {}
        with open('./stocko/instruments/stocko_instruments.csv', 'r') as file:
            reader = csv.DictReader(file)
            for index, row in enumerate(reader):  # Use `enumerate` to get the row index
                sub = index  # Use the row index as `sub`
                if sub not in body:
                    body[sub] = []
                    
                    if row['exchange'] == exchange:
                        body[sub].append({
                            'code': int(row['exchange_token']) ,
                            'symbol': row['trading_symbol']  ,
                            'expiry': row['expiry'] if row['expiry'] else None,
                            'lotSize': int(row['lot_size']) if row['lot_size'] else 0,
                            'company': row['company_name'],
                            'exchange': row['exchange']
                        })
                    else:
                        pass
                else:
                    pass
        master_contract_by_token = OrderedDict()
        master_contract_by_symbol = OrderedDict()
        for sub in body:
            for scrip in body[sub]:
                if scrip:
                    token = int(scrip['code'])
                    symbol = scrip['symbol']
                    if ('expiry' in scrip)  and scrip['expiry'] != None: 
                        expiry = datetime.strptime(scrip['expiry'], '%d-%b-%Y').date()
                    else:
                        expiry = None
                    lot_size = scrip['lotSize'] if ('lotSize' in scrip) else None
                    name = scrip['company']
                    exch = scrip['exchange']
                    instrument = Instrument(
                        exch, token, symbol, name, expiry, lot_size)
                    master_contract_by_token[token] = instrument
                    master_contract_by_symbol[symbol] = instrument
                else:
                    pass
        
        self.__master_contracts_by_token[exchange] = master_contract_by_token
        self.__master_contracts_by_symbol[exchange] = master_contract_by_symbol
        print(f"Downloaded instruments for {exchange}")

    def __api_call_helper(self, name, http_method, params, data):
        # helper formats the url and reads error codes nicely
        config = self.__service_config
        url = f"{config['host']}{config['routes'][name]}"
        if params is not None:
            url = url.format(**params)
        response = self.__api_call(url, http_method, data)
        if response.status_code != 200:            
            raise requests.HTTPError(response.text)
        return json.loads(response.text)

    def __api_call(self, url, http_method, data):
        # logger.debug('url:: %s http_method:: %s data:: %s headers:: %s', url, http_method, data, headers)        
        r = None
        headers = self.__headers
        if http_method is Requests.POST:
            #r = self.reqsession.post(url, data=json.dumps(data), headers=headers)
            r = requests.post(url, data=json.dumps(data), headers=headers)
        elif http_method is Requests.DELETE:
            r = requests.delete(url, headers=headers)
        elif http_method is Requests.PUT:
            r = requests.put(
                url, data=json.dumps(data), headers=headers)
        elif http_method is Requests.GET:
            r = requests.get(url, headers=headers)        
        return r

    def get_candles(self, exchange, symbol, start_time, end_time, interval=5, is_index=False, time = 'minute'): ###pending work
        exchange = exchange.upper()
        idx = '' if not is_index else '_INDICES'
        divider = 1
        if exchange == 'CDS':
            divider = 1 #1e7
        # symbol = symbol.upper()
        instrument = self.get_instrument_by_symbol(exchange, symbol)
        start_time = int(start_time.timestamp())
        end_time = int(end_time.timestamp())
        if time == 'minute':
            candletype = 1    
        elif time == 'hour':
            candletype = 1    
        elif time == 'day' or time == 'week' or time == 'month' :
            candletype = 3   
        params_tv = {
        'exchange': exchange + idx, #'NFO',
        'token': instrument.token,#35012,
        'candletype': candletype,
        'data_duration': interval,
        'starttime': start_time,
        'endtime': end_time,
        }
        r = requests.get(
            'https://web.stocko.in/api/v1/charts/tdv', params=params_tv, headers=self.__headers)
        data = r.json()
        return self.__format_candles(data, divider) #



    def buy_bo(self, instrument, qty, price, trigger_price, stop_loss_value, square_off_value): #### pending
        data = self.place_order(TransactionType.Buy, instrument, qty,
                                OrderType.StopLossLimit, ProductType.BracketOrder,
                                price=price, trigger_price=trigger_price, stop_loss=stop_loss_value,
                                square_off=square_off_value, order_tag='python-buy-bo')
        if data['status'] == 'success':
            return data['data']['oms_order_id']
        return data.json()

    def sell_bo(self, instrument, qty, price, trigger_price, stop_loss_value, square_off_value):  #### pending
        data = self.place_order(TransactionType.Sell, instrument, qty,
                                OrderType.StopLossLimit, ProductType.BracketOrder,
                                price=price, trigger_price=trigger_price, stop_loss=stop_loss_value,
                                square_off=square_off_value, order_tag='python-sell-bo')
        if data['status'] == 'success':
            return data['data']['oms_order_id']
        return data.json()

    def get_total_m2m(self):
        data = self.get_netwise_positions()
        if data['status'] != 'success':
            return None
        else:
            positions = pd.DataFrame(data['data']['positions'], index=None)
            if positions.empty:
                return 0
            positions['m2m'] = positions['m2m'].str.replace(
                ',', '').astype(float)
            return float(positions['m2m'].sum())

    
    def check_masters(self):
        ############ downloading instrument file if yesterdays
        file_path = './stocko/instruments/stocko_instruments.csv'
        # Get the current date
        current_date = datetime.now().date()
        # Check if the file exists
        if os.path.exists(file_path):
            file_modified_time = os.path.getmtime(file_path)
            file_date = datetime.fromtimestamp(file_modified_time).date()
            # Compare the file date with the current date
            if file_date != current_date:
                print("Instruments File is not from today. Downloading ...")
                self.download_master()
            else:
                pass
                #print("Todays Instrument File found. Download skipped")
        else:
            #print("File does not exist. Please check the file path.")
            self.download_master()

    def download_master(self):
        url = "https://web.stocko.in/api/v1/contract/Compact?info=download"
        destination_folder = Path("./stocko/instruments"  )
        zip_file_name = "Stocko_instruments.zip"  
        zip_file_path = destination_folder/zip_file_name
        renamed_csv_file_name = "Stocko_instruments.csv" 
        renamed_csv_file_path = destination_folder/renamed_csv_file_name

        destination_folder.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, stream=True)

        if response.status_code == 200:
            with open(zip_file_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            print(f"Token file downloaded successfully to {zip_file_path}")

            bl_extracted = False
            try:
                with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
                    zip_file_names = zip_ref.namelist()
                    if zip_file_names:
                        extracted_file_name = zip_file_names[0]
                        zip_ref.extract(extracted_file_name, destination_folder)
                        extracted_file_path = destination_folder/extracted_file_name
                        # Rename the extracted file
                        shutil.move(extracted_file_path, renamed_csv_file_path)
                        bl_extracted = True
                    else:
                        print("No files found in the zip archive.")
            except zipfile.BadZipFile:
                print("The downloaded file is not a valid zip file.")

            if bl_extracted:
                zip_file_path.unlink
        else:
            print(f"Failed to download the file. HTTP Status Code: {response.status_code}")
