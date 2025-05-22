import discord
from discord.ext import commands, tasks
import logging
import asyncio
import json
from datetime import datetime

from .live_service import LiveStockService
from .live_views import StockView
from .constants import UPDATE_INTERVAL

# Load config
with open('config.json') as config_file:
    config = json.load(config_file)
    LIVE_STOCK_CHANNEL_ID = int(config['id_live_stock'])

class LiveStock(commands.Cog):
    def __init__(self, bot):
        if not hasattr(bot, 'live_stock_instance'):
            self.bot = bot
            self.message_id = None
            self.update_lock = asyncio.Lock()
            self.last_update = datetime.utcnow().timestamp()
            self.service = LiveStockService(bot)
            self.stock_view = StockView(bot)
            self.logger = logging.getLogger("LiveStock")
            self._task = None
            
            bot.add_view(self.stock_view)
            bot.live_stock_instance = self

    async def cog_load(self):
        """Called when cog is being loaded"""
        self.live_stock.start()
        self.logger.info("LiveStock cog loaded and task started")

    def cog_unload(self):
        """Called when cog is being unloaded"""
        if self._task and not self._task.done():
            self._task.cancel()
        if hasattr(self, 'live_stock') and self.live_stock.is_running():
            self.live_stock.cancel()
        self.logger.info("LiveStock cog unloaded")

    @tasks.loop(seconds=UPDATE_INTERVAL)
    async def live_stock(self):
        async with self.update_lock:
            try:
                channel = self.bot.get_channel(LIVE_STOCK_CHANNEL_ID)
                if not channel:
                    self.logger.error(f"Could not find channel with ID {LIVE_STOCK_CHANNEL_ID}")
                    return

                products = await self.service.product_manager.get_all_products()
                embed = await self.service.create_stock_embed(products)

                if self.message_id:
                    try:
                        message = await channel.fetch_message(self.message_id)
                        await message.edit(embed=embed, view=self.stock_view)
                        self.logger.debug(f"Updated existing message {self.message_id}")
                    except discord.NotFound:
                        message = await channel.send(embed=embed, view=self.stock_view)
                        self.message_id = message.id
                        self.logger.info(f"Created new message {self.message_id} (old not found)")
                else:
                    message = await channel.send(embed=embed, view=self.stock_view)
                    self.message_id = message.id
                    self.logger.info(f"Created initial message {self.message_id}")

                self.last_update = datetime.utcnow().timestamp()

            except Exception as e:
                self.logger.error(f"Error updating live stock: {e}")

    @live_stock.before_loop
    async def before_live_stock(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    """Setup the LiveStock cog"""
    try:
        await bot.add_cog(LiveStock(bot))
        logging.info(f'LiveStock cog loaded successfully at {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC')
    except Exception as e:
        logging.error(f"Error loading LiveStock cog: {e}")
        raise