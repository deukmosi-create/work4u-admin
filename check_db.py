import sqlite3

# Connect to your database
conn = sqlite3.connect('applications.db')
cursor = conn.cursor()

# Check table structure
cursor.execute("PRAGMA table_info(applications);")
columns = cursor.fetchall()

print("Current table structure:")
for col in columns:
    print(f"Column: {col[1]}, Type: {col[2]}, Not Null: {col[3]}, Default: {col[4]}")

# Check if there's any data
cursor.execute("SELECT * FROM applications LIMIT 5;")
data = cursor.fetchall()
print(f"\nSample data (first 5 rows):")
for row in data:
    print(row)

conn.close()