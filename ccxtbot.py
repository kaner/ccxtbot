#!/usr/bin/python3

import ccxt
import datetime
from dateutil.relativedelta import relativedelta
import plotly.plotly as py
import plotly.graph_objs as go

#import matplotlib
#matplotlib.use("Agg") # Prevent DISPLAY error
#import matplotlib.pyplot as plt

class OhlcvData:
    def __init__(self, rawDataBlock):
        if len(rawDataBlock) != 6:
            print("Bad data block: ", rawDataBlock)
            return
        self.timestamp = datetime.datetime.utcfromtimestamp(rawDataBlock[0]/1000)
        self.openPrice = rawDataBlock[1]
        self.highPrice = rawDataBlock[2]
        self.lowPrice = rawDataBlock[3]
        self.closePrice = rawDataBlock[4]
        self.typicalPrice = calculateTypicalPrice(self.highPrice, self.lowPrice, self.closePrice)
        self.ohlcAverage = calculateOHLCAverage(self.openPrice, self.highPrice, self.lowPrice, self.closePrice)
        self.volume = rawDataBlock[5]

    def __str__(self):
        return "Timestamp: " + str(self.timestamp) + " " + \
                "Open price: " + str(self.openPrice) + " " + \
                "high price: " + str(self.highPrice) + " " + \
                "low price: " + str(self.lowPrice) + "  " + \
                "close price: " + str(self.closePrice) + " " + \
                "Typical price: " + str(self.typicalPrice) + " " + \
                "Volume: " + str(self.volume)

class SimpleMA:
    def __init__(self, dataChunk):
        self.nDays = len(dataChunk)
        self.timestamp = dataChunk[-1].timestamp
        self.typicalPriceMA = sum(d.typicalPrice for d in dataChunk) / len(dataChunk)
        self.ohlcMA = sum(d.ohlcAverage for d in dataChunk) / len(dataChunk)
        self.highMA = sum(d.highPrice for d in dataChunk) / len(dataChunk)
        self.lowMA = sum(d.lowPrice for d in dataChunk) / len(dataChunk)
        self.openMA = sum(d.openPrice for d in dataChunk) / len(dataChunk)
        self.closeMA = sum(d.closePrice for d in dataChunk) / len(dataChunk)

    def __str__(self):
        return "Number of Days: " + str(self.nDays) + " " \
                "Timestamp: " + str(self.timestamp) + " " \
                "Typical Price Moving Average: " + str(self.typicalPriceMA) + " " \
                "OHLC Moving Average: " + str(self.ohlcMA) + " " \
                "High Moving Average: " + str(self.highMA) + " " \
                "Low Moving Average: " + str(self.lowMA) + " " \
                "Open Moving Average: " + str(self.openMA) + " " \
                "close Moving Average: " + str(self.closeMA)

class ExpotentialMA:
    def __init__(self, dataPoint, previousEMA, nDays):
        self.nDays = nDays
        self.k = round((2 / (nDays + 1)), 4) # Round k by 4 digits
        self.timestamp = dataPoint.timestamp
        self.price = dataPoint.closePrice
        # Calculate EMA according to https://www.tradingview.com/wiki/Moving_Average#Exponential_Moving_Average_.28EMA.29
        #self.ema = (self.price * self.k) + (previousEMA * (1-self.k))
        # Try another one according to https://sciencing.com/calculate-exponential-moving-averages-8221813.html
        self.ema = ((self.price - previousEMA) * self.k) + previousEMA

    def __str__(self):
        return "Numer of Days: " + str(self.nDays) + " " \
                "K: " + str(self.k) + " " \
                "Timestamp: " + str(self.timestamp) + " " \
                "Price: " + str(self.price) + " " \
                "EMA: " + str(self.ema)

def _mkUnixMillisTimeStamp(dateTimeStamp):
    return int(dateTimeStamp.timestamp() * 1000)

