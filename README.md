# RentMatch – Smart Rental Finder (Corrected)

This is the corrected single-file version of the RentMatch Flask + SQLite project.

## Run it in VS Code on Windows

1. Install Python 3.10 or newer.
2. Extract the ZIP and open the extracted folder in VS Code.
3. Open **Terminal → New Terminal**.
4. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

6. Run the app:

   ```powershell
   python rentmatch_all_in_one.py
   ```

7. Open **http://127.0.0.1:5000** in your browser.

The SQLite database is created automatically in the same folder. To recreate the original demo data, stop the server and delete `rentmatch_allinone.db`, then run the app again.

## Demo accounts

Password for all demo accounts: `password123`

- Admin: `admin@rentmatch.com`
- Owner: `suresh.gowda@gmail.com`
- Tenant: `rohan.student@gmail.com`

## Corrections made

- Public registration cannot create administrator accounts.
- Invalid numeric search/recommendation values are handled without crashing.
- Owner listing creation validates required and numeric fields.
- Only tenant accounts can send enquiries or use favourites.
- Favourite API validates JSON, property IDs, account role and listing availability.
- Enquiry submissions validate message/phone and property availability.
- Disabled accounts are signed out when the current user is loaded.
- Administrators cannot disable their own account.
- Secret key can be configured with `RENTMATCH_SECRET_KEY`.

## Important limitations

This is for a local academic project demonstration, not production deployment. The listings and contact details are illustrative demo data and are not verified real offers. Before deploying publicly, add CSRF protection, rate limiting, robust URL validation, audit logging and production secret management. A syntax check passed, but the application could not be launched in this environment because Flask is not installed and network access to install packages was unavailable. Run it locally after installing `requirements.txt` and report any traceback for further debugging.
