# Susu Management System

A Django REST Framework application for managing a rotating savings group (Susu).

The application allows group administrators to create a savings group, register members, record weekly contributions, close weeks, issue payouts, and view contribution and payout reports.

## Features

* Create a savings group with a fixed weekly contribution in GHS.
* Register members with unique IDs.
* Automatically assign joining order.
* Record full and partial contributions.
* Track outstanding balances.
* Reject unknown members, duplicate member IDs, invalid payments, and overpayments.
* Prevent a week from closing when contributions are outstanding.
* Pay the entire weekly pot to the next eligible member.
* Maintain contribution and payout history.
* Generate reports showing the current week, member payment status, outstanding balances, and payout history.
* Use decimal arithmetic for financial calculations.

## Technology Stack

* Python
* Django
* Django REST Framework
* SQLite for local development
* Django TestCase for automated testing

## Requirements

* Python 3.13 or another compatible Python version.
* pip
* Git

## Installation

Clone the repository:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_PROJECT_DIRECTORY>
```

Create and activate a virtual environment.

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Apply the database migrations:

```bash
python manage.py migrate
```

Run the application:

```bash
python manage.py runserver
```

The API will be available at:

`http://127.0.0.1:8000/api/`

## API Endpoints

| Method | Endpoint                          | Description               |
| ------ | --------------------------------- | ------------------------- |
| GET    | `/api/groups/`                    | List groups               |
| POST   | `/api/groups/`                    | Create a group            |
| GET    | `/api/groups/<id>/`               | Retrieve a group          |
| GET    | `/api/groups/<id>/members/`       | List members              |
| POST   | `/api/groups/<id>/members/`       | Add a member              |
| POST   | `/api/groups/<id>/contributions/` | Record a contribution     |
| POST   | `/api/groups/<id>/close-week/`    | Close the current week    |
| GET    | `/api/groups/<id>/report/`        | Retrieve the group report |

Replace `<id>` with the ID of the relevant group.

## Example Workflow

### 1. Create a group

Send a POST request to `/api/groups/`:

```json
{
    "name": "Chinsali Susu",
    "weekly_contribution": "50.00"
}
```

### 2. Add members

Send a POST request to `/api/groups/1/members/`:

```json
{
    "member_id": "AMA001",
    "name": "Ama"
}
```

Register other members in the same way.

### 3. Record a contribution

Send a POST request to `/api/groups/1/contributions/`:

```json
{
    "member_id": "AMA001",
    "amount": "50.00"
}
```

Partial payments are allowed as long as the payment does not exceed the member's outstanding balance.

### 4. Close the week

Send a POST request to `/api/groups/1/close-week/`.

The week closes only when every member has paid the full weekly contribution. Otherwise, the API reports the members and amounts outstanding.

### 5. View the report

Send a GET request to `/api/groups/1/report/`.

The report includes the current week, member payment statuses, outstanding balances, and payout history.

## Running the Tests

Run the entire test suite:

```bash
python manage.py test
```

Or run only the Susu application tests:

```bash
python manage.py test susu
```

The tests cover group creation, membership, partial payments, payment validation, week closure, payout order, and reporting.

## Business Rules

* Each member contributes the same fixed amount every week.
* Members receive payouts in their joining order.
* Each member receives one payout per group rotation.
* Partial payments are permitted.
* Payments must be positive and cannot exceed the outstanding balance.
* A week cannot close until all members have paid in full.
* Membership is locked after the first week closes.
* The group completes its rotation after every member receives a payout.

See `NOTES.md` for assumptions and limitations.
