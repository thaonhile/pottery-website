from flask import Flask, render_template, request, flash, redirect, url_for
from flask_mail import Mail, Message
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
app = Flask(__name__)



import os

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

app.secret_key = "your-secret-key"


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html")

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        user_message = request.form.get('message')


        message = Mail(
            from_email='contact@madebynhile.com',
            to_emails='lethaonhi007@gmail.com',
            subject=f'New Contact Form from {name}',
            html_content=f"""
            <strong>Name:</strong> {name}<br>
            <strong>Email:</strong> {email}<br><br>
            <strong>Message:</strong><br>
            {user_message}
            """
        )

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        sg.send(message)
        flash('Your message has been sent!')
        return redirect(url_for('contact'))

    return render_template('contact.html')

if __name__ == "__main__":
    app.run(debug=True)
    



