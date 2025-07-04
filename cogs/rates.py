import discord
from discord.ext import commands, tasks
from utils import get_live_rate

class ExchangeRates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_rate = None
        self.update_rates.start()

    @tasks.loop(minutes=5)
    async def update_rates(self):
        new_rate = get_live_rate()
        if self.current_rate != new_rate:
            self.current_rate = new_rate
            channel = self.bot.get_channel(int(self.bot.config['rate_channel_id']))
            await channel.send(f"💱 1 LTC = ${new_rate:.2f}")

    @update_rates.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ExchangeRates(bot))
