#!/usr/bin/env python3
"""
Anime Farewell Bot - A Telegram bot that sends anime-themed farewell messages
when users leave or get kicked from group chats.
"""

import os
import logging
import json
import requests
from urllib.parse import quote
import time
import sqlite3
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required. Please set it with your bot token from @BotFather")

class BotDatabase:
    def __init__(self, db_path="bot_settings.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with settings tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create settings table for messages and images
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER,
                setting_type TEXT,
                content TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, setting_type)
            )
        ''')
        
        # Create admin table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                chat_id INTEGER,
                user_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (chat_id, user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def set_message(self, chat_id, message_type, content, image_path=None):
        """Set a custom message for a chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (chat_id, setting_type, content, image_path)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, message_type, content, image_path))
        conn.commit()
        conn.close()
    
    def get_message(self, chat_id, message_type):
        """Get a custom message for a chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT content, image_path FROM settings 
            WHERE chat_id = ? AND setting_type = ?
        ''', (chat_id, message_type))
        result = cursor.fetchone()
        conn.close()
        return result if result else (None, None)
    
    def add_admin(self, chat_id, user_id):
        """Add an admin for a chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO admins (chat_id, user_id)
            VALUES (?, ?)
        ''', (chat_id, user_id))
        conn.commit()
        conn.close()
    
    def is_admin(self, chat_id, user_id):
        """Check if user is admin for a chat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 1 FROM admins WHERE chat_id = ? AND user_id = ?
        ''', (chat_id, user_id))
        result = cursor.fetchone()
        conn.close()
        return result is not None

class TelegramBot:
    def __init__(self, token):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.db = BotDatabase()
        self.user_states = {}  # Track user interaction states
        
    def send_message(self, chat_id, text):
        """Send a text message"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        try:
            response = requests.post(url, data=data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def send_photo(self, chat_id, photo_path, caption):
        """Send a photo with caption"""
        url = f"{self.base_url}/sendPhoto"
        
        try:
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {
                    'chat_id': chat_id,
                    'caption': caption,
                    'parse_mode': 'HTML'
                }
                response = requests.post(url, data=data, files=files)
                return response.json()
        except Exception as e:
            logger.error(f"Failed to send photo: {e}")
            return None
    
    def get_updates(self, offset=None, timeout=30):
        """Get updates from Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {
            'timeout': timeout,
            'allowed_updates': json.dumps(['chat_member', 'message', 'callback_query'])
        }
        if offset:
            params['offset'] = offset
            
        try:
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get updates: {e}")
            return None
    
    def send_inline_keyboard(self, chat_id, text, keyboard):
        """Send message with inline keyboard"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'HTML',
            'reply_markup': json.dumps({
                'inline_keyboard': keyboard
            })
        }
        
        try:
            response = requests.post(url, data=data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send keyboard: {e}")
            return None
    
    def answer_callback_query(self, callback_query_id, text=""):
        """Answer callback query"""
        url = f"{self.base_url}/answerCallbackQuery"
        data = {
            'callback_query_id': callback_query_id,
            'text': text
        }
        
        try:
            response = requests.post(url, data=data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
            return None
    
    def edit_message(self, chat_id, message_id, text, keyboard=None):
        """Edit an existing message"""
        url = f"{self.base_url}/editMessageText"
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text,
            'parse_mode': 'HTML'
        }
        
        if keyboard:
            data['reply_markup'] = json.dumps({
                'inline_keyboard': keyboard
            })
        
        try:
            response = requests.post(url, data=data)
            return response.json()
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            return None
    
    def download_file(self, file_id):
        """Download a file from Telegram"""
        # Get file info first
        url = f"{self.base_url}/getFile"
        response = requests.get(url, params={'file_id': file_id})
        
        if response.status_code == 200:
            file_info = response.json()
            if file_info.get('ok'):
                file_path = file_info['result']['file_path']
                file_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"
                
                # Download the actual file
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    return file_response.content, file_path.split('/')[-1]
        
        return None, None

def get_default_messages():
    """Get default farewell messages"""
    return {
        'leave': (
            "<b>Awww… {username}, you're leaving?</b>\n\n"
            "Well, it was <i>cute</i> while it lasted. Byeee~ 💋\n\n"
            "I'm gonna miss you sooo much~ 💔 <i>(not really)</i>\n"
            "But don’t come back crawling and crying afterwards.😘"
        ),
        'kick': (
            "<b>Oh? {username} got the boot? 👢</b>\n\n"
            "Well, well, well... someone couldn’t behave~ 😏\n\n"
            "<u>Bye bye~</u>\n"
            "<b>You earned it, b*tch.</b> 😘\n"
            "<i>Teehee~ 💋</i>"
        ),
        'ban': (
            "<b>Ooopsie! Thehehe... {username} got banned?!</b> 😢\n\n"
            "I’m <i>devastated.</i> Truly.\n"
            "Like… I’m totally gonna cry about it later… maybe… not. 💅\n\n"
            "<i>Well, well... <u>that’s what happens when you don’t follow the rules~</u></i> 😤\n"
            "<b>Gonna miss you sooo much…</b>\n"
            "<i>Hihi~ 💋🖤</i> <b>no.</b> 😘💋"
        )
    }

def handle_message(bot, update):
    """Handle text messages and commands"""
    try:
        if 'message' not in update:
            return
            
        message = update['message']
        chat_id = message.get('chat', {}).get('id')
        user_id = message.get('from', {}).get('id')
        text = message.get('text', '')
        
        if not chat_id or not user_id:
            return
        
        # Handle /edit command
        if text == '/edit' or text == '/edit@Yukira':
            handle_settings_command(bot, chat_id, user_id, message.get('message_id'))
        
        # Handle user states (waiting for message input)
        elif user_id in bot.user_states:
            handle_user_input(bot, chat_id, user_id, text, message)
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")

def handle_settings_command(bot, chat_id, user_id, message_id):
    """Show settings menu"""
    # Check if user is chat admin
    if not is_chat_admin(bot, chat_id, user_id):
        bot.send_message(chat_id, "❌ Only group administrators can access settings.")
        return
    
    keyboard = [
        [{"text": "📝 Edit Leave Message", "callback_data": "edit_leave"}],
        [{"text": "👢 Edit Kick Message", "callback_data": "edit_kick"}],
        [{"text": "🚫 Edit Ban Message", "callback_data": "edit_ban"}],
        [{"text": "🖼️ Change Leave Image", "callback_data": "image_leave"}],
        [{"text": "🖼️ Change Kick Image", "callback_data": "image_kick"}],
        [{"text": "🖼️ Change Ban Image", "callback_data": "image_ban"}],
        [{"text": "🔄 Reset to Default", "callback_data": "reset_default"}]
    ]
    
    bot.send_inline_keyboard(
        chat_id, 
        "⚙️ <b>Farewell Bot Settings</b>\n\nChoose what you'd like to customize:", 
        keyboard
    )

def handle_settings_command_edit(bot, chat_id, user_id, message_id):
    """Edit existing message to show settings menu"""
    keyboard = [
        [{"text": "📝 Edit Leave Message", "callback_data": "edit_leave"}],
        [{"text": "👢 Edit Kick Message", "callback_data": "edit_kick"}],
        [{"text": "🚫 Edit Ban Message", "callback_data": "edit_ban"}],
        [{"text": "🖼️ Change Leave Image", "callback_data": "image_leave"}],
        [{"text": "🖼️ Change Kick Image", "callback_data": "image_kick"}],
        [{"text": "🖼️ Change Ban Image", "callback_data": "image_ban"}],
        [{"text": "🔄 Reset to Default", "callback_data": "reset_default"}]
    ]
    
    bot.edit_message(
        chat_id, 
        message_id,
        "⚙️ <b>Farewell Bot Settings</b>\n\nChoose what you'd like to customize:", 
        keyboard
    )

def handle_callback_query(bot, update):
    """Handle inline keyboard callbacks"""
    try:
        if 'callback_query' not in update:
            return
            
        callback = update['callback_query']
        chat_id = callback.get('message', {}).get('chat', {}).get('id')
        user_id = callback.get('from', {}).get('id')
        message_id = callback.get('message', {}).get('message_id')
        data = callback.get('data', '')
        callback_id = callback.get('id')
        
        if not chat_id or not user_id:
            return
        
        # Answer callback query
        bot.answer_callback_query(callback_id)
        
        # Check if user is admin
        if not is_chat_admin(bot, chat_id, user_id):
            bot.answer_callback_query(callback_id, "Only admins can change settings!")
            return
        
        if data.startswith('edit_'):
            message_type = data.split('_')[1]
            current_message, _ = bot.db.get_message(chat_id, message_type)
            if not current_message:
                current_message = get_default_messages().get(message_type, "Default message")
            
            back_keyboard = [[{"text": "◀️ Back to Settings", "callback_data": "back_to_menu"}]]
            
            bot.edit_message(
                chat_id, 
                message_id, 
                f"📝 <b>Edit {message_type.title()} Message</b>\n\n<i>Current message:</i>\n{current_message}\n\n💬 Send me the new message you want to use:",
                back_keyboard
            )
            
            # Set user state to wait for message input
            bot.user_states[user_id] = {
                'action': 'edit_message',
                'message_type': message_type,
                'chat_id': chat_id
            }
            
        elif data.startswith('image_'):
            message_type = data.split('_')[1]
            back_keyboard = [[{"text": "◀️ Back to Settings", "callback_data": "back_to_menu"}]]
            
            bot.edit_message(
                chat_id,
                message_id,
                f"🖼️ <b>Change {message_type.title()} Image</b>\n\n📷 Send me a photo that you want to use for {message_type} messages.\n\nSupported formats: JPG, PNG, GIF",
                back_keyboard
            )
            
            # Set user state to wait for image
            bot.user_states[user_id] = {
                'action': 'upload_image',
                'message_type': message_type,
                'chat_id': chat_id
            }
            
        elif data == 'reset_default':
            # Reset all settings to default
            conn = sqlite3.connect(bot.db.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM settings WHERE chat_id = ?', (chat_id,))
            conn.commit()
            conn.close()
            
            back_keyboard = [[{"text": "◀️ Back to Settings", "callback_data": "back_to_menu"}]]
            
            bot.edit_message(
                chat_id,
                message_id,
                "✅ <b>Settings Reset</b>\n\nAll messages and images have been reset to default values.",
                back_keyboard
            )
            
        elif data == 'back_to_menu':
            # Go back to main settings menu
            handle_settings_command_edit(bot, chat_id, user_id, message_id)
            
    except Exception as e:
        logger.error(f"Error handling callback: {e}")

def parse_message_entities(text, entities):
    """Parse message entities to convert to HTML formatting"""
    if not entities:
        return text
    
    # Sort entities by offset in reverse order to avoid position shifts
    sorted_entities = sorted(entities, key=lambda x: x.get('offset', 0), reverse=True)
    
    formatted_text = text
    for entity in sorted_entities:
        entity_type = entity.get('type')
        offset = entity.get('offset', 0)
        length = entity.get('length', 0)
        
        if entity_type == 'bold':
            formatted_text = formatted_text[:offset] + '<b>' + formatted_text[offset:offset+length] + '</b>' + formatted_text[offset+length:]
        elif entity_type == 'italic':
            formatted_text = formatted_text[:offset] + '<i>' + formatted_text[offset:offset+length] + '</i>' + formatted_text[offset+length:]
        elif entity_type == 'underline':
            formatted_text = formatted_text[:offset] + '<u>' + formatted_text[offset:offset+length] + '</u>' + formatted_text[offset+length:]
        elif entity_type == 'strikethrough':
            formatted_text = formatted_text[:offset] + '<s>' + formatted_text[offset:offset+length] + '</s>' + formatted_text[offset+length:]
        elif entity_type == 'code':
            formatted_text = formatted_text[:offset] + '<code>' + formatted_text[offset:offset+length] + '</code>' + formatted_text[offset+length:]
    
    return formatted_text

def handle_user_input(bot, chat_id, user_id, text, message):
    """Handle user input when in a specific state"""
    try:
        state = bot.user_states.get(user_id)
        if not state:
            return
        
        if state['action'] == 'edit_message':
            # Parse formatting entities if present
            entities = message.get('entities', [])
            formatted_text = parse_message_entities(text, entities)
            
            # Save the new message
            message_type = state['message_type']
            bot.db.set_message(chat_id, message_type, formatted_text)
            
            back_keyboard = [[{"text": "◀️ Back to Settings", "callback_data": "back_to_menu"}]]
            
            bot.send_inline_keyboard(
                chat_id,
                f"✅ <b>{message_type.title()} message updated!</b>\n\n<i>New message:</i>\n{formatted_text}",
                back_keyboard
            )
            
            # Clear user state
            del bot.user_states[user_id]
            
        elif state['action'] == 'upload_image':
            # Handle photo upload
            if 'photo' in message:
                photo = message['photo'][-1]  # Get highest resolution
                file_id = photo.get('file_id')
                
                if file_id:
                    # Download and save image
                    file_content, filename = bot.download_file(file_id)
                    if file_content:
                        # Create images directory if it doesn't exist
                        os.makedirs('images', exist_ok=True)
                        
                        # Save image
                        message_type = state['message_type']
                        image_path = f"images/{message_type}_{chat_id}_{filename}"
                        
                        with open(image_path, 'wb') as f:
                            f.write(file_content)
                        
                        # Update database
                        current_message, _ = bot.db.get_message(chat_id, message_type)
                        bot.db.set_message(chat_id, message_type, current_message or get_default_messages().get(message_type, ""), image_path)
                        
                        back_keyboard = [[{"text": "◀️ Back to Settings", "callback_data": "back_to_menu"}]]
                        
                        bot.send_inline_keyboard(
                            chat_id,
                            f"✅ <b>{message_type.title()} image updated!</b>\n\n📷 New image has been saved and will be used for {message_type} messages.",
                            back_keyboard
                        )
                    else:
                        bot.send_message(chat_id, "❌ Failed to download image. Please try again.")
                else:
                    bot.send_message(chat_id, "❌ No image found. Please send a photo.")
            else:
                bot.send_message(chat_id, "❌ Please send a photo, not text.")
            
            # Clear user state
            del bot.user_states[user_id]
            
    except Exception as e:
        logger.error(f"Error handling user input: {e}")

def is_chat_admin(bot, chat_id, user_id):
    """Check if user is a chat administrator"""
    try:
        url = f"{bot.base_url}/getChatMember"
        response = requests.get(url, params={'chat_id': chat_id, 'user_id': user_id})
        
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                member = data['result']
                status = member.get('status')
                return status in ['creator', 'administrator']
        
        return False
    except Exception as e:
        logger.error(f"Error checking admin status: {e}")
        return False

def handle_chat_member_update(bot, update):
    """Handle chat member status changes"""
    try:
        if 'chat_member' not in update:
            return
            
        chat_member_update = update['chat_member']
        old_member = chat_member_update.get('old_chat_member', {})
        new_member = chat_member_update.get('new_chat_member', {})
        
        # Only process if user was actually a member before
        if old_member.get('status') not in ['member', 'administrator', 'creator']:
            return
        
        # Check if user left or was banned
        if new_member.get('status') in ['left', 'kicked', 'banned']:
            user = old_member.get('user', {})
            chat_id = chat_member_update.get('chat', {}).get('id')
            
            if not user or not chat_id:
                return
                
            # Determine message type - need to check ban status more carefully
            status = new_member.get('status')
            if status == 'left':
                message_type = 'leave'
            elif status == 'kicked':
                # Check if it's a ban by looking at until_date
                until_date = new_member.get('until_date', 0)
                # If until_date is 0 or very far in future, it's a ban. Otherwise it's a kick.
                if until_date == 0 or until_date > 2147483647:  # Permanent ban
                    message_type = 'ban'
                else:
                    message_type = 'kick'
            else:
                message_type = 'kick'  # fallback
            
            # Get username or fallback to full name
            username = user.get('username')
            if username:
                username = f"@{username}"
            else:
                first_name = user.get('first_name', '')
                last_name = user.get('last_name', '')
                username = f"{first_name} {last_name}".strip()
            
            # Get custom message or use default
            custom_message, custom_image = bot.db.get_message(chat_id, message_type)
            if custom_message:
                message_text = custom_message.format(username=username)
            else:
                message_text = get_default_messages()[message_type].format(username=username)
            
            logger.info(f"User {username} ({message_type}) from chat {chat_id}")
            
            # Send message with image
            image_sent = False
            
            # Try custom image first
            if custom_image and os.path.exists(custom_image):
                result = bot.send_photo(chat_id, custom_image, message_text)
                if result and result.get('ok'):
                    image_sent = True
                    
            # Try default image if custom failed or doesn't exist
            if not image_sent:
                default_image = "assets/farewell_anime.svg"
                if os.path.exists(default_image):
                    result = bot.send_photo(chat_id, default_image, message_text)
                    if result and result.get('ok'):
                        image_sent = True
            
            # Send text only if no image worked
            if not image_sent:
                logger.warning("Failed to send image, sending text only")
                bot.send_message(chat_id, message_text)
                
    except Exception as e:
        logger.error(f"Error in chat member handler: {e}")

def main():
    """Main entry point"""
    logger.info("🎌 Anime Farewell Bot starting...")
    
    bot = TelegramBot(BOT_TOKEN)
    
    # Test bot connection
    test_response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
    if test_response.status_code == 200:
        bot_info = test_response.json()
        if bot_info.get('ok'):
            logger.info(f"✅ Bot connected successfully: @{bot_info['result']['username']}")
        else:
            logger.error("❌ Bot token is invalid")
            return
    else:
        logger.error("❌ Failed to connect to Telegram API")
        return
    
    logger.info("Bot is now monitoring for chat member changes...")
    logger.info("📝 Make sure to:")
    logger.info("   1. Add the bot to your group")
    logger.info("   2. Give it admin permissions")
    logger.info("   3. Enable 'Ban users' permission to see member changes")
    
    offset = None
    
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=30)
            
            if updates and updates.get('ok'):
                for update in updates.get('result', []):
                    # Process different types of updates
                    if 'chat_member' in update:
                        handle_chat_member_update(bot, update)
                    elif 'message' in update:
                        handle_message(bot, update)
                    elif 'callback_query' in update:
                        handle_callback_query(bot, update)
                    
                    # Update offset to avoid processing same update twice
                    offset = update.get('update_id', 0) + 1
            
            time.sleep(1)  # Small delay to prevent overwhelming the API
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            time.sleep(5)  # Wait before retrying

if __name__ == "__main__":
    main()
