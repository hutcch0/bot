# Discord Utility & Game Bot

A feature-rich Discord bot with moderation, games, economy, and utility commands.  
Supports global bans (cross-server), AFK system, blackjack, slots, a mines game, reporting, and more!

---

## Features

- **Global Ban System:** Ban users across all servers the bot is in (with MySQL database support).
- **Economy:** Earn, buy, and sell coins. Leaderboard and balance tracking.
- **Games:** Blackjack, slots, and a mines game.
- **AFK System:** Set yourself as AFK, notifies others, and auto-removes on your return.
- **Moderation:** Kick, ban, mute, unmute, and purge messages.
- **Reporting:** Members can report users; staff can claim/close reports.
- **Social Links:** Share your community’s links with an embed.
- **Photo Command:** Randomly sends a photo from a JSON file.

---

## Commands

| Command                        | Description                                                              | Permission        |
|--------------------------------|--------------------------------------------------------------------------|-------------------|
| **🔨 Moderation**              |                                                                          |                   |
| `!globalban @user [reason]`    | Globally ban a user across all servers                                   | Owner Only        |
| `!globalunban @user [reason]`  | Globally unban a user across all servers                                 | Owner Only        |
| `!bans`                        | Show the global ban list                                                 | Owner Only        |
| `!kick @user [reason]`         | Kick a user from the server                                              | Kick Members      |
| `!timeout @user <mins> [reason]`| Timeout a user for a set number of minutes (max 40320 / 28 days)       | Moderate Members  |
| `!report @user <reason>`       | Report a user to the staff                                               | Everyone          |
| **🛠️ Utility**                 |                                                                          |                   |
| `!uptime`                      | Show how long the bot has been online                                    | Everyone          |
| `!afk [reason]`                | Set yourself as AFK                                                      | Everyone          |
| `!userinfo [@user]`            | Show info about a user                                                   | Everyone          |
| `!serverinfo`                  | Show info about the server                                               | Everyone          |
| `!social`                      | Show social/community links                                              | Everyone          |
| `!photo`                       | Send a random photo from the photo list                                  | Everyone          |
| **💰 Economy**                 |                                                                          |                   |
| `!balance [@user]`             | Show your (or another users) coin, money balance and level               | Everyone          |
| `!work`                        | Work to earn money (once per day)                                        | Everyone          |
| `!buycoin <amount>`            | Buy coins with your cash                                                 | Everyone          |
| `!sellcoin <amount>`           | Sell coins for cash                                                      | Everyone          |
| `!coinvalue`                   | Show the current coin market value                                       | Everyone          |
| `!leaderboard`                 | Show the top 10 coin holders                                             | Everyone          |
| `!xp [@user]`                  | Show your (or another users) level and XP progress                       | Everyone          |
| `!lottery`                     | Show the current lottery pot and ticket price                            | Everyone          |
| `!lottery buy <amount>`        | Buy lottery tickets (more tickets = better odds)                         | Everyone          |
| `!lottery draw`                | Draw a lottery winner and pay out the pot                                | Owner Only        |
| **🎮 Games**                   |                                                                          |                   |
| `!blackjack [bet]`             | Start a game of blackjack with an optional coin bet                      | Everyone          |
| `!hit`                         | Draw another card in your blackjack game                                 | Everyone          |
| `!stand`                       | Hold your hand and let the dealer play in blackjack                      | Everyone          |
| `!slots <bet>`                 | Spin the slot machine (2x on two of a kind, 5x on jackpot)              | Everyone          |
| `!mine <bet> <row> <col>`      | Pick a cell on a 3x3 grid and avoid the bombs                           | Everyone          |
| **⚙️ Bot Management**          |                                                                          |                   |
| `!reload <cog>`                | Reload a specific cog without restarting                                 | Owner Only        |
| `!load <cog>`                  | Load a cog that is not currently loaded                                  | Owner Only        |
| `!unload <cog>`                | Unload a currently loaded cog                                            | Owner Only        |
| `!cogs`                        | List all currently loaded cogs                                           | Owner Only        |

---
