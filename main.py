"""
This script implements a Discord bot using the nextcord library. The bot allows users to play a word-based game called Wordbomb.
"""

import nextcord
from nextcord.ext import commands
from nextcord.ui import Button, View
import random, asyncio
import signal
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN: str = os.getenv('DISCORD_TOKEN')
bot = commands.Bot(command_prefix="!", intents=nextcord.Intents.all())

global games
games = {}

class Data:
    """
    A class to handle the word data for the game.

    Attributes:
        words (set): A set of valid words loaded from the 'words.txt' file.
    """
    with open('words.txt', 'r') as f: words = set(word.strip().lower() for word in f.readlines())

class Player:
    """
    Represents a player in the Wordbomb game.

    Attributes:
        id (int): The unique identifier of the player.
        status (str): The status of the player (e.g., 'Player', 'Owner').
        hearts (int): The number of lives the player has.
    """
    def __init__(self, id: int, status: str = "Player") -> None:
        self.id = id
        self.status = status
        self.hearts = 2

class wordbombGame:
    """
    Represents a Wordbomb game instance.

    Attributes:
        userID (int): The ID of the user who created the game.
        channelID (int): The ID of the channel where the game is hosted.
        gameID (int): A unique identifier for the game.
        stage (int): The current stage of the game.
        plays (int): The number of plays made in the game.
        countdown (int): The countdown timer before the game starts.
        currentPlayerIndex (int): The index of the current player in the players list.
        timeRemaining (int): The time remaining for the current turn.
        players (list[Player]): A list of players in the game.
        used_words (set): A set of words that have already been used.
        currentStarter (str): The current starting letter for the game.
        running (bool): Whether the game is currently running.
        responded (bool): Whether the current player has responded.
        singleplayer (bool): Whether the game is in single-player mode.
        response (nextcord.Message): The last response message from a player.
        join_msg (nextcord.Message): The message for players to join the game.
        main_msg (nextcord.Message): The main game message.
        timeStageRelation (dict[int, int]): A mapping of stages to time limits.
        stageStartersRelation (dict[int, list]): A mapping of stages to starting letters.
    """
    def __init__(self, userID: int, channelID: int) -> None:
        self.userID: int = userID
        self.channelID: int = channelID
        self.gameID: int = random.randint(1, 999999)
        self.stage: int = 1
        self.plays: int = 0
        self.countdown: int = 10
        self.currentPlayerIndex: int = 0
        self.timeRemaining: int = 8
        
        self.players: list[Player] = [Player(userID, "Owner")]
        self.used_words: set = set()
        self.currentStarter: str = random.choice(Data.easy_starters)
        
        self.running: bool = True
        self.responded: bool = False
        self.singleplayer: bool = False
        
        self.response: nextcord.Message = None
        self.join_msg: nextcord.Message = None
        self.main_msg: nextcord.Message = None

        self.timeStageRelation: dict[int, int] = {1: 8, 2: 7, 3: 6, 4: 5, 5: 4, 6: 3, 7: 2}
        self.stageStartersRelation: dict[int, list] = {
            i: [word[i - 1] for word in Data.words if len(word) > i - 1] for i in range(1, 8)
        }

async def gameOver(Game) -> None:
    """
    Ends the game and displays the game statistics.

    Args:
        Game (wordbombGame): The game instance to end.
    """
    embed: nextcord.Embed = nextcord.Embed(title='Statistics')
    embed.add_field(name="Stage", value=Game.stage)
    embed.add_field(name="Plays", value=Game.plays)
    embed.add_field(name="Winner", value=f"<@{Game.players[0].id}>" if Game.players else "None (Singleplayer)")
    embed.add_field(name="Host", value=f"<@{Game.userID}>")

    await Game.main_msg.delete()
    channel: nextcord.TextChannel = bot.get_channel(Game.channelID)
    await channel.send(content="Game over!", embed=embed)
    await Game.join_msg.delete()
    
    Game.running = False

def update_embed(Game, nextup) -> nextcord.Embed:
    """
    Updates the game embed with the current game state.

    Args:
        Game (wordbombGame): The game instance.
        nextup (int): The ID of the next player.

    Returns:
        nextcord.Embed: The updated embed.
    """
    embed: nextcord.Embed = nextcord.Embed(title="Guess a word", description=f"Send a word that begins with `{Game.currentStarter}`")
    embed.add_field(name="Stage", value=Game.stage)
    embed.add_field(name="Plays", value=Game.plays)
    embed.add_field(name="Next Up", value=f"<@{nextup}>")
    embed.add_field(name="Time remaining", value=f"{int(Game.timeRemaining)} seconds")
    return embed

