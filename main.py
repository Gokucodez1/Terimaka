import discord
from discord.ext import commands
from discord import ui, ButtonStyle, Embed
import asyncio
import json
import sqlite3
from datetime import datetime
from utils import *

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='$', intents=intents)

# Database connection
bot.db_conn = sqlite3.connect('deals.db', check_same_thread=False)
bot.db_cursor = bot.db_conn.cursor()

class RoleView(ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=3600)
        self.channel_id = channel_id
        
    @ui.button(label="Sender", style=ButtonStyle.green)
    async def sender(self, interaction, button):
        deal = load_deal(self.channel_id)
        if not deal:
            return await interaction.response.send_message("Deal expired!", ephemeral=True)
        
        bot.db_cursor.execute(
            "UPDATE deals SET sender_id=? WHERE channel_id=?",
            (interaction.user.id, self.channel_id)
        )
        bot.db_conn.commit()
        
        await interaction.response.send_message(
            embed=Embed(
                description=f"✅ You're now the Sender",
                color=0x00FF00
            ),
            ephemeral=True
        )
        await check_roles_ready(interaction.channel)

    @ui.button(label="Receiver", style=ButtonStyle.blurple)
    async def receiver(self, interaction, button):
        deal = load_deal(self.channel_id)
        if not deal:
            return await interaction.response.send_message("Deal expired!", ephemeral=True)
        
        bot.db_cursor.execute(
            "UPDATE deals SET receiver_id=? WHERE channel_id=?",
            (interaction.user.id, self.channel_id)
        )
        bot.db_conn.commit()
        
        await interaction.response.send_message(
            embed=Embed(
                description=f"✅ You're now the Receiver",
                color=0x00FF00
            ),
            ephemeral=True
        )
        await check_roles_ready(interaction.channel)

async def check_roles_ready(channel):
    deal = load_deal(channel.id)
    if deal and deal[2] and deal[3]:  # Both sender and receiver set
        await channel.send(
            embed=Embed(
                title="Roles Confirmed",
                description=f"Sender: <@{deal[2]}>\nReceiver: <@{deal[3]}>",
                color=0x00FF00
            ),
            view=ConfirmView(channel.id, 'roles')
        )

class ConfirmView(ui.View):
    def __init__(self, channel_id, confirm_type):
        super().__init__(timeout=3600)
        self.channel_id = channel_id
        self.confirm_type = confirm_type

    @ui.button(label="Confirm", style=ButtonStyle.green)
    async def confirm(self, interaction, button):
        deal = load_deal(self.channel_id)
        if not deal:
            return await interaction.response.send_message("Deal expired!", ephemeral=True)
        
        if interaction.user.id not in [deal[2], deal[3]]:
            return await interaction.response.send_message(
                "❌ Only deal participants can confirm!",
                ephemeral=True
            )
        
        if self.confirm_type == 'roles':
            await start_amount_selection(interaction.channel)
        elif self.confirm_type == 'amount':
            await generate_payment_invoice(interaction.channel)
        
        await interaction.response.defer()

async def start_amount_selection(channel):
    await channel.send(
        embed=Embed(
            title="Enter Amount (USD)",
            description="Minimum: $0.10\nExample: `1.50`",
            color=0x5865F2
        )
    )
    
    def check(m):
        amount = validate_amount(m.content)
        return (
            amount is not None and
            m.channel == channel and
            m.author.id == load_deal(channel.id)[2]  # Only sender can set amount
        )

    try:
        msg = await bot.wait_for('message', check=check, timeout=300)
        usd_amount = float(msg.content.replace('$', '').strip())
        ltc_amount = usd_amount / get_live_rate()
        
        bot.db_cursor.execute(
            "UPDATE deals SET amount_usd=?, amount_ltc=? WHERE channel_id=?",
            (usd_amount, ltc_amount, channel.id)
        )
        bot.db_conn.commit()
        
        await channel.send(
            embed=Embed(
                title="Amount Confirmed",
                description=f"${usd_amount:.2f} USD ≈ {ltc_amount:.8f} LTC",
                color=0x00FF00
            ),
            view=ConfirmView(channel.id, 'amount')
        )
        
    except asyncio.TimeoutError:
        await channel.delete()

async def generate_payment_invoice(channel):
    deal = load_deal(channel.id)
    await channel.send(
        embed=Embed(
            title="PAYMENT INVOICE",
            description=(
                f"**Amount:** ${deal[5]:.2f} USD\n"
                f"**Converted:** {deal[4]:.8f} LTC\n"
                "Send to: `" + get_ltc_address() + "`"
            ),
            color=0x5865F2
        ),
        view=InvoiceView()
    )
    
    bot.db_cursor.execute(
        "UPDATE deals SET status='awaiting_payment' WHERE channel_id=?",
        (channel.id,)
    )
    bot.db_conn.commit()

class InvoiceView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Show Address", style=ButtonStyle.green)
    async def address(self, interaction, button):
        await interaction.response.send_message(
            f"```{get_ltc_address()}```",
            ephemeral=False
        )
    
    @ui.button(label="QR Code", style=ButtonStyle.blurple)
    async def qr(self, interaction, button):
        with open('qr.txt') as f:
            qr = f.read().strip()
        await interaction.response.send_message(
            f"QR Code: {qr}",
            ephemeral=False
        )

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.load_extension('cogs.rates')
    await bot.load_extension('cogs.monitor')
    
    bot.db_cursor.execute('''CREATE TABLE IF NOT EXISTS deals
                           (channel_id INT PRIMARY KEY,
                            deal_code TEXT,
                            sender_id INT,
                            receiver_id INT,
                            amount_ltc REAL,
                            amount_usd REAL,
                            start_time TEXT,
                            status TEXT)''')
    bot.db_conn.commit()

@bot.event
async def on_guild_channel_create(channel):
    if channel.category_id == int(bot.config['category_id']):
        deal_code = generate_deal_code()
        await channel.send(
            f"Deal Code: `{deal_code}`\n"
            "Send the other user's Developer ID to start."
        )
        
        bot.db_cursor.execute(
            "INSERT INTO deals VALUES (?, ?, NULL, NULL, NULL, NULL, ?, 'init')",
            (channel.id, deal_code, datetime.now().isoformat())
        )
        bot.db_conn.commit()

@bot.command()
@commands.is_owner()
async def release(ctx, channel_id: int, ltc_address: str):
    """Owner override to release funds"""
    deal = load_deal(channel_id)
    if not deal:
        return await ctx.send("❌ Deal not found!")
    
    if not validate_ltc_address(ltc_address):
        return await ctx.send("❌ Invalid LTC address format!")
    
    try:
        txid = send_ltc(ltc_address, deal[4])
        await ctx.send(
            embed=Embed(
                title="✅ Funds Released (Owner Override)",
                description=(
                    f"**Amount:** {deal[4]:.8f} LTC\n"
                    f"**To:** `{ltc_address}`\n"
                    f"**TXID:** `{txid}`"
                ),
                color=0x00FF00
            )
        )
        
        bot.db_cursor.execute(
            "UPDATE deals SET status='completed' WHERE channel_id=?",
            (channel_id,)
        )
        bot.db_conn.commit()
    except Exception as e:
        await ctx.send(f"❌ Release failed: {str(e)}")

# Load config and run
bot.config = json.load(open('config.json'))
bot.run(bot.config['bot_token'])
