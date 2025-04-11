from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
import sqlite3
from datetime import datetime
import os
from flask import send_file
from werkzeug.utils import secure_filename
from models.screening_pipeline import run_screening_pipeline
from models.resume_parser import extract_and_clean_text
from models.screening_pipeline import run_single_resume_screening
from flask import session
import smtplib
from email.mime.text import MIMEText
from scripts.init_db import get_db_connection
from utils.email_sender import send_email
from dotenv import load_dotenv
import uuid

load_dotenv()

app = Flask(__name__)


app.secret_key = os.urandom(24)
DATABASE = 'database.db'
JD_PATH = 'data/job_description.csv'
UPLOAD_FOLDER = 'uploads'
#app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}  




@app.context_processor
def inject_now():
    from datetime import datetime
    return {'now': datetime.now()}
now = datetime.now() 

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/resume/<filename>')
def serve_resume(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def index():
    """Home page."""
    return render_template('index.html')


@app.route("/run_screening")
def run_screening():
    jd_path = "data/job_description.csv"
    resumes_folder = "data/CVs"

    results = run_screening_pipeline(jd_path, resumes_folder)

    return render_template("screening_results.html", candidates=results)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        user_type = request.form['userType']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (username, password, email, user_type) VALUES (?, ?, ?, ?)",
                (username, password, email, user_type),
            )
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists.', 'danger')
            return render_template('register.html', now=now)
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST']) 
def login():
  
    """Login page."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?', 
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session['user_id'] = user['user_id']  # FIXED
            session['username'] = user['username']
            session['user_type'] = user['user_type']
            flash('Login successful!', 'success')

            if user['user_type'] == 'company':
                # Optionally fetch actual company_name from another table if you want
                return redirect(url_for('company_dashboard'))
            else:
                return redirect(url_for('applicant_dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')



@app.route('/logout')
def logout():
    """Logout route."""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))




@app.route('/upload_resume', methods=['GET', 'POST'])  
def upload_resume():
    if 'user_id' not in session or session.get('user_type') != 'applicant':
        flash("Please log in as an applicant to upload a resume.", "warning")
        return redirect(url_for('login'))

    score = None
    status = None
    original_filename = None

    conn = get_db_connection()
    cursor = conn.cursor()
    jobs = cursor.execute("SELECT job_id, title FROM jobs").fetchall()

    if request.method == 'POST':
        job_id_str = request.form.get('job_id')

        # Validate job_id from dropdown
        if not job_id_str or not job_id_str.isdigit():
            flash("Please select a valid job from the dropdown.", "danger")
            return redirect(url_for('upload_resume'))
        job_id = int(job_id_str)
        file = request.files['resume']

        if file and file.filename.endswith('.pdf'):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            original_filename = secure_filename(file.filename)
            filename = f"{timestamp}_{original_filename}"
            save_path = os.path.join('uploads', filename)
            file.save(save_path)

            parsed_resumes = {filename: extract_and_clean_text(save_path)}

            # run screening
            shortlisted, score_map = run_single_resume_screening(
                jd_path='data/job_description.csv',
                parsed_resumes=parsed_resumes
            )

            score = round(score_map.get(filename, 0) * 100, 2)
            status = "shortlisted" if score >= 80 else "applied"
            applicant_id = session.get('user_id')

            cursor.execute(
                '''INSERT INTO applications (applicant_id, job_id, resume_path, status, prediction_score)
                   VALUES (?, ?, ?, ?, ?)''',
                (applicant_id, job_id, save_path, status, score)
            )
            conn.commit()

            if status == "shortlisted":
                flash("Congrats! You’ve been shortlisted.", "success")
            else:
                flash("Thanks for applying. We'll get back to you soon.", "info")

    conn.close()

    return render_template(
        'upload_resume.html',
        status=status,
        score=score,
        filename=original_filename,
        jobs=jobs
    )




@app.route('/company_dashboard')
def company_dashboard():
    if 'user_id' not in session or session['user_type'] != 'company':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    company_id = session['user_id']
    company_name = session.get('company_name', 'Unknown Company')

    jobs = cursor.execute(
        'SELECT * FROM jobs WHERE company_id = ?',
        (company_id,)
    ).fetchall()

    total_applications = cursor.execute('''
        SELECT COUNT(applications.application_id)
        FROM applications
        JOIN jobs ON applications.job_id = jobs.job_id
        WHERE jobs.company_id = ?
    ''', (company_id,)).fetchone()[0] or 0

    shortlisted_applications = cursor.execute('''
        SELECT applications.*, users.username, users.email, jobs.title
        FROM applications
        JOIN users ON applications.applicant_id = users.user_id
        JOIN jobs ON applications.job_id = jobs.job_id
        WHERE applications.status = 'shortlisted'
        AND jobs.company_id = ?
    ''', (company_id,)).fetchall()

    conn.close()
    return render_template(
        'company_dashboard.html',
        company_name=company_name,
        jobs=jobs,
        total_applications=total_applications,
        shortlisted_applications=shortlisted_applications,
       
    )

@app.route('/applicant_dashboard')
def applicant_dashboard():
    """Applicant dashboard page."""
    if 'user_id' not in session or session['user_type'] != 'applicant':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    applicant_id = session['user_id']

    # Get applications by the applicant
    applications = cursor.execute(
        '''SELECT applications.*, jobs.title
           FROM applications 
           JOIN jobs ON applications.job_id = jobs.job_id
           WHERE applications.applicant_id = ?''',
        (applicant_id,),
    ).fetchall()

    # Get all jobs
    jobs = cursor.execute('SELECT jobs.*, users.username as company_name FROM jobs JOIN users ON jobs.company_id = users.user_id').fetchall()
    conn.close()
    return render_template('applicant_dashboard.html', applications=applications, jobs=jobs)

@app.route('/company/post_job', methods=['GET', 'POST'])
def post_job():
    # Ensure only logged-in company users can access this
    if 'user_id' not in session or session.get('user_type') != 'company':
        flash("Please log in as a company to post a job.", "warning")
        return redirect(url_for('login'))  # or your home page

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        requirements = request.form['requirements']
        location = request.form['location']
        job_type = request.form['job_type']
        salary = request.form['salary']
        company_id = session.get('user_id')  # Now safely guaranteed to be present

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO jobs (title, description, requirements, location, job_type, salary, company_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, requirements, location, job_type, salary, company_id))
        conn.commit()
        conn.close()

        flash("Job posted successfully!", "success")
        return redirect(url_for('job_listings'), now=now)

    return render_template('post_job.html', now=now)


@app.route('/job_listings')
def job_listings():
    """Job listings page for companies."""
    if 'user_id' not in session or session['user_type'] != 'company':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    company_id = session['user_id']

    # Fetch jobs posted by the logged-in company
    jobs = cursor.execute(
        '''SELECT jobs.*, COUNT(applications.application_id) as applications
           FROM jobs
           LEFT JOIN applications ON jobs.job_id = applications.job_id
           WHERE jobs.company_id = ?
           GROUP BY jobs.job_id''',
        (company_id,),
    ).fetchall()
    conn.close()
    return render_template('job_listings.html', jobs=jobs, now=now)
@app.route('/company/jobs')
def view_jobs():
    if 'user_id' not in session or session.get('user_type') != 'company':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    company_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    jobs = cursor.execute(
        '''SELECT * FROM jobs WHERE company_id = ?''',
        (company_id,)
    ).fetchall()
    conn.close()

    return render_template('view_jobs.html', jobs=jobs)

@app.route('/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    if 'user_id' not in session or session['user_type'] != 'company':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure the job belongs to the logged-in company
    job = cursor.execute('SELECT * FROM jobs WHERE job_id = ? AND company_id = ?', (job_id, session['user_id'])).fetchone()
    if not job:
        conn.close()
        flash('Job not found or unauthorized.', 'danger')
        return redirect(url_for('job_listings'))

    # Delete related applications first (to maintain foreign key integrity, if enforced)
    cursor.execute('DELETE FROM applications WHERE job_id = ?', (job_id,))
    cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
    conn.commit()
    conn.close()

    flash('Job deleted successfully.', 'success')
    return redirect(url_for('job_listings'))



@app.route('/company/job/<int:job_id>/applicants')
def view_applicants(job_id):
    conn = get_db_connection()
    applicants = conn.execute('''
        SELECT a.*, u.username, u.email
        FROM applications a
        JOIN users u ON a.applicant_id = u.user_id
        WHERE a.job_id = ?
        ORDER BY prediction_score DESC
    ''', (job_id,)).fetchall()
    conn.close()
    return render_template('view_applicants.html', applicants=applicants, job_id=job_id)


'''@app.route('/view_resume/<int:applicant_id>')
def view_resume(applicant_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch resume path from applications table
    cursor.execute('SELECT resume_path FROM applications WHERE applicant_id = ?', (applicant_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        relative_path = result['resume_path'].replace('\\', '/')  # ensure consistent slashes
        full_path = os.path.join(os.getcwd(), relative_path)  # absolute path

        if os.path.exists(full_path):
            return send_file(full_path)
        else:
            return f"Resume file not found at {full_path}", 404
    else:
        return "Resume not found", 404'''


@app.route('/schedule_interview/<int:application_id>', methods=['POST'])
def schedule_interview(application_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get the application and applicant email
    cursor.execute('SELECT applicant_email, job_id FROM applications WHERE id = ?', (application_id,))
    application = cursor.fetchone()

    if not application:
        flash('Application not found.', 'danger')
        conn.close()
        return redirect(url_for('company_dashboard'))

    applicant_email = application['applicant_email']
    job_id = application['job_id']

    # Optionally update application status
    cursor.execute('UPDATE applications SET interview_scheduled = 1 WHERE id = ?', (application_id,))
    conn.commit()
    conn.close()

    '''# ---- Email Notification ---- #
    subject = "Interview Scheduled for Your Job Application"
    body = f"""
    Dear Applicant,

    Congratulations! You've been shortlisted and an interview has been scheduled for your job application (Job ID: {job_id}).

    Please check your email/calendar for more details or await further instructions.

    Regards,
    Recruitment Team
    """
'''
    try:
        sender_email = os.environ.get("EMAIL_ADDRESS")
        sender_password = os.environ.get("EMAIL_PASSWORD")

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = applicant_email

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)

        flash('Interview scheduled and email sent to the applicant.', 'success')
    except Exception as e:
        print(f"Error sending email: {e}")
        flash('Interview scheduled but failed to send email.', 'warning')

    return redirect(url_for('view_applicants', job_id=job_id))
@app.route('/job_details/<int:job_id>')
def job_details(job_id):
    """Job details page."""
    conn = get_db_connection()
    cursor = conn.cursor()

    job = cursor.execute(
        '''SELECT jobs.*, users.username as company_name
           FROM jobs
           JOIN users ON jobs.company_id = users.user_id
           WHERE jobs.job_id = ?''',
        (job_id,),
    ).fetchone()

    if not job:
        flash('Job not found.', 'danger')
        return redirect(url_for('index'))
    
    if session.get('user_type') == 'applicant':
        return render_template('job_details.html', job=job)
    elif session.get('user_type') == 'company':
        return render_template('job_details.html', job=job)
    else:
        return render_template('job_details.html', job=job)


@app.route('/apply_job/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    """Apply for a job page."""
    if 'user_id' not in session or session['user_type'] != 'applicant':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    applicant_id = session['user_id']

    # Check if the applicant has already applied for this job
    application = cursor.execute(
        'SELECT * FROM applications WHERE applicant_id = ? AND job_id = ?',
        (applicant_id, job_id),
    ).fetchone()

    if application:
        # Fetch the application status
        application_status = application['status']
        conn.close()
        return render_template('apply_job.html', job=application, application_status=application_status)


    job = cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,)).fetchone()
    if not job:
        flash('Job not found.', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'resume' not in request.files:
            flash('No resume uploaded.', 'danger')
            return render_template('apply_job.html', job=job)
        resume = request.files['resume']
        if resume.filename == '':
            flash('No resume selected.', 'danger')
            return render_template('apply_job.html', job=job)
        if resume and allowed_file(resume.filename):
            ext = resume.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            resume_path = os.path.join('uploads', filename)
            resume.save(resume_path)
            cursor.execute(
                 'INSERT INTO applications (applicant_id, job_id, resume_path) VALUES (?, ?, ?)',
                   (applicant_id, job_id, resume_path),
                   ) 
            conn.commit()
            conn.close()
            flash('Application submitted successfully!', 'success')
            return redirect(url_for('applicant_dashboard'))
        else:
            flash('Invalid file type. Please upload a PDF, DOC, or DOCX file.', 'danger')
            return render_template('apply_job.html', job=job)

    return render_template('apply_job.html', job=job)



@app.route('/shortlisting/<int:job_id>', methods=['GET', 'POST']) 
def shortlisting(job_id):
    """Shortlisting page for companies to view applications for a job."""
    if 'user_id' not in session or session['user_type'] != 'company':
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()
    company_id = session['user_id']

    # ensure the job belongs to the logged-in company
    job = cursor.execute(
        'SELECT * FROM jobs WHERE job_id = ? AND company_id = ?', 
        (job_id, company_id)
    ).fetchone()

    if not job:
        flash('Job not found or does not belong to your company.', 'danger')
        return redirect(url_for('job_listings'))

    if request.method == 'POST':
        applicant_id = request.form['applicant_id']

        # check the current status
        application_status = cursor.execute(
            'SELECT status FROM applications WHERE job_id = ? AND applicant_id = ?', 
            (job_id, applicant_id)
        ).fetchone()[0]

        if application_status == 'applied':
            cursor.execute(
                'UPDATE applications SET status = "shortlisted" WHERE job_id = ? AND applicant_id = ?',
                (job_id, applicant_id),
            )
            conn.commit()

            # Fetch candidate's email
            user = cursor.execute(
                'SELECT username, email FROM users WHERE user_id = ?',
                (applicant_id,)
            ).fetchone()
            
            if user and user['email']:
                subject = f"Shortlisted for {job['title']}"
                content = f"""
