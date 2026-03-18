import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "your-token-here")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
DOWNLOAD_PATH = "/tmp/downloads"  # Railway pe /tmp use karo (writable hai)

# Railway pe /tmp folder use karo kyunki baaki folders read-only hain
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)

PLATFORMS = [
    'youtube.com', 'youtu.be', 'instagram.com', 
    'facebook.com', 'fb.watch', 'tiktok.com',
    'twitter.com', 'x.com', 'snapchat.com',
    'bilibili.com', 'vk.com', 'reddit.com'
]
