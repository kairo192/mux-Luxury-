p = r"c:\Users\MOURAD\Desktop\mix luxury\luxe-ecommerce\backend\app\database.py"
with open(p, "r", encoding="utf-8") as f:
    code = f.read()

old_get_conn = """    conn = sqlite3.connect(DB_PATH, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")"""

new_get_conn = """    target_db_path = os.getenv("LUXE_SQLITE_PATH") or DB_PATH
    conn = sqlite3.connect(target_db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    conn.execute("PRAGMA cache_size = -64000;")
    conn.execute("PRAGMA mmap_size = 268435456;")
    conn.execute("PRAGMA temp_store = MEMORY;")"""

assert old_get_conn in code, "old_get_conn not found in database.py"
code = code.replace(old_get_conn, new_get_conn, 1)

with open(p, "w", encoding="utf-8", newline="\r\n") as f:
    f.write(code)

print("Updated database.py with dynamic path and performance PRAGMAs!")
