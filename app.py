from flask import Flask, render_template, request, flash, redirect, url_for, abort
from flask_mail import Mail, Message
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
app = Flask(__name__)
from html import escape
products = [
    {
        "id": 1,
        "slug": "blue-lotion-dispenser",
        "name": "Blue Lotion Dispenser",
        "category": "Home Essentials",
        "sku": "001",
        "description": "A handmade ceramic lotion dispenser with a blue glaze.",
        "details": (
            "Each piece is shaped and glazed by hand. Natural "
            "variations in color, texture, and form make every "
            "dispenser unique."),
        "price": 45.00,
        "image": "images/dinnerware.jpg",
        "available": True
    },
    {
        "id": 2,
        "slug": "olive-oil-bottle",
        "name": "Olive Oil Bottle",
        "category": "Home Essentials",
        "sku": "002",
        "description": "A functional handmade ceramic bottle.",
        "details": (
            "Each piece is shaped and glazed by hand. Natural "
            "variations in color, texture, and form make every "
            "dispenser unique."),
        "price": 52.00,
        "image": "images/home-essentials.jpg",
        "available": True
    },
    {
        "id": 3,
        "slug": "serving-bowl",
        "name": "Handmade Serving Bowl",
        "category": "Dinnerware",
        "sku": "003",
        "description": "A handmade bowl for serving meals.",
        "details": (
            "Each piece is shaped and glazed by hand. Natural "
            "variations in color, texture, and form make every "
            "dispenser unique."),       
        "price": 65.00,
        "image": "images/gallery-hero.jpg",
        "available": False
    }
]

import os

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

app.secret_key = "your-secret-key"


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/gallery")
def gallery():
    return render_template("gallery.html",
                          products=products)
@app.route("/product/<slug>")
def product_detail(slug):
    product = next(
        (
            item
            for item in products
            if item["slug"] == slug
        ),
        None
    )

    if product is None:
        abort(404)



    return render_template(
        "product.html",
        product=product
    )        
        
        

@app.route("/about")
def about():
    return render_template("about.html")

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


from flask import request, render_template, abort, flash
from markupsafe import escape
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


@app.route("/purchase-request/<slug>", methods=["GET", "POST"])
def purchase_request(slug):

    # Find product
    product = next(
        (
            item
            for item in products
            if item["slug"] == slug
        ),
        None
    )

    if product is None:
        abort(404)

    # Show purchase request form
    if request.method == "GET":
        return render_template(
            "purchase_request.html",
            product=product
        )

    # ----------------------------------------
    # POST: Process purchase request
    # ----------------------------------------

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    fulfillment = request.form.get("fulfillment", "").strip()
    user_message = request.form.get("message", "").strip()

    # Validate quantity
    try:
        quantity = int(request.form.get("quantity", "1"))
    except (TypeError, ValueError):
        quantity = 1

    quantity = max(1, min(quantity, 10))

    # Required fields
    if not name or not email:
        flash(
            "Please enter your name and email address.",
            "error"
        )

        return render_template(
            "purchase_request.html",
            product=product
        )

    # ----------------------------------------
    # SendGrid configuration
    # ----------------------------------------

    if not SENDGRID_API_KEY:
        print("ERROR: SENDGRID_API_KEY is not configured.")

        flash(
            "The email service is not configured. "
            "Please try again later.",
            "error"
        )

        return render_template(
            "purchase_request.html",
            product=product
        )

    # ----------------------------------------
    # Escape customer input for HTML email
    # ----------------------------------------

    safe_name = escape(name)
    safe_email = escape(email)
    safe_phone = escape(phone or "Not provided")
    safe_fulfillment = escape(
        fulfillment or "Not provided"
    )

    safe_user_message = escape(
        user_message or "No additional message provided."
    ).replace("\n", "<br>")

    safe_product_name = escape(
        str(product["name"])
    )

    safe_product_sku = escape(
        str(product["sku"])
    )

    # Safely convert price
    try:
        product_price = float(product["price"])
    except (TypeError, ValueError):
        product_price = 0.0

    # ----------------------------------------
    # Create email
    # ----------------------------------------

    message = Mail(
        from_email="contact@madebynhile.com",
        to_emails="lethaonhi007@gmail.com",
        subject=(
            f"Purchase Request: "
            f"{product['name']} - SKU {product['sku']}"
        ),
        html_content=f"""
            <h2>New Purchase Request</h2>

            <h3>Product Information</h3>

            <p>
                <strong>Item:</strong>
                {safe_product_name}
            </p>

            <p>
                <strong>SKU:</strong>
                {safe_product_sku}
            </p>

            <p>
                <strong>Price:</strong>
                ${product_price:.2f}
            </p>

            <p>
                <strong>Quantity:</strong>
                {quantity}
            </p>

            <hr>

            <h3>Customer Information</h3>

            <p>
                <strong>Name:</strong>
                {safe_name}
            </p>

            <p>
                <strong>Email:</strong>
                {safe_email}
            </p>

            <p>
                <strong>Phone:</strong>
                {safe_phone}
            </p>

            <p>
                <strong>Preferred Fulfillment:</strong>
                {safe_fulfillment}
            </p>

            <hr>

            <h3>Questions or Special Requests</h3>

            <p>
                {safe_user_message}
            </p>
        """
    )

    # ----------------------------------------
    # Send email
    # ----------------------------------------

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)

        response = sg.send(message)

        print(
            "Purchase request email status:",
            response.status_code
        )

        # SendGrid normally returns 202 when accepted
        if response.status_code not in (200, 201, 202):
            print(
                "Unexpected SendGrid status:",
                response.status_code
            )

            flash(
                "Your purchase request could not be sent. "
                "Please try again.",
                "error"
            )

            return render_template(
                "purchase_request.html",
                product=product
            )

    except Exception as error:

        print(
            "Purchase request SendGrid error:",
            repr(error)
        )

        flash(
            "Your purchase request could not be sent. "
            "Please try again.",
            "error"
        )

        return render_template(
            "purchase_request.html",
            product=product
        )

    # ----------------------------------------
    # SUCCESS
    # ----------------------------------------
    # Do NOT redirect to purchase_success.
    # Render the success page directly.

    return render_template(
        "purchase_success.html",
        product=product,
        customer_name=name,
        customer_email=email
    )


if __name__ == "__main__":
    app.run(debug=True)
    



