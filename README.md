# Paper & Pages — Bookshop Automation System

A Flask + SQLite bookshop application with a customer storefront and an admin inventory/order dashboard.

## Features
- Customer registration and login (hashed passwords)
- Search by title, author, ISBN and category
- Persistent book catalogue and inventory
- Shopping cart and checkout
- Stock deduction when an order is placed
- Customer order history
- Admin dashboard with sales totals and low-stock alerts
- Admin book management and order/payment status updates

## Run locally
1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Run `pip install -r requirements.txt`.
4. Run `flask --app app seed` to create sample books and the admin account.
5. Run `python app.py`.
6. Open http://127.0.0.1:5000

Demo admin login: `admin@bookshop.local` / `Admin123!`

Change the demo password and set a strong `SECRET_KEY` before any deployment. SQLite is suitable for a local academic demonstration; for multi-user production deployment, configure PostgreSQL using `DATABASE_URL`. Add CSRF protection, HTTPS, backups, payment gateway integration and rate limiting before public production use.

## Database
Tables: `user`, `book`, `order`, `order_item`. SQLAlchemy creates the schema automatically. `flask --app app seed` inserts demo catalogue records and the initial admin account.


## Deploy online (Render + PostgreSQL)
1. Push this project folder to a GitHub repository.
2. Create a persistent PostgreSQL database with a provider such as Neon or Render.
3. In Render, choose **New + → Web Service**, connect the GitHub repository and deploy.
4. Render detects `render.yaml`; set `DATABASE_URL` to the PostgreSQL connection string from your database provider. Render generates `SECRET_KEY` from the blueprint.
5. After the first deploy, open the Render Shell and run `flask --app app seed` once to create the sample catalogue and demo admin.
6. Open the public `onrender.com` URL shown by Render.

Use a persistent PostgreSQL database for hosted deployment. Do not rely on the local SQLite file for a hosted service because many hosting platforms use ephemeral application filesystems. Change the demo admin password immediately after first login. Configure backups, HTTPS, CSRF protection, rate limiting and production logging before real customer use.
