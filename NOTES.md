# Susu Management System — Notes

## 1. Assumptions and Decisions

### Fixed Contribution

Each group has one fixed weekly contribution amount denominated in Ghanaian cedis (GHS). Members must contribute this amount each week.

The contribution amount is stored using decimal arithmetic to avoid floating-point rounding errors.

### Member Identification

Every member has a unique member ID within a group. Two members may have the same name if their IDs differ.

### Joining Order

Members receive payouts in the order they join. The system assigns each new member a joining position automatically.

### Membership Changes

Members can only be added before Week 1 closes. This prevents the weekly contribution requirements and payout order from changing during an active rotation.

### Partial Payments

Members may pay in multiple installments. The system calculates the outstanding balance by subtracting the total amount already paid from the weekly contribution.

### Overpayments

Payments greater than a member's outstanding balance are rejected. Zero and negative payments are also rejected.

### Closing a Week

A week closes only when every registered member has paid the full contribution.

If any member owes money, the system reports the outstanding balances and does not issue a payout.

### Payout Order

The entire weekly pot is paid to the next member in joining order who has not previously received a payout.

Each member can receive one payout during a group rotation.

### Completion

The rotation is complete after every registered member has received one payout. Additional contributions and payouts should not be permitted.

### Historical Records

Contribution and payout records are retained to preserve the group's financial history.

### Database

SQLite is used for local development. A production deployment handling concurrent financial operations should use a database such as PostgreSQL and appropriate transaction locking.

## 2. Validation

The application validates the following:

* Duplicate member IDs.
* Unknown members.
* Zero and negative payments.
* Payments exceeding the outstanding balance.
* Contributions containing more than two decimal places.
* Attempts to close a week with unpaid contributions.
* Attempts to add members after Week 1 closes.
* Attempts to close an empty group.
* Attempts to issue duplicate payouts.

## 3. Testing

Automated tests use Django's built-in testing framework.

The test suite covers group creation, member registration, partial payments, invalid contributions, outstanding balances, payout order, week progression, and report generation.

Run the tests with:

```bash
python manage.py test susu
```

## 4. Limitations

* The application currently exposes a REST API rather than a graphical user interface.
* Authentication and role-based permissions are not yet implemented.
* The initial implementation is designed for a simple rotating savings group.
* Production concurrency and financial reconciliation require further testing.
* Administrative corrections and reversals are not implemented.
* Notifications and payment gateway integrations are not included.

## 5. Future Improvements

With more development time, I would:

1. Add authentication and role-based access control.
2. Use PostgreSQL for production.
3. Improve concurrency handling and transaction tests.
4. Add audit logs for financial operations.
5. Implement controlled payment reversals.
6. Add notifications for outstanding contributions.
7. Support exporting reports to CSV or PDF.
8. Add API documentation using OpenAPI and Swagger.
9. Introduce stronger financial reconciliation and payout verification.
10. Add integration tests for the complete API workflow.
