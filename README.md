# AutoHire-AI
##  live demo

   [Visit autoHire AI](https://autohire-ai-j684.onrender.com/)

# Resume Shortlisting Application

## Overview
This web application, built with Flask, is designed to streamline the resume shortlisting process for hiring companies and provide a platform for job applicants to find and apply for jobs. It manages user authentication, job postings, applications, and resume uploads.

## Features

### For Hiring Companies:
- **Post Job Openings:** Create and manage job listings, including details like title, description, requirements, location, and salary.
- **View Applications:** See a list of applicants who have applied for each job.
- **Shortlist Candidates:** Mark applicants as shortlisted for further steps in the hiring process.
- **Company Dashboard:** View an overview of posted jobs and application statistics.

### For Job Applicants:
- **Find Job Listings:** Browse available job postings.
- **Apply for Jobs:** Submit applications, including uploading a resume.
- **Application Status:** Track the status of your applications (applied, shortlisted, etc.).
- **Applicant Dashboard:** View application history and available jobs.

## Technologies Used
- **Flask:** A Python web framework for building the application.
- **SQLite:** A lightweight, file-based database to store user data, job postings, and applications.
- **Werkzeug:** For handling file uploads and security.
- **HTML/CSS:** For designing the user interface.
- **Bootstrap:** For responsive front-end design.

## Architecture

  ![image](https://github.com/user-attachments/assets/6563e9a1-6d23-407c-8c1d-fd2990f81b21)


## Database Schema

### Tables
```sql
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    user_type TEXT NOT NULL CHECK (user_type IN ('company', 'applicant'))
);

CREATE TABLE jobs (
    job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    location TEXT NOT NULL,
    job_type TEXT NOT NULL,
    salary REAL,
    posted_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    company_id INTEGER NOT NULL,
    FOREIGN KEY (company_id) REFERENCES users(user_id)
);

CREATE TABLE applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    resume_path TEXT NOT NULL,
    applied_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'applied' CHECK (status IN ('applied', 'shortlisted', 'not shortlisted')),
    prediction_score REAL,
    FOREIGN KEY (applicant_id) REFERENCES users(user_id),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

```

## Setup and Installation

### Clone the Repository:

``` bash
git clone https://github.com/Sarita-021/autoHire_AI.git
cd autoHire_AI
```

### Install the Required Python Packages:

``` bash
pip/pip3 install -r requirements.txt
```

### Set Up the Database:
The application uses SQLite, which doesn't require a separate server. The database file (database.db) will be created in the application directory. The necessary tables are automatically created on startup.

### Run the Application:

``` bash
python/python3 app.py
```

### Access the Application:
Open your web browser and go to:
``` cpp
http://127.0.0.1:5000
```

###  Watch Video

[![Watch the video](https://img.youtube.com/vi/ayM1CJU9X-Q/0.jpg)](https://youtu.be/ayM1CJU9X-Q)


## File Structure

``` pgsql
├── app.py
├── database.db
├── uploads/          # Store uploaded resumes
└── templates/
    ├── base.html
    ├── index.html
    ├── register.html
    ├── login.html
    ├── company_dashboard.html
    ├── applicant_dashboard.html
    ├── post_job.html
    ├── job_listings.html
    ├── job_details.html
    ├── apply_job.html
    └── email_template.html
└── static/
    ├── style.css
├── .gitignore
├── README.md
├── requirements.txt
```
Thank You!!!

