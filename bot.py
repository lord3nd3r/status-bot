#!/usr/bin/env python3
"""
IRC Status Bot - Manages user modes and channel operations
"""

import json
import logging
import ssl
import sys
import base64
import socket
from typing import Dict, List, Optional
import time
import re


class IRCBot:
    """IRC bot with SASL, SSL support and admin commands"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.server = config['server']
        self.port = config['port']
        self.nickname = config['nickname']
        self.username = config.get('username', config['nickname'])
        self.realname = config.get('realname', config['nickname'])
        self.use_ssl = config.get('ssl', True)
        self.sasl_config = config.get('sasl', {})
        self.channels = config.get('channels', [])
        self.admins = config.get('admins', [])
        self.command_prefix = config.get('command_prefix', '!')
        self.status_db_file = config.get('status_db', f"status_{config['name']}.json")
        
        self.socket = None
        self.connected = False
        self.identified = False
        self.buffer = ""
        
        # Setup logging
        self.logger = logging.getLogger(f"IRCBot-{config['name']}")
        
        # Persistent status database: {"#channel": {"nick": "mode"}}
        self.status_db = self.load_status_db()
    
    def load_status_db(self) -> Dict:
        """Load persistent status database from file"""
        try:
            with open(self.status_db_file, 'r') as f:
                db = json.load(f)
                self.logger.info(f"Loaded {len(db)} channels from status database")
                return db
        except FileNotFoundError:
            self.logger.info("No existing status database, starting fresh")
            return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing status database: {e}")
            return {}
    
    def save_status_db(self):
        """Save persistent status database to file"""
        try:
            with open(self.status_db_file, 'w') as f:
                json.dump(self.status_db, f, indent=2)
            self.logger.debug("Saved status database")
        except Exception as e:
            self.logger.error(f"Error saving status database: {e}")
    
    def add_status(self, channel: str, nick: str, mode: str):
        """Add a persistent status for a user"""
        if channel not in self.status_db:
            self.status_db[channel] = {}
        self.status_db[channel][nick.lower()] = mode
        self.save_status_db()
        self.logger.info(f"Added persistent status: {nick} -> {mode} in {channel}")
    
    def remove_status(self, channel: str, nick: str) -> bool:
        """Remove a persistent status for a user"""
        if channel in self.status_db and nick.lower() in self.status_db[channel]:
            del self.status_db[channel][nick.lower()]
            if not self.status_db[channel]:  # Remove empty channel
                del self.status_db[channel]
            self.save_status_db()
            self.logger.info(f"Removed persistent status: {nick} in {channel}")
            return True
        return False
    
    def get_status(self, channel: str, nick: str) -> Optional[str]:
        """Get the persistent status for a user"""
        if channel in self.status_db:
            return self.status_db[channel].get(nick.lower())
        return None
    
    def apply_status(self, channel: str, nick: str):
        """Apply persistent status to a user if they have one"""
        mode = self.get_status(channel, nick)
        if mode:
            self.set_mode(channel, f'+{mode}', nick)
            self.logger.info(f"Auto-applied +{mode} to {nick} in {channel}")
    
    def connect(self):
        """Connect to IRC server with SSL support"""
        self.logger.info(f"Connecting to {self.server}:{self.port} (SSL: {self.use_ssl})")
        
        raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        if self.use_ssl:
            context = ssl.create_default_context()
            self.socket = context.wrap_socket(raw_socket, server_hostname=self.server)
        else:
            self.socket = raw_socket
        
        try:
            self.socket.connect((self.server, self.port))
            self.connected = True
            self.logger.info("Connected successfully")
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            raise
    
    def send_raw(self, message: str):
        """Send raw IRC message"""
        if not self.connected:
            self.logger.error("Not connected, cannot send message")
            return
        
        try:
            self.socket.send(f"{message}\r\n".encode('utf-8'))
            self.logger.debug(f">>> {message}")
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            self.connected = False
    
    def send_sasl_plain(self):
        """Send SASL PLAIN authentication"""
        if not self.sasl_config.get('enabled'):
            return
        
        username = self.sasl_config['username']
        password = self.sasl_config['password']
        
        # SASL PLAIN format: \0username\0password
        auth_string = f"\0{username}\0{password}"
        auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
        
        self.send_raw("AUTHENTICATE PLAIN")
        # Wait a bit for server response
        time.sleep(0.5)
        self.send_raw(f"AUTHENTICATE {auth_b64}")
    
    def register(self):
        """Register with IRC server"""
        # Request SASL if enabled
        if self.sasl_config.get('enabled'):
            self.send_raw("CAP REQ :sasl")
        
        self.send_raw(f"NICK {self.nickname}")
        self.send_raw(f"USER {self.username} 0 * :{self.realname}")
    
    def join_channel(self, channel: str):
        """Join a channel"""
        if not channel.startswith('#'):
            channel = f"#{channel}"
        self.send_raw(f"JOIN {channel}")
        self.logger.info(f"Joining {channel}")
    
    def part_channel(self, channel: str, message: str = "Leaving"):
        """Part a channel"""
        if not channel.startswith('#'):
            channel = f"#{channel}"
        self.send_raw(f"PART {channel} :{message}")
        self.logger.info(f"Parting {channel}")
    
    def set_mode(self, channel: str, mode: str, target: str):
        """Set mode on user in channel"""
        self.send_raw(f"MODE {channel} {mode} {target}")
        self.logger.info(f"Setting mode {mode} on {target} in {channel}")
    
    def send_message(self, target: str, message: str):
        """Send PRIVMSG to channel or user"""
        self.send_raw(f"PRIVMSG {target} :{message}")
    
    def is_admin(self, hostmask: str) -> bool:
        """Check if user is an admin based on hostmask"""
        for admin_pattern in self.admins:
            # Convert IRC wildcard pattern to regex
            regex_pattern = admin_pattern.replace('*', '.*').replace('?', '.')
            if re.match(regex_pattern, hostmask, re.IGNORECASE):
                return True
        return False
    
    def parse_hostmask(self, prefix: str) -> tuple:
        """Parse IRC hostmask into (nick, user, host)"""
        if '!' in prefix and '@' in prefix:
            nick = prefix.split('!')[0]
            user = prefix.split('!')[1].split('@')[0]
            host = prefix.split('@')[1]
            return (nick, user, host)
        return (prefix, '', '')
    
    def handle_command(self, prefix: str, target: str, message: str):
        """Handle bot commands"""
        if not message.startswith(self.command_prefix):
            return
        
        # Check if user is admin
        if not self.is_admin(prefix):
            nick = self.parse_hostmask(prefix)[0]
            self.logger.warning(f"Non-admin {prefix} attempted command: {message}")
            self.send_message(nick, "Error: You don't have permission to use bot commands.")
            return
        
        # Parse command
        parts = message[len(self.command_prefix):].split()
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        nick = self.parse_hostmask(prefix)[0]
        reply_to = nick if target == self.nickname else target
        
        self.logger.info(f"Admin {nick} executed: {message}")
        
        # Mode commands
        if command == 'addq' and args:
            # Add +q (owner)
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '+q', args[0])
                self.add_status(channel, args[0], 'q')
                self.send_message(reply_to, f"Added +q to {args[0]} in {channel} (persistent)")
        
        elif command == 'delq' and args:
            # Remove +q
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '-q', args[0])
                self.remove_status(channel, args[0])
                self.send_message(reply_to, f"Removed +q from {args[0]} in {channel} (persistent)")
        
        elif command == 'adda' and args:
            # Add +a (admin/protected)
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '+a', args[0])
                self.add_status(channel, args[0], 'a')
                self.send_message(reply_to, f"Added +a to {args[0]} in {channel} (persistent)")
        
        elif command == 'dela' and args:
            # Remove +a
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '-a', args[0])
                self.remove_status(channel, args[0])
                self.send_message(reply_to, f"Removed +a from {args[0]} in {channel} (persistent)")
        
        elif command == 'addo' and args:
            # Add +o (operator)
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '+o', args[0])
                self.add_status(channel, args[0], 'o')
                self.send_message(reply_to, f"Added +o to {args[0]} in {channel} (persistent)")
        
        elif command == 'delo' and args:
            # Remove +o
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '-o', args[0])
                self.remove_status(channel, args[0])
                self.send_message(reply_to, f"Removed +o from {args[0]} in {channel} (persistent)")
        
        elif command == 'addh' and args:
            # Add +h (halfop)
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '+h', args[0])
                self.add_status(channel, args[0], 'h')
                self.send_message(reply_to, f"Added +h to {args[0]} in {channel} (persistent)")
        
        elif command == 'delh' and args:
            # Remove +h
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '-h', args[0])
                self.remove_status(channel, args[0])
                self.send_message(reply_to, f"Removed +h from {args[0]} in {channel} (persistent)")
        
        elif command == 'addv' and args:
            # Add +v (voice)
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '+v', args[0])
                self.add_status(channel, args[0], 'v')
                self.send_message(reply_to, f"Added +v to {args[0]} in {channel} (persistent)")
        
        elif command == 'delv' and args:
            # Remove +v
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                self.set_mode(channel, '-v', args[0])
                self.remove_status(channel, args[0])
                self.send_message(reply_to, f"Removed +v from {args[0]} in {channel} (persistent)")
        
        elif command == 'join' and args:
            # Join a channel
            channel = args[0]
            self.join_channel(channel)
            self.send_message(reply_to, f"Joining {channel}")
        
        elif command == 'part' and args:
            # Part a channel
            channel = args[0]
            reason = ' '.join(args[1:]) if len(args) > 1 else "Requested by admin"
            self.part_channel(channel, reason)
            self.send_message(reply_to, f"Parting {channel}")
        
        elif command == 'say' and len(args) >= 2:
            # Say something in a channel
            channel = args[0]
            msg = ' '.join(args[1:])
            self.send_message(channel, msg)
        
        elif command == 'raw' and args:
            # Send raw IRC command
            raw_cmd = ' '.join(args)
            self.send_raw(raw_cmd)
            self.send_message(reply_to, f"Sent: {raw_cmd}")
        
        elif command == 'liststatus':
            # List all persistent statuses
            if not self.status_db:
                self.send_message(reply_to, "No persistent statuses configured.")
            else:
                self.send_message(reply_to, "Persistent statuses:")
                for channel, users in self.status_db.items():
                    for nick, mode in users.items():
                        self.send_message(reply_to, f"  {channel}: {nick} -> +{mode}")
        
        elif command == 'delstatus' and args:
            # Remove a persistent status without changing current mode
            nick = args[0]
            channel = target if target.startswith('#') else (args[1] if len(args) > 1 else None)
            if channel:
                if self.remove_status(channel, nick):
                    self.send_message(reply_to, f"Removed persistent status for {nick} in {channel}")
                else:
                    self.send_message(reply_to, f"No persistent status found for {nick} in {channel}")
            else:
                self.send_message(reply_to, "Please specify a channel")
        
        elif command == 'clearstatus':
            # Clear all persistent statuses
            count = sum(len(users) for users in self.status_db.values())
            self.status_db = {}
            self.save_status_db()
            self.send_message(reply_to, f"Cleared {count} persistent status(es)")
        
        elif command == 'qhelp':
            # Show help
            help_text = [
                "Available commands:",
                "Mode commands: addq/delq, adda/dela, addo/delo, addh/delh, addv/delv <nick> [channel]",
                "Channel: join <channel>, part <channel> [reason]",
                "Status: liststatus, delstatus <nick> [channel], clearstatus",
                "Other: say <channel> <message>, raw <command>, qhelp",
                "Note: Mode commands are persistent - users will be auto-opped on join"
            ]
            for line in help_text:
                self.send_message(reply_to, line)
    
    def handle_line(self, line: str):
        """Handle a single IRC line"""
        self.logger.debug(f"<<< {line}")
        
        parts = line.split(' ')
        
        # Handle PING
        if parts[0] == 'PING':
            pong_target = parts[1] if len(parts) > 1 else ''
            self.send_raw(f"PONG {pong_target}")
            return
        
        # Handle CAP responses
        if len(parts) >= 2 and parts[1] == 'CAP':
            if len(parts) >= 4 and parts[3] == 'ACK' and 'sasl' in line.lower():
                self.send_sasl_plain()
        
        # Handle SASL responses
        if len(parts) >= 2 and parts[0] == 'AUTHENTICATE' and parts[1] == '+':
            # Server is ready for SASL, already sent in send_sasl_plain
            pass
        
        if len(parts) >= 2 and parts[1] == '903':
            # SASL success
            self.logger.info("SASL authentication successful")
            self.send_raw("CAP END")
        
        if len(parts) >= 2 and parts[1] in ['904', '905', '906']:
            # SASL failed
            self.logger.error("SASL authentication failed")
            self.send_raw("CAP END")
        
        # Handle end of MOTD (ready to join channels)
        if len(parts) >= 2 and parts[1] in ['376', '422']:
            if not self.identified:
                self.identified = True
                self.logger.info("Registration complete, joining channels")
                for channel in self.channels:
                    self.join_channel(channel)
        
        # Handle JOIN
        if len(parts) >= 3 and parts[1] == 'JOIN':
            prefix = parts[0][1:] if parts[0].startswith(':') else parts[0]
            channel = parts[2][1:] if parts[2].startswith(':') else parts[2]  # Remove leading :
            nick = self.parse_hostmask(prefix)[0]
            
            # Don't auto-apply to ourselves
            if nick.lower() != self.nickname.lower():
                self.logger.debug(f"{nick} joined {channel}")
                # Small delay to let the user fully join before applying modes
                time.sleep(0.5)
                self.apply_status(channel, nick)
        
        # Handle PRIVMSG
        if len(parts) >= 4 and parts[1] == 'PRIVMSG':
            prefix = parts[0][1:] if parts[0].startswith(':') else parts[0]
            target = parts[2]
            message = ' '.join(parts[3:])[1:]  # Remove leading :
            
            self.handle_command(prefix, target, message)
    
    def run(self):
        """Main bot loop"""
        self.connect()
        self.register()
        
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8', errors='ignore')
                if not data:
                    self.logger.warning("Connection closed by server")
                    break
                
                self.buffer += data
                
                while '\r\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\r\n', 1)
                    if line:
                        self.handle_line(line)
            
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, quitting")
                self.send_raw("QUIT :Shutting down")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                break
        
        if self.socket:
            self.socket.close()
        self.connected = False


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        logging.error("config.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing config.json: {e}")
        sys.exit(1)
    
    # Set log level
    log_level = config.get('log_level', 'INFO')
    logging.getLogger().setLevel(getattr(logging, log_level))
    
    # Start bots for each network
    networks = config.get('networks', [])
    if not networks:
        logging.error("No networks configured")
        sys.exit(1)
    
    # For simplicity, run one bot at a time
    # In production, you'd want to use threading or asyncio for multiple networks
    for network_config in networks:
        logging.info(f"Starting bot for network: {network_config['name']}")
        bot = IRCBot(network_config)
        try:
            bot.run()
        except KeyboardInterrupt:
            logging.info("Shutting down")
            break
        except Exception as e:
            logging.error(f"Bot crashed: {e}", exc_info=True)
            logging.info("Waiting 30 seconds before reconnecting...")
            time.sleep(30)


if __name__ == '__main__':
    main()
