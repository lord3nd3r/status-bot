# IRC Status Bot

A powerful IRC bot for managing user modes and channel operations with SASL and SSL support.

## Features

- ✅ **SSL/TLS Support** - Secure connections to IRC servers
- ✅ **SASL Authentication** - PLAIN SASL authentication support
- ✅ **Multiple Networks** - Connect to multiple IRC networks (sequential)
- ✅ **User Mode Management** - Add/remove modes: +q (owner), +a (admin), +o (op), +h (halfop), +v (voice)
- ✅ **Persistent Status** - Automatically re-apply modes when users reconnect
- ✅ **Channel Management** - Join and part channels dynamically
- ✅ **Admin Control** - Restrict commands to authorized users via hostmask matching
- ✅ **PM and Channel Commands** - Works in both private messages and channels
- ✅ **Logging** - Comprehensive logging with configurable log levels

## Requirements

- Python 3.6 or higher
- No external dependencies (uses only Python standard library)

## Installation

1. Clone or download this repository
2. Edit `config.json` with your IRC network settings
3. Run the bot:

```bash
python3 bot.py
```

## Configuration

Edit `config.json` to configure your bot:

```json
{
  "networks": [
    {
      "name": "ExampleNet",
      "server": "irc.example.net",
      "port": 6697,
      "ssl": true,
      "nickname": "StatusBot",
      "username": "statusbot",
      "realname": "Status Management Bot",
      "sasl": {
        "enabled": true,
        "username": "statusbot",
        "password": "your_sasl_password_here"
      },
      "channels": ["#example", "#test"],
      "admins": [
        "admin!*@*.example.com",
        "End3r!*@*"
      ],
      "command_prefix": "!",
      "status_db": "status_ExampleNet.json"
    }
  ],
  "log_level": "INFO"
}
```

### Configuration Options

- **name**: Network identifier (for logging)
- **server**: IRC server hostname
- **port**: IRC server port (usually 6697 for SSL, 6667 for non-SSL)
- **ssl**: Enable SSL/TLS connection (true/false)
- **nickname**: Bot's nickname
- **username**: Bot's username (ident)
- **realname**: Bot's real name field
- **sasl**: SASL authentication settings
  - **enabled**: Enable SASL authentication
  - **username**: SASL username (usually same as NickServ account)
  - **password**: SASL password
- **channels**: List of channels to auto-join
- **admins**: List of admin hostmask patterns (supports * and ? wildcards)
- **command_prefix**: Command prefix (default: !)
- **status_db**: Filename for persistent status database (optional, default: status_<network>.json)
- **log_level**: Logging level (DEBUG, INFO, WARNING, ERROR)

### Admin Hostmask Patterns

Hostmasks follow the IRC format: `nick!user@host`

Examples:
- `End3r!*@*` - Matches nickname "End3r" with any user@host
- `*!*@*.example.com` - Matches any user from example.com domain
- `admin!~admin@192.168.*.*` - Matches specific user from 192.168.x.x subnet

## Commands

All commands require admin privileges (matching hostmask in config).

### Mode Commands

Add or remove channel modes for users. **These commands create persistent status assignments** - users will automatically receive their assigned mode when they join the channel.

| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| `addq` | Add +q (owner) | `!addq <nick> [channel]` | `!addq End3r` or `!addq End3r #channel` |
| `delq` | Remove +q | `!delq <nick> [channel]` | `!delq End3r` |
| `adda` | Add +a (admin/protected) | `!adda <nick> [channel]` | `!adda End3r` |
| `dela` | Remove +a | `!dela <nick> [channel]` | `!dela End3r` |
| `addo` | Add +o (operator) | `!addo <nick> [channel]` | `!addo End3r` |
| `delo` | Remove +o | `!delo <nick> [channel]` | `!delo End3r` |
| `addh` | Add +h (halfop) | `!addh <nick> [channel]` | `!addh End3r` |
| `delh` | Remove +h | `!delh <nick> [channel]` | `!delh End3r` |
| `addv` | Add +v (voice) | `!addv <nick> [channel]` | `!addv End3r` |
| `delv` | Remove +v | `!delv <nick> [channel]` | `!delv End3r` |

**Note**: When used in a channel, the channel parameter is optional (uses current channel). In PM, you must specify the channel.

### Channel Management Commands

| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| `join` | Join a channel | `!join <channel>` | `!join #newchannel` |
| `part` | Leave a channel | `!part <channel> [reason]` | `!part #channel Goodbye!` |

