import logging
from stocko import AlphaTrade, LiveFeedType, TransactionType, OrderType, ProductType, WsFrameMode, wsclient
import config
from threading import Thread
import concurrent.futures

from datetime import datetime, timedelta
import datetime as dt
import time, sys
from time import sleep
import warnings
warnings.filterwarnings("ignore")

#logging.basicConfig(filename="./logexcel.txt", level=logging.DEBUG,format="%(asctime)s %(message)s")
#logging.debug("Debug logging started...")
#logging.basicConfig(level=logging.DEBUG)
api=None

def Stocko_login():
    global api
    isConnected = 0
    try:    
        api = AlphaTrade(login_id=config.login_id, password=config.password, totp=config.Totp, client_secret = config.client_secret, master_contracts_to_download=['NSE','NFO','BFO'])        
        print(f"{datetime.now().time()} : Logged in successfully")
        isConnected = 1
    except Exception as e:
        print(f"{datetime.now().time()} : Login failed. Resolve issue and retry..error is:: {e}")
        sys.exit()    
    return isConnected

socket_opened = False
SYMBOLDICT = {}
live_data = {}
def logwritter(msg, filename='log.log'):
    out = datetime.now().strftime("\n%Y%m%d,%H:%M:%S.%f")[:-2]+" : "+str(msg)
    open(filename, 'a').write(out)


def socket():        
    def event_handler_quote_update(inmessage):
        print(inmessage)
        global live_data
        global SYMBOLDICT        
        fields = ['token', 'ltp', 'pc', 'close', 'open', 'high', 'low', 'volume', 'ltq', 'ltp','best_bid_price','best_ask_price','atp','oi','ap']            
        message = { field: inmessage[field] for field in set(fields) & set(inmessage.keys())}
        key = inmessage['exchange'] + '|' + inmessage['instrument'][2]
        if key in SYMBOLDICT:
            symbol_info =  SYMBOLDICT[key]
            symbol_info.update(message)
            SYMBOLDICT[key] = symbol_info
            live_data[key] = symbol_info
        else:
            SYMBOLDICT[key] = message
            live_data[key] = message
            
        print(f"quote updated ")
        #print(SYMBOLDICT)
        print(live_data)
    def open_callback():
        global socket_opened
        socket_opened = True
        print("Websocket opened!")
        subs_lst=[]

    api.start_websocket(subscribe_callback=event_handler_quote_update,
                          socket_open_callback=open_callback,
                          run_in_background=True)
    while(socket_opened==False):
        pass
    #api.subscribe(api.get_instrument_by_symbol('NSE', 'TATASTEEL-EQ'), LiveFeedType.MARKET_DATA)
    #sleep(3)
    

def strategy():
    logwritter("Starting Bot......")
    try:
        print("Starting Websocket................................................................")
        socket()
        #sleep(3)
    except Exception as err:
        print("Websocket Connection Failed for trading bot. Exiting..")
        print(f"An Exception: {err} has occured in the program.")
        sys.exit()

def place_order(exchange: str, symbol: str, qty: int, BS: str):
    ordid = 0
    try:
        if BS == "SELL":
            t_type = TransactionType.Sell
        else:
            t_type = TransactionType.Buy
        ordid=api.place_order(transaction_type = t_type,
                     instrument = api.get_instrument_by_symbol(exchange, symbol),
                     quantity = qty,
                     order_type = OrderType.Market,
                     product_type = ProductType.Delivery,
                     price = 00.0,
                     trigger_price = None,
                     stop_loss = None,
                     square_off = None,
                     trailing_sl = None,
                     is_amo = False)
    except Exception as Er:
        print(f"Error: {Er}")
    return ordid

            
if __name__ == '__main__':
    try:
        print("Running Stocko app..")
        if(Stocko_login() == 1 ): 
            idx=api.get_instrument_by_symbol('NFO', 'NIFTY25JANFUT')
            stk=api.get_instrument_by_symbol('NSE', 'RELIANCE-EQ')
            print(idx)
            print(stk) 
            print("Scrip info :-")
            scrip_info = api.get_scrip_info(idx)
            print(scrip_info)
 
            print("Profile :-")
            profile = api.get_profile()
            print(profile)
            
            print("Balance :-")
            bal=api.get_balance() 
            print(bal)

            print("cancel order :-")
            cancel= api.cancel_order(5200001)
            print(cancel)

            
            print("Demat holdings :-")
            holdings= api.get_dematholdings()
            print(holdings)
            print("Tradeboook :-")
            tradebook= api.get_tradebook()
            print(tradebook)

            print("Orderbook completed :-")
            ordbook= api.get_orderbook(pending=False)
            print(ordbook)

            print("Orderbook pendings :-")
            ordbook= api.get_orderbook(pending=True)
            print(ordbook)

            print("Orderbook default (pending) :-")
            ordbook= api.get_orderbook()
            print(ordbook)

            print("Subscribed exchanges :-")
            enabled_exchanges= api.get_exchanges()
            print(enabled_exchanges)

            print("Live netpositions :-")
            day_pos = api.fetch_live_positions()
            print(day_pos)

            print("Historical netpositions :-")
            net_pos= api.fetch_netwise_positions()
            print(net_pos)

            print("Order status :-")
            ord_hist= api.get_order_history(order_id='241228000000057')
            print(ord_hist)


            strategy()          
            while(socket_opened==False):
                print(socket_opened)
                pass
            print("Connected to WebSocket...")
            sleep(1)

            # subscribe to websocket
            Token = api.get_instrument_by_symbol("NFO","PFC25JANFUT") 
            print(Token)
            api.subscribe(Token, LiveFeedType.MARKET_DATA)        
            sleep(1)

            #Cautiously Place market order - 
            #ord1=place_order('NSE','IDEA-EQ', 1, "SELL")
            #print("\n\nOrder placed :- ",ord1)            
        else:
            print("Credential is not correct")
            sys.exit()    
    except( KeyboardInterrupt, SystemExit ):
        logwritter( "Keyboard Interrupt. EXITING ...." )    
        print( "Keyboard Interrupt. EXITING ...." )    
        sys.exit()
    