# telegram_bot/get_chat_id_simple.py
import requests

# ✅ توکن واقعی شما
TOKEN = "8344618839:AAG-aU1E6S2mbnEAVCMB0Giqdq-zWefj6Vg"


def get_updates():
    """Get updates from Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

    print("=" * 50)
    print("🤖 Getting Chat IDs from recent messages")
    print("=" * 50)
    print("\n📱 Send a message to your bot first, then run this script\n")

    try:
        response = requests.get(url, timeout=10)
        data = response.json()

        if not data.get('ok'):
            print("❌ Error:", data.get('description'))
            print("\n💡 Tip: Make sure the token is correct")
            return

        updates = data.get('result', [])

        if not updates:
            print("⚠️ No messages found!")
            print("\n📝 Instructions:")
            print("1. Open Telegram")
            print("2. Search: @wvc_reporter_bot")
            print("3. Send any message (like 'Hello' or '/start')")
            print("4. Run this script again\n")
            return

        print(f"✅ Found {len(updates)} message(s):\n")

        chat_ids = set()

        for update in updates:
            if 'message' in update:
                msg = update['message']
                chat = msg['chat']
                user = msg['from']

                chat_id = chat['id']
                chat_ids.add(chat_id)

                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"👤 Name: {user.get('first_name')} {user.get('last_name', '')}")
                print(f"🆔 Username: @{user.get('username', 'N/A')}")
                print(f"💬 Chat ID: {chat_id}")
                print(f"📝 Message: {msg.get('text', 'N/A')}")
                print()

        if chat_ids:
            print("=" * 50)
            print("📋 Summary:")
            print("=" * 50)
            print(f"\nAdd these to your .env file:")
            print(f"TELEGRAM_CHAT_IDS={','.join(map(str, chat_ids))}")
            print("\n" + "=" * 50)

    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error: {e}")
        print("💡 Check your internet connection")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")


if __name__ == "__main__":
    try:
        get_updates()
    except KeyboardInterrupt:
        print("\n\n👋 Stopped by user")