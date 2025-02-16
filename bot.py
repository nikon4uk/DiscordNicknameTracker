import discord
import json
from discord.ext import commands
from discord.ui import View, Button
from dotenv import load_dotenv
import os


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Файл для збереження історії ніків

DATA_FILE = "nickname_history.json"


# Завантаження або ініціалізація файлу


def load_data():

    try:

        with open(DATA_FILE, "r", encoding="utf-8") as file:

            return json.load(file)

    except FileNotFoundError:

        return {}


def save_data(data):

    with open(DATA_FILE, "w", encoding="utf-8") as file:

        json.dump(data, file, indent=4, ensure_ascii=False)


# Завантажуємо історію ніків

nickname_data = load_data()


# Налаштування бота

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents)


# Фіксуємо зміну ніків


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
                "date": str(discord.utils.utcnow().date()),
                "likes": 0,
                "liked_by": [],
            }
        )

        save_data(nickname_data)


# Відправляє історію ніків з кнопками для лайків


@bot.command()
async def history(ctx, member: discord.Member):

    user_id = str(member.id)

    if user_id not in nickname_data or not nickname_data[user_id]["nickname_changes"]:

        await ctx.send(f"❌ {member.mention} ще не змінював нік.")

        return

    for change in nickname_data[user_id]["nickname_changes"]:

        view = LikeView(user_id, change)  # Передаємо зміну ніку у View

        embed = discord.Embed(
            title="📜 Історія ніків",
            description=f"**{change['old']}** → **{change['new']}** ({change['date']})",
            color=discord.Color.blue(),
        )

        await ctx.send(embed=embed, view=view)


# Клас для кнопок лайків


class LikeView(View):

    def __init__(self, user_id, change):

        super().__init__()

        self.change = change

        self.like_button = Button(
            label=f"👍 {self.change['likes']} лайків",
            style=discord.ButtonStyle.green
        )
        self.add_item(self.like_button)
        self.like_button.callback = self.like_button_callback

    async def like_button_callback(self, interaction: discord.Interaction):

        try:
            change = self.change

            user_liked = str(interaction.user.id)

            # Перемикання лайка (додаємо або прибираємо)

            if user_liked in change["liked_by"]:

                change["liked_by"].remove(user_liked)

                change["likes"] -= 1

                message = (
                    f"❌ {interaction.user.mention}, ти прибрав лайк з {change['new']}."
                )

            else:

                change["liked_by"].append(user_liked)

                change["likes"] += 1

                message = (
                    f"✅ {interaction.user.mention}, ти поставив лайк {change['new']}!"
                )

            # Оновлюємо кнопку та базу

            self.like_button.label = f"👍 {change['likes']} лайків"

            save_data(nickname_data)

            await interaction.response.edit_message(view=self)

            await interaction.followup.send(message, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"Помилка: {str(e)}", ephemeral=True)


# Запуск бота
bot.run(f"{TOKEN}")
