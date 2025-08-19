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

| Command           | Description                                                                  |
|-------------------|------------------------------------------------------------------------------|
| `!ban @user [reason]`      | Globally ban a user (cross-server, staff only)                      |
| `!unban @user`             | Globally unban a user (staff only)                                  |
| `!banlist`                 | Show the global ban list (staff only)                               |
| `!kick @user [reason]`     | Kick a user (staff only)                                            |
| `!mute @user [reason]`     | Mute a user (staff only, requires "Muted" role)                     |
| `!unmute @user [reason]`   | Unmute a user (staff only)                                          |
| `!purge <number>`          | Delete a number of messages (staff only)                            |
| `!report @user <reason>`   | Report a user to the staff                                          |
| `!afk [reason]`            | Set yourself as AFK                                                 |
| `!back`                    | Remove your AFK status                                              |
| `!blackjack`               | Start a game of blackjack                                           |
| `!hit`                     | Draw a card in blackjack                                            |
| `!stand`                   | Stand in blackjack                                                  |
| `!slots <bet>`             | Play the slots game                                                 |
| `!mine <bet> <row> <col>`  | Play the mines game (pick a spot in a 3x3 grid, avoid the bomb)     |
| `!buycoin <amount>`        | Buy coins with your money                                           |
| `!sellcoin <amount>`       | Sell coins for money                                                |
| `!balance`                 | Show your coin and money balance                                    |
| `!leaderboard`             | Show the top coin holders                                           |
| `!coinvalue`               | Show the current coin value                                         |
| `!userinfo [@user]`        | Show info about a user                                              |
| `!serverinfo`              | Show info about the server                                          |
| `!uptime`                  | Show how long the bot has been online                               |
| `!social`                  | Show social/community links                                         |
| `!photo`                   | Send a random photo from a JSON file                                |
| `!work`                    | work for money.                                                     |
| `!lottery`                 | Show the current lottery status.                                    |
| `!lottery buy <amount>`    | Buy lottery tickets (more tickets = better odds)                    |
| `!lottery my`              | Show how many tickets you have in the current lottery.              |
| `!stop`                    | Stop the bot (bot owner only)                                       |

---
