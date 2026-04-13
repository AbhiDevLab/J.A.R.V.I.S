import csv
import sqlite3

con = sqlite3.connect("jarvis.db")
cursor = con.cursor()

query = "CREATE TABLE IF NOT EXISTS sys_command(id integer primary key, name VARCHAR(100), path VARCHAR(1000))"
cursor.execute(query)

# query = "INSERT INTO sys_command values(null, 'word', 'C:\\Program Files\\Microsoft Office\\Office16\\WINWORD.EXE')"
# cursor.execute(query)
# con.commit()

# FOR DELETING DUPLICATE RECORDS OF WORD IN THE TABLE

# cursor.execute("DELETE FROM sys_command WHERE name = 'word' AND id NOT IN (SELECT MIN(id) FROM sys_command WHERE name = 'word')")
# con.commit()


cursor.execute("CREATE TABLE IF NOT EXISTS web_command(id integer primary key, name VARCHAR(100), url VARCHAR(1000))")

# query = "INSERT INTO web_command values(null, 'youtube', 'https://www.youtube.com/')"
# cursor.execute(query)
# con.commit()

# query = "UPDATE sys_command SET path = 'start onenote:' WHERE name = 'one note'"
# cursor.execute(query)
# con.commit()

# query = "INSERT INTO sys_command VALUES (NULL, 'whatsapp', 'start whatsapp:')"
# cursor.execute(query)
# con.commit()

# query = "Delete FROM web_command WHERE id = 2"
# cursor.execute(query)
# con.commit()

# Create a table with the desired columns
cursor.execute('''CREATE TABLE IF NOT EXISTS contacts (id integer primary key, name VARCHAR(200), mobile_no VARCHAR(255), email VARCHAR(255) NULL)''')


# cursor.execute("DELETE FROM CONTACTS")
# con.commit()


### CLEANER SCRIPT OF CONTACTS CSV i.e. CONTACTS_CLEANER CSV ###

# def normalize_phone(phone):
#     if not phone:
#         return None
#     phone = str(phone).strip().replace(" ", "")
#     try:
#         if "e" in phone.lower():
#             phone = str(int(float(phone)))  # from scientific notation
#     except:
#         pass
#     if not phone.startswith("+91"):
#         # Ensure it has last 10 digits
#         digits = ''.join(filter(str.isdigit, phone))
#         if len(digits) >= 10:
#             phone = "+91" + digits[-10:]
#         else:
#             phone = None  # Invalid number
#     return phone

# def build_full_name(row):
#     first = row.get("First Name", "").strip()
#     middle = row.get("Middle Name", "").strip()
#     last = row.get("Last Name", "").strip()
#     full_name = " ".join(part for part in [first, middle, last] if part)
#     return full_name if full_name else None

# input_file = "contacts(1).csv"
# output_file = "updated_contacts.csv"

# with open(input_file, 'r', encoding='utf-8') as infile, open(output_file, 'w', newline='', encoding='utf-8') as outfile:
#     reader = csv.DictReader(infile)
#     fieldnames = ["name", "mobile_no", "email"]
#     writer = csv.DictWriter(outfile, fieldnames=fieldnames)
#     writer.writeheader()

#     for row in reader:
#         name = build_full_name(row)
#         phone = normalize_phone(row.get("Phone 1 - Value") or row.get("Phone"))
#         email = row.get("E-mail 1 - Value", "").strip()

#         if phone:  # Only write if phone is valid
#             writer.writerow({"name": name, "mobile_no": phone, "email": email})



# # ## FINALLY INSERTING THE CONTACTS INTO DB ###

# con = sqlite3.connect("jarvis.db")
# cursor = con.cursor()

# with open('updated_contacts.csv', 'r', encoding='utf-8') as csvfile:
#     reader = csv.DictReader(csvfile)
#     inserted = 0

#     for row in reader:
#         name = row["name"].strip() if row["name"] else None
#         mobile = row["mobile_no"].strip().replace(" ", "") if row["mobile_no"] else None
#         email = row["email"].strip() if row["email"] else None

#         if not mobile:
#             continue  # Skip invalid records

#         # Insert only if this mobile_no doesn't already exist
#         cursor.execute("SELECT 1 FROM contacts WHERE REPLACE(mobile_no, ' ', '') = ?", (mobile,))
#         exists = cursor.fetchone()

#         if not exists:
#             cursor.execute(
#                 "INSERT INTO contacts (name, mobile_no, email) VALUES (?, ?, ?)",
#                 (name, mobile, email)
#             )
#             inserted += 1

# con.commit()
# con.close()

### Inserting single contacts ###

# query = "INSERT INTO contacts VALUES(null, 'Shubham Bhaiya (CIIE)', '+91 7528026837', null)"
# cursor.execute(query)
# con.commit()

# Add camera command
# cursor.execute("INSERT OR REPLACE INTO sys_command (name, path) VALUES ('camera', 'start microsoft.windows.camera:')")
# con.commit()
# con.close()