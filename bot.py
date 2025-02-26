import discord
import json
from discord.ext import commands
from discord.ui import Select, View, Button
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

PER_PAGE = 10
# File for saving nickname history
DATA_FILE = os.getenv("FILE_PATH")


# Load or initialize the file
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


# Load nickname history
nickname_data = load_data()

# Bot configuration
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)


# Track nickname changes
@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        user_id = str(after.id)

        if user_id not in nickname_data:
            nickname_data[user_id] = {"nickname_changes": []}

        nickname_data[user_id]["nickname_changes"].append(
            {
                "old": before.nick if before.nick else after.name,
                "new": after.nick if after.nick else after.name,
                "date": str(discord.utils.utcnow().strftime("%Y-%m-%d %H:%M")),
                "likes": 0,
                "liked_by": [],
            }
        )

        save_data(nickname_data)


class NicknameHistoryView(View):
    def __init__(self, user_id: str, sort_by="date", page_size=PER_PAGE):
        super().__init__()
        self.user_id = user_id
        self.data = load_data()
        self.nickname_changes = self.data.get(user_id, {}).get("nickname_changes", [])

        self.page_size = page_size
        self.current_page = 0
        self.sort_by = sort_by
        self.sort_nicknames()

        # Pagination buttons
        self.prev_page = discord.ui.Button(
            label="⬅️", style=discord.ButtonStyle.gray, disabled=True
        )
        self.next_page = discord.ui.Button(
            label="➡️",
            style=discord.ButtonStyle.gray,
            disabled=(len(self.nickname_changes) <= page_size),
        )
        self.sort_button = discord.ui.Button(
            label="🔀 Сортувати: Дата", style=discord.ButtonStyle.blurple
        )

        self.prev_page.callback = self.prev_page_callback
        self.next_page.callback = self.next_page_callback
        self.sort_button.callback = self.toggle_sorting

        self.add_item(self.prev_page)
        self.add_item(self.next_page)
        self.add_item(self.sort_button)

        # Dropdown menu for likes
        self.like_select = Select(placeholder="Постав лайк нікнейму!", options=[])
        self.like_select.callback = self.like_select_callback

        self.update_select_options()
        self.add_item(self.like_select)

    def sort_nicknames(self):
        """Sort nicknames by date or likes"""
        if self.sort_by == "date":
            self.nickname_changes.sort(key=lambda x: x["date"], reverse=True)
        else:
            self.nickname_changes.sort(key=lambda x: x["likes"], reverse=True)

    async def toggle_sorting(self, interaction: discord.Interaction):
        """Toggle sorting between date and likes"""
        self.sort_by = "likes" if self.sort_by == "date" else "date"
        self.sort_button.label = "🔀 Сортувати: " + (
            "Лайки" if self.sort_by == "likes" else "Дата"
        )
        self.sort_nicknames()
        self.current_page = 0
        self.update_select_options()
        await self.update_message(interaction)

    def update_select_options(self):
        """Update dropdown menu for likes"""
        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_nicknames = self.nickname_changes[start_idx:end_idx]

        self.like_select.options = [
            discord.SelectOption(
                label=f"{change['new']} ({change['likes']} лайків) [{change['date']}]",
                value=str(idx),
            )
            for idx, change in enumerate(page_nicknames, start=start_idx)
        ]

    async def prev_page_callback(self, interaction: discord.Interaction):
        """Switch to the previous page"""
        if self.current_page > 0:
            self.current_page -= 1
            self.update_select_options()
            await self.update_message(interaction)

    async def next_page_callback(self, interaction: discord.Interaction):
        """Switch to the next page"""
        if self.current_page < (len(self.nickname_changes) - 1) // self.page_size:
            self.current_page += 1
            self.update_select_options()
            await self.update_message(interaction)

    async def like_select_callback(self, interaction: discord.Interaction):
        """Add or remove like from the selected nickname"""
        selected_index = int(self.like_select.values[0])
        change = self.nickname_changes[selected_index]
        user_id = str(interaction.user.id)

        if user_id in change["liked_by"]:
            change["liked_by"].remove(user_id)
            change["likes"] -= 1
            message = (
                f"❌ {interaction.user.mention}, ти прибрав лайк з {change['new']}."
            )
        else:
            change["liked_by"].append(user_id)
            change["likes"] += 1
            message = (
                f"✅ {interaction.user.mention}, ти поставив лайк {change['new']}!"
            )

        self.data[self.user_id]["nickname_changes"] = self.nickname_changes
        save_data(self.data)

        self.sort_nicknames()
        self.update_select_options()

        # Update message text
        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_nicknames = self.nickname_changes[start_idx:end_idx]

        message_text = "**📜 Історія ніків:**\n" + "\n".join(
            [
                f"🔹 {change['old']} → **{change['new']}** ({change['likes']} лайків) [{change['date']}]"
                for change in page_nicknames
            ]
        )

        await interaction.response.edit_message(content=message_text, view=self)
        await interaction.followup.send(message, ephemeral=True)

    async def update_message(self, interaction: discord.Interaction):
        """Update message text and button states"""
        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_nicknames = self.nickname_changes[start_idx:end_idx]

        message_text = "**📜 Історія ніків:**\n" + "\n".join(
            [
                f"🔹 {change['old']} → **{change['new']}** ({change['likes']} лайків) [{change['date']}]"
                for change in page_nicknames
            ]
        )

        self.prev_page.disabled = self.current_page == 0
        self.next_page.disabled = (
            self.current_page >= (len(self.nickname_changes) - 1) // self.page_size
        )

        await interaction.response.edit_message(content=message_text, view=self)


