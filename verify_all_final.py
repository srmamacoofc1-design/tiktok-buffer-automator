import sqlite3
import sys
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')
from buffer_client import BufferClient

conn = sqlite3.connect('data/app.db')
c = conn.cursor()
c.execute("""
    SELECT p.id, p.name, a.token, a.org_id, p.channel_id
    FROM profiles p
    JOIN accounts a ON p.account_id = a.id
    ORDER BY p.id
""")

print("=" * 65)
print("STATUS FINAL DAS 6 CONTAS NO BUFFER:")
print("=" * 65)

for pid, pname, token, org_id, ch_id in c.fetchall():
    client = BufferClient(token)
    posts = client.get_scheduled_posts(org_id, ch_id)
    print(f"\n--- Conta #{pid}: @{pname} ({len(posts)}/10 posts na fila) ---")
    sorted_posts = sorted(posts, key=lambda x: x.get('dueAt') or '')
    for idx, p in enumerate(sorted_posts):
        due = p.get('dueAt')
        brt_str = ''
        if due:
            dt = datetime.fromisoformat(due.replace('Z', '+00:00')) - timedelta(hours=3)
            brt_str = dt.strftime('%d/%m %H:%M BRT')
        txt = (p.get('text') or '').replace('\n', ' ')[:35]
        print(f"  #{idx+1}: {brt_str} | {txt}...")
