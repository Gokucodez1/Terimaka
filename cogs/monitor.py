import discord
from discord.ext import commands, tasks
from utils import load_deal
from sochain import check_payment

class PaymentMonitor(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monitor_payments.start()

    @tasks.loop(seconds=30)
    async def monitor_payments(self):
        cursor = self.bot.db_conn.cursor()
        cursor.execute("SELECT channel_id, amount_ltc FROM deals WHERE status='awaiting_payment'")
        for channel_id, amount_ltc in cursor.fetchall():
            payment = check_payment(amount_ltc)
            if payment:
                channel = self.bot.get_channel(channel_id)
                await channel.send(
                    f"✅ Payment detected! TXID: `{payment['txid']}`",
                    embed=discord.Embed(
                        description=f"Amount: {payment['amount']} LTC\nConfirmations: {payment['confirmations']}/6",
                        color=0x00FF00
                    )
                )

async def setup(bot):
    await bot.add_cog(PaymentMonitor(bot))
