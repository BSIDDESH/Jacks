"""Removes study-plan data so the planner can be tested from a clean slate.
Run from the jacks-backend folder: python reset_study.py"""
import sqlite3

conn = sqlite3.connect("jacks.db")
events = conn.execute("DELETE FROM calendar_events WHERE title LIKE 'Study:%'").rowcount
proposals = conn.execute("DELETE FROM proposals WHERE title LIKE 'Study:%'").rowcount
conn.commit()
conn.close()
print(f"Removed {events} study events and {proposals} study proposals.")
