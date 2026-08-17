import os
from decimal import Decimal, InvalidOperation
from functools import wraps
from html import escape
from slugify import slugify
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "temporary-local-development-key"
)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

database_url = os.getenv("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = (
    database_url or "sqlite:///products.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

import random
import string


def generate_sku():
    while True:
        characters = string.ascii_uppercase + string.digits

        sku = "SKU-" + "".join(
            random.choices(characters, k=6)
        )

        existing_sku = Product.query.filter_by(
            sku=sku
        ).first()

        if not existing_sku:
            return sku
def generate_unique_slug(name):
    base_slug = slugify(name)
    slug = base_slug
    counter = 2

    while Product.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug

# =========================================================
# PRODUCT DATABASE MODEL
# =========================================================

class Product(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    slug = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    sku = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    category = db.Column(
        db.String(100),
        nullable=False
    )

    description = db.Column(
        db.Text,
        nullable=False
    )

    details = db.Column(
        db.Text,
        nullable=True
    )

    price = db.Column(
        db.Numeric(10, 2),
        nullable=False
    )

    image_url = db.Column(
        db.String(500),
        nullable=False
    )

    available = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    def __repr__(self):
        return f"<Product {self.name}>"

class ProductImage(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True
    )

    image_url = db.Column(
        db.String(500),
        nullable=False
    )

    alt_text = db.Column(
        db.String(200),
        nullable=True
    )

    display_order = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("product.id"),
        nullable=False
    )

    product = db.relationship(
        "Product",
        backref=db.backref(
            "additional_images",
            lazy=True,
            order_by="ProductImage.display_order"
        )
    )

    def __repr__(self):
        return f"<ProductImage {self.image_url}>"

# Create the Product table if it does not already exist.
# This works with local SQLite and Render PostgreSQL.
with app.app_context():
    db.create_all()


# =========================================================
# ADMIN AUTHENTICATION
# =========================================================

def admin_credentials_are_valid(username, password):
    expected_username = os.getenv("ADMIN_USERNAME")
    expected_password = os.getenv("ADMIN_PASSWORD")

    if not expected_username or not expected_password:
        return False

    return (
        username == expected_username
        and password == expected_password
    )


def require_admin(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        authentication = request.authorization

        if (
            not authentication
            or not admin_credentials_are_valid(
                authentication.username,
                authentication.password
            )
        ):
            return Response(
                "Administrator authentication required.",
                401,
                {
                    "WWW-Authenticate":
                    'Basic realm="Product Administration"'
                }
            )

        return view_function(*args, **kwargs)

    return decorated_function


# =========================================================
# ADMIN: ADD PRODUCT
# =========================================================

@app.route("/admin/products/add", methods=["GET", "POST"])
@require_admin
def admin_add_product():
    if request.method == "POST":
        action = request.form.get("action", "gallery")
        name = request.form.get("name", "").strip()
        slug = generate_unique_slug(name)
        sku = generate_sku()
        category = request.form.get("category", "").strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        details = request.form.get(
            "details",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            ""
        ).strip()

        image_url = request.form.get(
            "image_url",
            ""
        ).strip()

        additional_image_urls = [
            request.form.get(
                "additional_image_1",
                ""
            ).strip(),

            request.form.get(
                "additional_image_2",
                ""
            ).strip(),

            request.form.get(
                "additional_image_3",
                ""
            ).strip(),
        ]

        available = request.form.get("available") == "on"

        if (
            not name
            or not slug
            or not sku
            or not category
            or not description
            or not price_text
            or not image_url
        ):
            flash(
                "Please complete all required product fields.",
                "error"
            )

            return render_template(
                "admin_product_form.html"
            )

        existing_slug = Product.query.filter_by(
            slug=slug
        ).first()

        if existing_slug:
            flash(
                "A product with this URL slug already exists.",
                "error"
            )

            return render_template(
                "admin_product_form.html"
            )


        try:
            price = Decimal(price_text)

            if price < 0:
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash(
                "Please enter a valid product price.",
                "error"
            )

            return render_template(
                "admin_product_form.html"
            )

        product = Product(
            name=name,
            slug=slug,
            sku=sku,
            category=category,
            description=description,
            details=details,
            price=price,
            image_url=image_url,
            available=available
        )

        try:
            db.session.add(product)

            # Flush saves the product temporarily so product.id is available.
            db.session.flush()

            for display_order, additional_url in enumerate(
                additional_image_urls,
                start=1
            ):
                if not additional_url:
                    continue

                product_image = ProductImage(
                    image_url=additional_url,
                    alt_text=product.name,
                    display_order=display_order,
                    product_id=product.id
                )

                db.session.add(product_image)

            db.session.commit()

        except Exception as error:
            db.session.rollback()

            print(
                f"Database product error: {repr(error)}",
                flush=True
            )

            flash(
                "The product could not be saved. "
                "Please check the information and try again.",
                "error"
            )

            return render_template(
                "admin_product_form.html"
            )

        flash(
            f"{product.name} was added successfully.",
            "success"
        )

        if action == "add_another":
            return redirect(
                url_for("admin_add_product")
            )

        return redirect(
            url_for(
                "product_detail",
                slug=product.slug
            )
        )


    return render_template(
        "admin_product_form.html"
    )
@app.route("/admin/products")
@require_admin
def admin_products():
    products = Product.query.order_by(
        Product.id.desc()
    ).all()

    return render_template(
        "admin_products.html",
        products=products
    )
@app.route("/admin/products/<int:product_id>/edit",
    methods=["GET", "POST"]
)
@require_admin
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == "POST":
        name = request.form.get(
            "name",
            ""
        ).strip()

        slug = request.form.get(
            "slug",
            ""
        ).strip().lower()

        sku = request.form.get(
            "sku",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        details = request.form.get(
            "details",
            ""
        ).strip()

        price_text = request.form.get(
            "price",
            ""
        ).strip()

        image_url = request.form.get(
            "image_url",
            ""
        ).strip()

        additional_image_urls = [
            request.form.get(
                "additional_image_1",
                ""
            ).strip(),

            request.form.get(
                "additional_image_2",
                ""
            ).strip(),

            request.form.get(
                "additional_image_3",
                ""
            ).strip(),
            request.form.get(
                "additional_image_4",
                ""
            ).strip(),
        ]

        available = (
            request.form.get("available") == "1"
        )

        # Validate required fields
        if (
            not name
            or not slug
            or not sku
            or not category
            or not description
            or not price_text
            or not image_url
        ):
            flash(
                "Please complete all required product fields.",
                "error"
            )

            return render_template(
                "admin_edit_product.html",
                product=product
            )

        # Check whether another product uses the same slug
        duplicate_slug = Product.query.filter(
            Product.slug == slug,
            Product.id != product.id
        ).first()

        if duplicate_slug:
            flash(
                "Another product already uses this URL slug.",
                "error"
            )

            return render_template(
                "admin_edit_product.html",
                product=product
            )

        # Check whether another product uses the same SKU
        duplicate_sku = Product.query.filter(
            Product.sku == sku,
            Product.id != product.id
        ).first()

        if duplicate_sku:
            flash(
                "Another product already uses this SKU.",
                "error"
            )

            return render_template(
                "admin_edit_product.html",
                product=product
            )

        # Validate price
        try:
            price = Decimal(price_text)

            if price < 0:
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash(
                "Please enter a valid product price.",
                "error"
            )

            return render_template(
                "admin_edit_product.html",
                product=product
            )

        # Update main product information
        product.name = name
        product.slug = slug
        product.sku = sku
        product.category = category
        product.description = description
        product.details = details
        product.price = price
        product.image_url = image_url
        product.available = available

        try:
            # Remove the old additional-image records
            ProductImage.query.filter_by(
                product_id=product.id
            ).delete(
                synchronize_session=False
            )

            # Add the current additional-image URLs
            for display_order, additional_url in enumerate(
                additional_image_urls,
                start=1
            ):
                if not additional_url:
                    continue

                product_image = ProductImage(
                    image_url=additional_url,
                    alt_text=product.name,
                    display_order=display_order,
                    product_id=product.id
                )

                db.session.add(product_image)

            # Save the product and image changes together
            db.session.commit()

        except Exception as error:
            db.session.rollback()

            print(
                f"Product update error: {repr(error)}",
                flush=True
            )

            flash(
                "The product could not be updated.",
                "error"
            )

            return render_template(
                "admin_edit_product.html",
                product=product
            )

        flash(
            f"{product.name} was updated successfully.",
            "success"
        )

        return redirect(
            url_for("admin_products")
        )

    additional_images = product.additional_images or []

    return render_template(
        "admin_edit_product.html",
        product=product,
        additional_images=additional_images
    )

# =========================================================
# REGULAR WEBSITE PAGES
# =========================================================

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/gallery")
def gallery():
    products = Product.query.order_by(
        Product.id.desc()
    ).all()

    return render_template(
        "gallery.html",
        products=products
    )


# =========================================================
# PRODUCT DETAILS
# =========================================================

@app.route("/product/<slug>")
def product_detail(slug):
    product = Product.query.filter_by(
        slug=slug
    ).first_or_404()

    products = Product.query.order_by(
        Product.id.asc()
    ).all()

    product_index = next(
        (
            index
            for index, item in enumerate(products)
            if item.id == product.id
        ),
        None
    )

    previous_product = None
    next_product = None

    if product_index is not None:
        if product_index > 0:
            previous_product = products[product_index - 1]

        if product_index < len(products) - 1:
            next_product = products[product_index + 1]

    return render_template(
        "product.html",
        product=product,
        previous_product=previous_product,
        next_product=next_product
    )


# =========================================================
# CONTACT FORM
# =========================================================

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        user_message = request.form.get("message", "").strip()

        if not name or not email or not user_message:
            flash(
                "Please complete your name, email, and message.",
                "error"
            )

            return render_template("contact.html")

        if not SENDGRID_API_KEY:
            flash(
                "The email service is not configured.",
                "error"
            )

            return render_template("contact.html")

        safe_name = escape(name)
        safe_email = escape(email)

        safe_message = escape(
            user_message
        ).replace(
            "\n",
            "<br>"
        )

        message = Mail(
            from_email="contact@madebynhile.com",
            to_emails="lethaonhi007@gmail.com",
            subject=f"New Contact Form Message from {name}",
            html_content=f"""
                <h2>New Contact Form Message</h2>

                <p>
                    <strong>Name:</strong>
                    {safe_name}
                </p>

                <p>
                    <strong>Email:</strong>
                    {safe_email}
                </p>

                <p>
                    <strong>Message:</strong>
                </p>

                <p>
                    {safe_message}
                </p>
            """
        )

        try:
            sendgrid = SendGridAPIClient(
                SENDGRID_API_KEY
            )

            response = sendgrid.send(message)

            print(
                f"Contact email status: "
                f"{response.status_code}",
                flush=True
            )

        except Exception as error:
            print(
                f"Contact form SendGrid error: "
                f"{repr(error)}",
                flush=True
            )

            if hasattr(error, "body"):
                print(
                    f"SendGrid response: {error.body}",
                    flush=True
                )

            flash(
                "Your message could not be sent. "
                "Please try again.",
                "error"
            )

            return render_template("contact.html")

        return redirect(
            url_for("contact_success")
        )

    return render_template("contact.html")


@app.route("/contact-success")
def contact_success():
    return render_template(
        "contact_success.html"
    )


# =========================================================
# PURCHASE REQUEST
# =========================================================

@app.route(
    "/purchase-request/<slug>",
    methods=["GET", "POST"]
)
def purchase_request(slug):
    product = Product.query.filter_by(
        slug=slug
    ).first_or_404()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        fulfillment = request.form.get(
            "fulfillment",
            ""
        ).strip()

        user_message = request.form.get(
            "message",
            ""
        ).strip()

        try:
            quantity = int(
                request.form.get("quantity", "1")
            )

        except (TypeError, ValueError):
            quantity = 1

        quantity = max(
            1,
            min(quantity, 10)
        )

        if not name or not email:
            flash(
                "Please enter your name and email address.",
                "error"
            )

            return render_template(
                "purchase_request.html",
                product=product
            )

        if not SENDGRID_API_KEY:
            print(
                "Purchase Request Error: "
                "SENDGRID_API_KEY is missing.",
                flush=True
            )

            flash(
                "The email service is not configured. "
                "Please try again later.",
                "error"
            )

            return render_template(
                "purchase_request.html",
                product=product
            )

        safe_name = escape(name)
        safe_email = escape(email)

        safe_phone = escape(
            phone or "Not provided"
        )

        safe_fulfillment = escape(
            fulfillment or "Not provided"
        )

        safe_user_message = escape(
            user_message
            or "No additional message provided."
        ).replace(
            "\n",
            "<br>"
        )

        safe_product_name = escape(
            product.name
        )

        safe_product_sku = escape(
            product.sku
        )

        product_price = float(
            product.price
        )

        message = Mail(
            from_email="contact@madebynhile.com",
            to_emails="lethaonhi007@gmail.com",
            subject=(
                f"Purchase Request: "
                f"{product.name} - SKU {product.sku}"
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

        try:
            sendgrid = SendGridAPIClient(
                SENDGRID_API_KEY
            )

            response = sendgrid.send(message)

            print(
                f"Purchase request email status: "
                f"{response.status_code}",
                flush=True
            )

        except Exception as error:
            print(
                f"Purchase request SendGrid error: "
                f"{repr(error)}",
                flush=True
            )

            if hasattr(error, "body"):
                print(
                    f"SendGrid response: {error.body}",
                    flush=True
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

        return redirect(
            url_for(
                "purchase_success",
                slug=product.slug
            )
        )

    return render_template(
        "purchase_request.html",
        product=product
    )


@app.route("/purchase-success/<slug>")
def purchase_success(slug):
    product = Product.query.filter_by(
        slug=slug
    ).first_or_404()

    return render_template(
        "purchase_success.html",
        product=product
    )


# =========================================================
# RUN LOCALLY
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)