@bot.command()
async def wholike(ctx, *, nickname: str = None):
    data = load_data()
    user_id = str(ctx.author.id)

    # Delete previous bot messages
    async for message in ctx.channel.history(limit=10):
        if not message.pinned:
            await message.delete()
            await asyncio.sleep(0.2)

    # Check if the user has nickname changes
    if user_id not in data or not data[user_id].get("nickname_changes"):
        await ctx.send("❌ У тебе немає змін нікнейму!")
        return

    # If a nickname is specified, search for it
    if nickname:
        found_nickname = None

        for user_data in data.values():
            for change in user_data["nickname_changes"]:
                # Compare with the exact nickname
                if change["new"].lower() == nickname.lower():
                    found_nickname = change
                    break

        if not found_nickname:
            await ctx.send(f"❌ Нікнейм `{nickname}` не знайдено.")
            return

        # Likes for the found nickname
        liker_list = [f"<@{uid}>" for uid in found_nickname["liked_by"]]
        message = f"**❤️ Хто лайкнув `{nickname}`:**\n" + (
            ", ".join(liker_list) if liker_list else "Ніхто 😢"
        )
    else:
        # If no nickname is specified, show all nickname changes with likes
        all_likes = []

        for change in data[user_id]["nickname_changes"]:
            if change["likes"] > 0:  # Check for likes
                liker_list = [f"<@{uid}>" for uid in change["liked_by"]]
                all_likes.append(
                    f"🔹 `{change['new']}` ({change['likes']} лайків) - {', '.join(liker_list) if liker_list else 'Ніхто'}"
                )

        if all_likes:
            message = "**❤️ Твої лайки:**\n" + "\n".join(all_likes)
        else:
            message = "❌ Ніхто тебе не лайкнув 😢"

    await ctx.send(message)


@bot.command(aliases=["fetchall", "fa"])
async def fetch_audit_nicknames(ctx):
    """Fetch nickname change history from the server audit log"""
    guild = ctx.guild
    nickname_changes = []

    # Get audit log entries
    async for entry in guild.audit_logs(action=discord.AuditLogAction.member_update):
        if isinstance(entry.target, discord.Member):
            # Check for changes
            if hasattr(entry.changes, "before") and hasattr(entry.changes, "after"):
                old_nick = (
                    entry.changes.before.nick
                    if hasattr(entry.changes.before, "nick")
                    else entry.target.name
                )
                new_nick = (
                    entry.changes.after.nick
                    if hasattr(entry.changes.after, "nick")
                    else entry.target.name
                )

                # Add changes to the list if nicknames differ
                if old_nick != new_nick:
                    nickname_changes.append(
                        {
                            "user_id": str(entry.target.id),
                            "old": old_nick,
                            "new": new_nick,
                            "date": str(entry.created_at.strftime("%Y-%m-%d %H:%M")),
                            "likes": 0,
                            "liked_by": [],
                        }
                    )

    # Save changes to the data structure
    for change in nickname_changes:
        user_id = change["user_id"]
        if user_id not in nickname_data:
            nickname_data[user_id] = {"nickname_changes": []}
        nickname_data[user_id]["nickname_changes"].append(change)

    save_data(nickname_data)
    await ctx.send("Історія змін ніків була успішно отримана з журналу аудиту.")


# Sends nickname history with like buttons
@bot.command(aliases=["h"])
async def history(ctx, user: discord.User = None):
    """Displays the nickname change history of a user"""
    target_user = user or ctx.author  # If no user is specified, show the author's history
    user_id = str(target_user.id)
    data = load_data()

    # Delete previous bot messages
    async for message in ctx.channel.history(limit=10):
        if not message.pinned:
            await message.delete()
            await asyncio.sleep(0.2)

    if user_id not in data or not data[user_id].get("nickname_changes"):
        await ctx.send(f"❌ У {target_user.mention} немає змін нікнейму!")
        return

    nickname_changes = data[user_id]["nickname_changes"]

    sorted_nicknames = sorted(nickname_changes, key=lambda x: x["date"], reverse=True)

    message_text = f"**📜 Історія ніків {target_user.mention}:**\n" + "\n".join(
        [
            f"🔹 {change['old']} → **{change['new']}** ({change['likes']} лайків) [{change['date']}]"
            for change in sorted_nicknames[:PER_PAGE]
        ]
    )

    view = NicknameHistoryView(user_id)
    await ctx.send(message_text, view=view)

# Run the bot
bot.run(f"{TOKEN}")