def _getOneOClockStamp(goBackDays=0):
    oneOClock = datetime.datetime.utcnow().replace(hour=1,minute=0,second=0,microsecond=0)
    oneOClock = oneOClock + relativedelta(days=-goBackDays)
    if goBackDays == 0 and datetime.datetime.utcnow() < oneOClock: # We're before 1 o'clock
        oneOClock = oneOClock + relativedelta(days=-1)
    return _mkUnixMillisTimeStamp(oneOClock)

def _transformRawOhlcvData(data):
    ohlcvData = []
    for i in data:
        ohlcvData.append(OhlcvData(i))

    return ohlcvData

def fetchCandleData(x, startTimeStamp):
    rawData = x.fetchOhlcv('BTC/USD', '1d', startTimeStamp)
    if not rawData:
        print("Failed to get rawData from exchange")
        return None

    # Check if we got the full bag
    if rawData[0][0] != startTimeStamp:
        print("Wrong start time: ", rawData[0][0])
        return None

    todayOneOClock = _getOneOClockStamp()
    if rawData[-1][0] != todayOneOClock:
        print("Didn't get the full bag, fetching more..")
        # TODO: Calculate +24h on top of the last received timestamp
        rawData = rawData + fetchCandleData(x, rawData[-1][0])

    # Transform the raw data into useful structures
    ohlcvData = _transformRawOhlcvData(rawData)

    return ohlcvData

# Calculate typical price according to TA.pdf, page 170
def calculateTypicalPrice(high, low, close):
    return (high + low + close)/3

# Calculate OHLC average according to https://www.thebalance.com/average-of-the-open-high-low-and-close-1031216
def calculateOHLCAverage(o, h, l, c):
    return (o + h + l + c)/4

def calculateSMAForData(data, maDayCount):
    sma = []
    # Look through array in maDayCount chunks, from beginning to end
    for i in range(0, (len(data)-maDayCount)):
        sma.append(SimpleMA(data[i:i+maDayCount]))
    return sma

# Calculate EMA according to http://www.dummies.com/personal-finance/investing/stocks-trading/how-to-calculate-exponential-moving-average-in-trading/
def calculateEMAForData(data, emaDayCount):
    ema = []
    sma = SimpleMA(data[0:emaDayCount-1]) # Use SMA to get the first data point
    previousEMA = sma.closeMA
    for d in data[emaDayCount:]:
        currentEMA = ExpotentialMA(d, previousEMA, emaDayCount)
        ema.append(currentEMA)
        previousEMA = currentEMA.ema # Prepare next round
    return ema

def findTradingSignals(data):
    maList = calculateSMAForData(data, 10)
    emaList = calculateEMAForData(data, 10)
    return maList, emaList

def createPlot(data, maList):
    trace0 = go.Candlestick(x=[d.timestamp for d in data],
                            open=[d.openPrice for d in data],
                            high=[d.highPrice for d in data],
                            low=[d.lowPrice for d in data],
                            close=[d.closePrice for d in data])
    closeMA = go.Scatter(x=[ma.timestamp for ma in maList],
                         y=[ma.closeMA for ma in maList])
    plotData = [trace0, closeMA]
    py.iplot(plotData, filename='ohlc_candlestick')

#def createPlot(data, maList):
#    closeMAArray = [ma.closeMA for ma in maList]
#    closePriceArray = [d.closePrice for d in data]
#    plt.plot(closeMAArray, "r-", closePriceArray, "b-")
#    plt.savefig("/var/www/html/kaner/closeMA.png")

def main():
    goBackDays = 30
    finex = ccxt.bitfinex()
    print("Trying to get %d days worth of data from %s" % (goBackDays, finex.name))
    data = fetchCandleData(finex, _getOneOClockStamp(goBackDays))
    maList, emaList = findTradingSignals(data)
    for ma in emaList:
       print(ma)
    #createPlot(data, maList)

if __name__ == '__main__':
    main()