async def startGame(Game) -> None:
    """
    Starts the Wordbomb game loop.

    Args:
        Game (wordbombGame): The game instance to start.
    """
    while Game.running:
        if not Game.players:
            await gameOver(Game)
            break

        nextup: int = Game.players[Game.currentPlayerIndex].id
        embed: nextcord.Embed = update_embed(Game, nextup)
        await Game.main_msg.edit(content=f"<@{nextup}>", embed=embed)

        while not Game.responded:
            await asyncio.sleep(0.1)
            Game.timeRemaining -= 0.1
            if Game.timeRemaining <= 0:
                Game.players[Game.currentPlayerIndex].hearts -= 1
                await Game.main_msg.edit(content=f"<@{nextup}> lost a life! {Game.players[Game.currentPlayerIndex].hearts} life remaining")
                await asyncio.sleep(2)
                break

        if Game.responded:
            response_content: str = Game.response.content.lower()
            if len(response_content) < 2 \
	            	or response_content in Game.used_words \
            		or not response_content.startswith(Game.currentStarter.lower()) \
            		or response_content not in Data.words:
                await Game.response.add_reaction("❌")
                Game.players[Game.currentPlayerIndex].hearts -= 1
                await Game.main_msg.edit(content=f"<@{nextup}> lost a life! {Game.players[Game.currentPlayerIndex].hearts} life remaining")
                await asyncio.sleep(2)
            else:
                Game.used_words.add(response_content)
                Game.plays = Game.plays + 1

        if Game.players[Game.currentPlayerIndex].hearts == 0:
            await Game.main_msg.edit(content=f"<@{nextup}> died!")
            Game.players.pop(Game.currentPlayerIndex)
            if Game.currentPlayerIndex >= len(Game.players):
                Game.currentPlayerIndex = 0
            await asyncio.sleep(2)

        if len(Game.players) == 1 and not Game.singleplayer:
            await Game.main_msg.edit(content=f"<@{Game.players[0].id}> wins!")
            await gameOver(Game)
            break

        Game.stage = min(7, (Game.plays // 10) + 1)
        Game.timeRemaining = Game.timeStageRelation[Game.stage]
        Game.currentStarter = random.choice(Game.stageStartersRelation[Game.stage])
        Game.currentPlayerIndex = (Game.currentPlayerIndex + 1) % len(Game.players)
        Game.response, Game.responded = None, False

async def startGameCountdown(interaction: nextcord.Interaction) -> None:
    """
    Handles the countdown before starting the game.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the countdown.
    """
    gameID = interaction.data["custom_id"]
    for game in games.values():
        if f"{game.gameID}###" == gameID:
            if len(game.players) == 1:
                game.singleplayer = True
            if game.stage == 1:
                return await interaction.response.send_message(f"Game already started in <#{game.channelID}>!", ephemeral=True)
            if interaction.user.id != game.userID:
                return await interaction.response.send_message(f"This game is being hosted by <@{game.userID}>!", ephemeral=True)

            embed: nextcord.Embed = nextcord.Embed(title="Game starting...", description="Game will start in **{}**".format(game.countdown))
            embed.add_field(name="Rule #1", value="Answers must be greater than or equal to 2 in length")
            embed.add_field(name="Rule #2", value="Answers must not be repeated")
            game.main_msg = await interaction.response.send_message(embed=embed)

            for _ in range(5):
                await asyncio.sleep(1)
                game.countdown -= 1
                embed.description = f"Game will start in **{game.countdown}**"
                await game.main_msg.edit(embed=embed)

            await startGame(game)
            break

async def joinGame(interaction: nextcord.Interaction) -> None:
    """
    Allows a user to join an existing game.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the join request.
    """
    gameID = interaction.data["custom_id"]
    for game in games.values():
        if str(game.gameID) == gameID:
            if any(player.id == interaction.user.id for player in game.players):
                embed = nextcord.Embed(title="Nope!", description="You have already joined the game!", color=nextcord.colour.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            game.players.append(Player(interaction.user.id))
            embed = nextcord.Embed(title='Waiting for players...', color=nextcord.colour.Color.orange())
            for player in game.players:
                embed.add_field(value=f'<@{player.id}>', name=player.status)

            await game.join_msg.edit(content=f"<@{interaction.user.id}> has joined the game!", embed=embed)
            return

    await interaction.response.send_message("Game not found or invalid game ID.", ephemeral=True)

async def userGameInstanceCreation(interaction: nextcord.Interaction) -> nextcord.Message | None:
    """
    Creates a new game instance for the user.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the game creation.

    Returns:
        nextcord.Message | None: The message sent to the user or None if a game already exists.
    """
    if any(game.channelID == interaction.channel_id for game in games.values()):
        return await interaction.response.send_message(f"A game is already running in <#{interaction.channel_id}>", ephemeral=True)

    if interaction.user.id in games:
        return await interaction.response.send_message(f"You already started a game in <#{games[interaction.user.id].channelID}>", ephemeral=True)

    games[interaction.user.id] = wordbombGame(interaction.user.id, interaction.channel_id)
    currentGame = games[interaction.user.id]
    embed = nextcord.Embed(title='Waiting for players...', color=nextcord.colour.Color.orange())
    button = Button(label="Join Game", style=nextcord.ButtonStyle.green, custom_id=str(currentGame.gameID))
    button.callback = joinGame
    button2 = Button(label="Start Game", style=nextcord.ButtonStyle.red, custom_id=f"{currentGame.gameID}###")
    button2.callback = startGameCountdown

    view = View()
    view.add_item(button)
    view.add_item(button2)

    for player in currentGame.players:
        embed.add_field(value=f'<@{player.id}>', name=player.status)

    currentGame.join_msg = await interaction.response.send_message(embed=embed, view=view)

def shutdown_handler(signal, frame) -> None:
    """
    Handles the shutdown signal to stop the bot gracefully.

    Args:
        signal: The signal received.
        frame: The current stack frame.
    """
    print("Shutting down...")
    loop = asyncio.get_running_loop()
    loop.stop()

@bot.event
async def on_ready() -> None:
    """
    Event handler for when the bot is ready.
    """
    print(f"Bot is online as {bot.user}")

@bot.event
async def on_message(message: nextcord.Message) -> None:
    """
    Event handler for when a message is sent in a channel.

    Args:
        message (nextcord.Message): The message sent.
    """
    for game in games.values():
        if game.channelID == message.channel.id:
            if any(player.id == message.author.id for player in game.players):
                if game.players[game.currentPlayerIndex].id == message.author.id:
                    game.responded = True
                    game.response = message

@bot.slash_command(description="Start your own Wordbomb game")
async def play(interaction: nextcord.Interaction) -> nextcord.Message:
    """
    Slash command to start a Wordbomb game.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the command.

    Returns:
        nextcord.Message: The message sent to the user.
    """
    button = Button(label="Create game", style=nextcord.ButtonStyle.green)
    button.callback = userGameInstanceCreation
    view = View()
    view.add_item(button)

    embed = nextcord.Embed(title="Play Wordbomb", description="Click play to create a game", color=nextcord.colour.Color.orange())
    return await interaction.response.send_message(embed=embed, view=view)

@bot.slash_command(description="Selects from a random list of words")
async def randomword(interaction: nextcord.Interaction) -> nextcord.Message:
    """
    Slash command to get a random word from the word list.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the command.

    Returns:
        nextcord.Message: The message sent to the user.
    """
    random_word = random.choice(list(Data.words))
    embed = nextcord.Embed(title="Random Word", description=random_word, color=nextcord.colour.Color.green())
    return await interaction.response.send_message(embed=embed)

@bot.slash_command(description="Stop ongoing games")
async def stopgame(interaction: nextcord.Interaction) -> nextcord.Message:
    """
    Slash command to stop an ongoing game.

    Args:
        interaction (nextcord.Interaction): The interaction that triggered the command.

    Returns:
        nextcord.Message: The message sent to the user.
    """
    currentGame = games[interaction.user.id]
    if not currentGame:
        return await interaction.response.send_message("You have no ongoing games!")

    del games[interaction.user.id]
    return await currentGame.main_msg.edit(content="This game was stopped by the host.")

signal.signal(signal.SIGINT, shutdown_handler)
bot.run(TOKEN)