Hi {user['username']},

Congratulations! You've been shortlisted for the position of "{job['title']}" at {job['company_name'] if 'company_name' in job.keys() else 'the company'}.

We will be in touch with the next steps soon.

Best regards,  
AutoHire AI Team
"""
                try:
                    send_email(user['email'], subject, content)
                    flash('Applicant shortlisted and notified via email.', 'success')
                except Exception as e:
                    flash(f'Applicant shortlisted, but email failed: {str(e)}', 'warning')
            else:
                flash('Applicant shortlisted. Email not available.', 'warning')

        elif application_status == 'shortlisted':
            cursor.execute(
                'UPDATE applications SET status = "not shortlisted" WHERE job_id = ? AND applicant_id = ?',
                (job_id, applicant_id),
            )
            conn.commit()
            flash('Applicant Not Shortlisted.', 'success')

        else:
            flash('Applicant already shortlisted or not shortlisted.', 'warning')

        return redirect(url_for('shortlisting', job_id=job_id))

    applications = cursor.execute(
        '''SELECT applications.*, users.username, users.email
           FROM applications
           JOIN users ON applications.applicant_id = users.user_id
           WHERE applications.job_id = ?''',
        (job_id,),
    ).fetchall()

    conn.close()
    return render_template('shortlisting.html', job=job, applications=applications)

@app.route('/test_email')
def test_email():
    try:
        send_email('ggkaushik2004@gmail.com', 'Test Email', ' a test email from Flask to check the email-notifier...')
        return 'Test email sent successfully.'
    except Exception as e:
        return f'Error sending email: {e}'

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Render provides PORT env variable
    app.run(host="0.0.0.0", port=port)  


