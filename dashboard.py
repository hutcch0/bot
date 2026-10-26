import json
import os
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web


class BotStats:
    def __init__(self) -> None:
        self.usage: Counter[str] = Counter()
        self.recent: deque[dict] = deque(maxlen=100)

    def record(self, command: str, user: str, guild: str | None) -> None:
        self.usage[command] += 1
        self.recent.appendleft(
            {
                "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "command": command,
                "user": user,
                "guild": guild or "DM",
            }
        )


class DashboardServer:
    def __init__(self, bot, stats: BotStats, port: int = 8081) -> None:
        self.bot = bot
        self.stats = stats
        self.port = port
        self.log_dir = Path("logs")

    def _uptime_seconds(self) -> int:
        return int((datetime.now(timezone.utc) - self.bot.start_time).total_seconds())

    def _format_uptime(self, seconds: int) -> str:
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}m {secs}s")
        return " ".join(parts)

    def _db_stats(self) -> dict | None:
        if self.bot.db_pool is None:
            return None

        conn = None
        cursor = None
        try:
            conn = self.bot.db_pool.get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("SELECT COUNT(*) AS count FROM users")
            users = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) AS count FROM bans")
            bans = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) AS count FROM afk_users")
            afk = cursor.fetchone()["count"]

            cursor.execute("SELECT pot FROM lottery_state WHERE id = 1")
            row = cursor.fetchone()
            lottery_pot = row["pot"] if row else 0

            cursor.execute("SELECT COALESCE(SUM(tickets), 0) AS total FROM lottery_tickets")
            lottery_tickets = cursor.fetchone()["total"]

            return {
                "users": int(users),
                "bans": int(bans),
                "afk": int(afk),
                "lottery_pot": int(lottery_pot),
                "lottery_tickets": int(lottery_tickets),
            }
        except Exception:
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _slash_commands(self) -> list[dict]:
        commands = []
        for cmd in self.bot.tree.walk_commands():
            commands.append(
                {
                    "name": cmd.qualified_name,
                    "description": cmd.description or "",
                }
            )
        commands.sort(key=lambda item: item["name"])
        return commands

    def _tail_logs(self, lines: int = 80) -> list[str]:
        if not self.log_dir.exists():
            return []

        log_files = sorted(self.log_dir.glob("bot_*.log"))
        if not log_files:
            return []

        latest = log_files[-1]
        try:
            content = latest.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []

        return content[-lines:]

    async def stats_handler(self, _request: web.Request) -> web.Response:
        bot = self.bot
        online = bot.is_ready()
        latency_ms = None
        if online:
            # During Discord gateway reconnect/resume, latency can briefly be inf.
            try:
                latency_ms = round(bot.latency * 1000)
            except (OverflowError, ValueError):
                latency_ms = None
        uptime_seconds = self._uptime_seconds()

        guilds = []
        if online:
            for guild in bot.guilds:
                guilds.append(
                    {
                        "name": guild.name,
                        "id": str(guild.id),
                        "members": guild.member_count or 0,
                    }
                )

        payload = {
            "online": online,
            "username": str(bot.user) if bot.user else None,
            "user_id": str(bot.user.id) if bot.user else None,
            "uptime_seconds": uptime_seconds,
            "uptime_label": self._format_uptime(uptime_seconds),
            "latency_ms": latency_ms,
            "guilds": guilds,
            "guild_count": len(guilds),
            "cogs": sorted(ext.replace("cogs.", "") for ext in bot.extensions),
            "slash_commands": self._slash_commands(),
            "db_connected": bot.db_pool is not None,
            "db_stats": self._db_stats(),
            "command_usage": dict(self.stats.usage.most_common(20)),
            "total_commands_used": sum(self.stats.usage.values()),
            "recent_commands": list(self.stats.recent),
            "started_at": self.bot.start_time.isoformat(),
        }

        return web.json_response(payload, headers={"Cache-Control": "no-store"})

    async def logs_handler(self, _request: web.Request) -> web.Response:
        return web.json_response(
            {"lines": self._tail_logs()},
            headers={"Cache-Control": "no-store"},
        )

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/stats", self.stats_handler)
        app.router.add_get("/logs", self.logs_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        self.bot.logger.info("Dashboard API listening on port %s", self.port)
