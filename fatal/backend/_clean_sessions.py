import sys
sys.path.insert(0, '.')
import db

c = db.get_connection()
c.execute("DELETE FROM chat_messages")
c.execute("DELETE FROM chat_threads")
c.execute("DELETE FROM match_sessions")
c.commit()
print("Cleaned all sessions, threads, messages")
