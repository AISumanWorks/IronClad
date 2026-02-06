import sqlite3

# Connect to DB
conn = sqlite3.connect('trading_bot.db')
cursor = conn.cursor()

print("🧹 Cleaning Ghost Data from the Brain...")

# Delete all rows from strategy_stats
cursor.execute('DELETE FROM strategy_stats')
conn.commit()

print("✨ Brain Memory Wiped. Ready for real data.")
conn.close()
