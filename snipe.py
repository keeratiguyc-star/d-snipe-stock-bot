import os
import threading
import discord
from discord.ext import commands
from flask import Flask
import yfinance as yf
from alpha_vantage.timeseries import TimeSeries
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return "Discord Bot is running!"

# ตั้งค่า Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# API Keys - ใส่ของคุณเอง
ALPHA_VANTAGE_API_KEY = os.getenv("API_KEY") # จาก alphavantage.co
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")  # จาก Discord Developer Portal

@bot.event
async def on_ready():
    print(f'{bot.user} has landed and is ready to snipe stocks!')

@bot.command(name='snipe')
async def snipe_stock(ctx, symbol: str):
    symbol = symbol.upper()
    embed = discord.Embed(title=f"📈 ข้อมูลหุ้น {symbol}", color=0x00ff00)
    embed.set_thumbnail(url=f"https://finance.yahoo.com/quote/{symbol}/profile?p={symbol}")
    
    try:
        # ดึงข้อมูลจาก yfinance
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")
        
        if not info or info.get('symbol') != symbol:
            embed.description = f"❌ ไม่พบข้อมูลหุ้น {symbol} ลองเช็คชื่อ ticker ใหม่!"
            await ctx.send(embed=embed)
            return
        
        # ข้อมูลบริษัท
        company_name = info.get('longName', 'N/A')
        exchange = info.get('exchange', 'N/A')
        embed.description = f"{company_name} ({exchange})"
        
        # ข้อมูลราคาและการเคลื่อนไหว
        current_price = info.get('currentPrice', 'N/A')
        previous_close = info.get('previousClose', 'N/A')
        open_price = info.get('open', 'N/A')
        day_high = info.get('dayHigh', 'N/A')
        day_low = info.get('dayLow', 'N/A')
        
        change = current_price - previous_close if current_price != 'N/A' and previous_close != 'N/A' else 0
        change_percent = (change / previous_close * 100) if previous_close != 'N/A' and previous_close != 0 else 0
        
        price_field = (
            f"ราคาปัจจุบัน: ${current_price:.4f}\n"
            f"เปลี่ยนแปลง: {change:+.4f} ({change_percent:+.4f}%)\n"
            f"ราคาเปิด: ${open_price:.4f}\n"
            f"สูงสุดวันนี้: ${day_high:.4f}\n"
            f"ต่ำสุดวันนี้: ${day_low:.4f}"
        )
        embed.add_field(name="💰 ราคาและการเคลื่อนไหว", value=price_field, inline=False)
        
        # ข้อมูลการซื้อขาย
        volume = hist['Volume'].iloc[-1] if not hist.empty else 'N/A'
        try:
            ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')
            quote_data, _ = ts.get_quote_endpoint(symbol=symbol)
            av_volume = quote_data['05. volume'].iloc[0] if not quote_data.empty else volume
            volume = av_volume if av_volume != 'N/A' else volume
        except Exception:
            pass
        
        trading_field = (
            f"ปริมาณซื้อขาย: {volume:,}\n"
            f"วันที่ล่าสุด: {datetime.datetime.now().strftime('%Y-%m-%d')}\n"
            f"ราคาปิดก่อนหน้า: ${previous_close:.4f}"
        )
        embed.add_field(name="📊 การซื้อขาย", value=trading_field, inline=False)
        
        # ข้อมูลบริษัท
        industry = info.get('industry', 'N/A')
        market_cap = info.get('marketCap', 'N/A')
        market_cap = f"${market_cap:,.0f}" if market_cap != 'N/A' else 'N/A'
        pe_ratio = info.get('trailingPE', 'None')
        eps = info.get('trailingEps', 'N/A')
        dividend_yield = info.get('dividendYield', 'None')
        dividend_yield = f"{dividend_yield * 100:.2f}%" if dividend_yield != 'None' else 'None'
        
        company_field = (
            f"อุตสาหกรรม: {industry}\n"
            f"มูลค่าตลาด: {market_cap}\n"
            f"P/E Ratio: {pe_ratio if pe_ratio != 'None' else 'None'}\n"
            f"EPS: ${eps:.2f}\n"
            f"Dividend Yield: {dividend_yield}"
        )
        embed.add_field(name="🏢 ข้อมูลบริษัท", value=company_field, inline=False)
        
        # ช่วง 52 สัปดาห์
        week52_high = info.get('fiftyTwoWeekHigh', 'N/A')
        week52_low = info.get('fiftyTwoWeekLow', 'N/A')
        week52_field = (
            f"สูงสุด 52 สัปดาห์: ${week52_high:.2f}\n"
            f"ต่ำสุด 52 สัปดาห์: ${week52_low:.2f}"
        )
        embed.add_field(name="📅 ช่วง 52 สัปดาห์", value=week52_field, inline=False)
        
        # การคาดการณ์เป้าราคานักวิเคราะห์
        rating = info.get('recommendationMean', 'N/A')
        rating_text = "ไม่มีคำแนะนำ"
        if rating != 'N/A':
            rating_value = float(rating)
            if rating_value <= 2.0:
                rating_text = "ซื้อ"
            elif rating_value <= 3.5:
                rating_text = "ถือ"
            else:
                rating_text = "ขาย"
        try:
            targets = ticker.analyst_price_targets
            if targets and targets.get('mean', 'N/A') != 'N/A':
                mean_target = targets.get('mean', 'N/A')
                low_target = targets.get('low', 'N/A')
                high_target = targets.get('high', 'N/A')
                analyst_field = (
                    f"การให้คะแนนโดยรวม: {rating_text} (คะแนน: {rating:.1f}/5.0)\n"
                    f"เป้าราคาเฉลี่ย: ${mean_target:.3f}\n"
                    f"เป้าราคาต่ำสุด: ${low_target:.3f}\n"
                    f"เป้าราคาสูงสุด: ${high_target:.3f}"
                )
            else:
                analyst_field = (
                    f"การให้คะแนนโดยรวม: {rating_text} (คะแนน: {rating if rating != 'N/A' else 'N/A'}/5.0)\n"
                    f"เป้าราคาเฉลี่ย: ไม่มีข้อมูล\n"
                    f"เป้าราคาต่ำสุด: ไม่มีข้อมูล\n"
                    f"เป้าราคาสูงสุด: ไม่มีข้อมูล"
                )
        except Exception:
            analyst_field = (
                f"การให้คะแนนโดยรวม: {rating_text} (คะแนน: {rating if rating != 'N/A' else 'N/A'}/5.0)\n"
                f"เป้าราคาเฉลี่ย: ไม่สามารถดึงข้อมูลได้\n"
                f"เป้าราคาต่ำสุด: ไม่สามารถดึงข้อมูลได้\n"
                f"เป้าราคาสูงสุด: ไม่สามารถดึงข้อมูลได้"
            )
        embed.add_field(name="🔮 การคาดการณ์เป้าราคาหุ้นจากการวิเคราะห์", value=analyst_field, inline=False)
        
        # Footer
        embed.set_footer(text=f"ข้อมูลจาก Yahoo Finance & Alpha Vantage | อัพเดทล่าสุด: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        embed.description = f"❌ เกิดข้อผิดพลาด: {str(e)}\nลองเช็คชื่อหุ้นหรือ API key ใหม่!"
        await ctx.send(embed=embed)

def run_flask():
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 10000)))

# รันบอท
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    bot.run(DISCORD_TOKEN)