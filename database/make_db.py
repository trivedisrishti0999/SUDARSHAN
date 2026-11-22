import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "inventory.db"
if DB_PATH.exists():
    DB_PATH.unlink()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("""
CREATE TABLE parts (
    part_id        TEXT PRIMARY KEY,
    class_name     TEXT NOT NULL,
    name           TEXT NOT NULL,
    specification  TEXT,
    material       TEXT,
    quantity       INTEGER NOT NULL,
    min_stock      INTEGER NOT NULL,
    zone           TEXT,
    rack           TEXT,
    shelf          TEXT,
    bin            TEXT,
    machines       TEXT
)
""")

parts = [
    ("HWS-0601", "Hex_Washer_Screw", "Hex Washer Screw M6 x 20", "M6, 20 mm", "Zinc-plated steel", 240, 100, "A", "R1", "S2", "B03", "CNC Mill X200, Conveyor C4"),
    ("HWS-0801", "Hex_Washer_Screw", "Hex Washer Screw M8 x 25", "M8, 25 mm", "Zinc-plated steel", 60, 100, "A", "R1", "S2", "B04", "Conveyor C4, Press P7"),
    ("HWS-1001", "Hex_Washer_Screw", "Hex Washer Screw M10 x 30", "M10, 30 mm", "Stainless steel", 150, 80, "A", "R1", "S3", "B01", "Press P7"),
    ("HXB-0801", "Hexagonal_Bolt", "Hexagonal Bolt M8 x 40", "M8, 40 mm", "Grade 8.8 steel", 420, 150, "A", "R2", "S1", "B02", "Lathe L100, CNC Mill X200"),
    ("HXB-1001", "Hexagonal_Bolt", "Hexagonal Bolt M10 x 50", "M10, 50 mm", "Grade 8.8 steel", 310, 120, "A", "R2", "S1", "B03", "Lathe L100, Press P7"),
    ("HXB-1201", "Hexagonal_Bolt", "Hexagonal Bolt M12 x 60", "M12, 60 mm", "Grade 10.9 steel", 35, 60, "A", "R2", "S2", "B01", "Press P7, Crane K2"),
    ("PHS-0301", "Philips_Screw", "Philips Screw M3 x 10", "M3, 10 mm", "Zinc-plated steel", 900, 300, "B", "R3", "S1", "B01", "Control Panel CP1, Packaging PK2"),
    ("PHS-0401", "Philips_Screw", "Philips Screw M4 x 16", "M4, 16 mm", "Zinc-plated steel", 650, 300, "B", "R3", "S1", "B02", "Control Panel CP1, Conveyor C4"),
    ("PHS-0501", "Philips_Screw", "Philips Screw M5 x 20", "M5, 20 mm", "Stainless steel", 120, 200, "B", "R3", "S2", "B01", "Packaging PK2"),
    ("PZD-0401", "Pozidriv_Screw", "Pozidriv Screw M4 x 16", "M4, 16 mm", "Zinc-plated steel", 180, 80, "B", "R4", "S1", "B01", "Control Panel CP1"),
    ("PZD-0501", "Pozidriv_Screw", "Pozidriv Screw M5 x 25", "M5, 25 mm", "Zinc-plated steel", 75, 80, "B", "R4", "S1", "B02", "Packaging PK2, Conveyor C4"),
    ("PZD-0601", "Pozidriv_Screw", "Pozidriv Screw M6 x 30", "M6, 30 mm", "Stainless steel", 95, 50, "B", "R4", "S2", "B01", "CNC Mill X200"),
    ("TRX-0301", "Torx_Screw", "Torx Screw M3 x 8 (T10)", "M3, 8 mm, T10", "Black oxide steel", 1100, 400, "C", "R5", "S1", "B01", "Robot Arm RA3, Control Panel CP1"),
    ("TRX-0401", "Torx_Screw", "Torx Screw M4 x 12 (T20)", "M4, 12 mm, T20", "Black oxide steel", 780, 400, "C", "R5", "S1", "B02", "Robot Arm RA3, CNC Mill X200"),
    ("TRX-0601", "Torx_Screw", "Torx Screw M6 x 20 (T30)", "M6, 20 mm, T30", "Stainless steel", 45, 150, "C", "R5", "S2", "B01", "Robot Arm RA3, Press P7"),
]
cur.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", parts)
conn.commit()

print(f"Database created: {DB_PATH}")
print(f"Parts stored: {cur.execute('SELECT COUNT(*) FROM parts').fetchone()[0]}")
print()
print("LOW STOCK ITEMS (quantity below minimum):")
for row in cur.execute("SELECT part_id, name, quantity, min_stock FROM parts WHERE quantity < min_stock ORDER BY part_id"):
    print(f"  {row[0]}  {row[1]:28s} qty {row[2]:4d}  (minimum {row[3]})")
conn.close()