### Status Management Commands

Manage persistent status assignments:

| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| `liststatus` | Show all persistent statuses | `!liststatus` | `!liststatus` |
| `delstatus` | Remove persistent status | `!delstatus <nick> [channel]` | `!delstatus End3r #example` |
| `clearstatus` | Clear all persistent statuses | `!clearstatus` | `!clearstatus` |

**Note**: `delstatus` removes the persistent assignment but doesn't change the user's current mode. Use `delo`, `delv`, etc. to remove both the persistent status and current mode.

### Utility Commands

| Command | Description | Usage | Example |
|---------|-------------|-------|---------|
| `say` | Send message to channel | `!say <channel> <message>` | `!say #test Hello everyone!` |
| `raw` | Send raw IRC command | `!raw <command>` | `!raw WHOIS End3r` |
| `help` | Show help message | `!help` | `!help` |

## Usage Examples

### In a Channel

```
<End3r> !addq Bob
<StatusBot> Added +q to Bob in #example (persistent)

<End3r> !addo Alice
<StatusBot> Added +o to Alice in #example (persistent)

<End3r> !join #newchannel
<StatusBot> Joining #newchannel

<End3r> !liststatus
<StatusBot> Persistent statuses:
<StatusBot>   #example: bob -> +q
<StatusBot>   #example: alice -> +o
```

### Auto-Apply on Join

When a user with a persistent status joins:

```
--> Bob has joined #example
-!- mode/#example [+q Bob] by StatusBot
```

### In Private Message

```
/msg StatusBot !addq End3r #example
<StatusBot> Added +q to End3r in #example (persistent)

/msg StatusBot !join #test
<StatusBot> Joining #test

/msg StatusBot !liststatus
<StatusBot> Persistent statuses:
<StatusBot>   #example: end3r -> +q
```

## Persistent Status Database

The bot maintains a JSON database file (default: `status_<network>.json`) that stores persistent status assignments. This file is automatically created and updated when you use mode commands.

**Example database structure:**
```json
{
  "#example": {
    "bob": "q",
    "alice": "o",
    "charlie": "v"
  },
  "#test": {
    "dave": "o"
  }
}
```

**Important notes:**
- Nicknames are stored in lowercase for case-insensitive matching
- The database is automatically saved when modes are added or removed
- Back up this file if you want to preserve status assignments
- The bot automatically applies modes when users join channels

## Security Considerations

1. **Protect your config.json and status database** - Contains SASL passwords and status assignments
   ```bash
   chmod 600 config.json status_*.json
   ```

2. **Use specific hostmasks** - Avoid overly broad patterns like `*!*@*`

3. **SASL Authentication** - Always use SASL when available for account-based authentication

4. **SSL/TLS** - Always use SSL (port 6697) for encrypted connections

## Running as a Service

### Using screen (simple method)

```bash
screen -S statusbot
python3 bot.py
# Press Ctrl+A then D to detach
```

To reattach: `screen -r statusbot`

### Using systemd (recommended for production)

Create `/etc/systemd/system/statusbot.service`:

```ini
[Unit]
Description=IRC Status Bot
After=network.target

[Service]
Type=simple
User=ircbot
WorkingDirectory=/home/ircbot/statusbot
ExecStart=/usr/bin/python3 /home/ircbot/statusbot/bot.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable statusbot
sudo systemctl start statusbot
sudo systemctl status statusbot
```

## Troubleshooting

### Bot doesn't connect

- Check server/port settings
- Verify SSL is enabled for SSL ports (usually 6697)
- Check firewall settings

### SASL authentication fails

- Verify SASL username/password are correct
- Ensure your NickServ account is registered
- Check if server supports SASL PLAIN

### Bot doesn't respond to commands

- Verify your hostmask matches an admin pattern
- Check command prefix setting
- Enable DEBUG logging to see what's happening:
  ```json
  "log_level": "DEBUG"
  ```

### Bot can't set modes

- Ensure the bot has appropriate channel privileges
- The bot needs to be an operator (+o) or higher to set most modes
- Some modes (like +q and +a) may require special privileges

## Multiple Networks

To connect to multiple networks, add more network configurations to the `networks` array in config.json. The bot will connect to each network sequentially (one at a time in the current implementation).

For true multi-network support, you can run multiple instances of the bot with different config files:

```bash
python3 bot.py config1.json &
python3 bot.py config2.json &
```

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions, please check the troubleshooting section above.
