import sqlite3
from datetime import date

# Create a richer sample database for advanced queries
conn = sqlite3.connect('example.db')
cur = conn.cursor()

# Reset schema to avoid column mismatch from previous runs
cur.execute('PRAGMA foreign_keys = OFF;')
for t in [
    'reviews','terminations','employees','departments',
    'documents','staff','personnel','divisions'
]:
    cur.execute(f'DROP TABLE IF EXISTS {t}')
cur.execute('PRAGMA foreign_keys = ON;')

"""Simple HR schema required by app
Tables:
  - departments (dept_id, dept_name, manager_id)
  - employees  (emp_id, full_name, dept_id, position, annual_salary, join_date, office_location, skills, reports_to)

Note: `skills` and `reports_to` are added to support the app's queries like
"Employees with Python skills over 100k" and "Who reports to John Smith?".
"""

cur.execute('''
CREATE TABLE IF NOT EXISTS departments (
    dept_id INTEGER PRIMARY KEY,
    dept_name TEXT NOT NULL,
    manager_id INTEGER
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS employees (
    emp_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT,
    dept_id INTEGER,
    position TEXT,
    annual_salary INTEGER,
    join_date TEXT,
    office_location TEXT,
    skills TEXT,
    reports_to TEXT,
    FOREIGN KEY (dept_id) REFERENCES departments(dept_id)
)
''')

# ---------------- Seed: departments/employees ----------------------
cur.executemany('INSERT INTO departments (dept_id, dept_name, manager_id) VALUES (?, ?, ?)', [
    (10, 'Engineering', 1),
    (20, 'Marketing', 4),
    (30, 'HR', 6),
    (40, 'Data Science', 7),
])

cur.executemany('''
INSERT INTO employees (emp_id, full_name, email, dept_id, position, annual_salary, join_date, office_location, skills, reports_to)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', [
    (1, 'John Smith', 'john@company.com', 10, 'Director of Engineering', 220000, '2020-04-01', 'SF', 'Leadership, Architecture', None),
    (2, 'Alice Johnson', 'alice@company.com', 10, 'Senior Software Engineer', 165000, '2023-01-15', 'SF', 'Python, React, SQL', 'John Smith'),
    (3, 'Bob Smith', 'bob@company.com', 10, 'Python Developer', 140000, '2024-03-20', 'SF', 'Python, Django, PostgreSQL', 'John Smith'),
    (4, 'Carol White', 'carol@company.com', 20, 'Marketing Manager', 130000, '2022-06-10', 'NYC', 'SEO, Content Strategy', 'Dana Scott'),
    (5, 'David Brown', 'david@company.com', 10, 'Full Stack Engineer', 150000, '2024-01-05', 'SF', 'JavaScript, Python, MongoDB', 'John Smith'),
    (6, 'Eve Davis', 'eve@company.com', 30, 'HR Specialist', 95000, '2023-08-12', 'Austin', 'Recruitment, Employee Relations', 'Sarah Lee'),
    (7, 'Grace Kim', 'grace@company.com', 40, 'ML Engineer', 180000, '2025-02-20', 'Remote', 'Python, ML, NLP', 'John Smith'),
    (8, 'Henry Zhao', 'henry@company.com', 40, 'Data Scientist', 172000, '2025-03-05', 'Remote', 'Python, Pandas, SQL', 'John Smith'),
    (9, 'Iris Patel', 'iris@company.com', 10, 'Engineer', 145000, '2024-07-01', 'SF', 'Python, SQL', 'John Smith'),
    (10, 'Jack Lee', 'jack@company.com', 20, 'Analyst', 90000, '2023-03-10', 'NYC', 'Excel, SEO', 'Dana Scott'),
    # Edge cases
    (11, 'John Johnson', 'john.johnson@company.com', 10, 'Engineer', 130000, '2024-09-01', 'SF', 'Python', 'John Smith'),
    (12, 'John Smith', 'john.smith2@company.com', 20, 'Analyst', 90000, '2023-05-12', 'NYC', 'Excel', 'Dana Scott'),
    (13, 'Empty Case', None, None, None, None, None, '', '', None),
])

conn.commit()
conn.close()

print('Created example.db with simple schema: employees & departments with 13 employees (includes edge cases)')
