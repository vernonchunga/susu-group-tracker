from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import Contribution, Member, Payout, SusuGroup


class SusuError(Exception):
    """Base exception for Susu business-rule violations."""


class DuplicateMemberError(SusuError):
    """Raised when a member ID already exists in the group."""


class UnknownMemberError(SusuError):
    """Raised when a member cannot be found in the group."""


class InvalidAmountError(SusuError):
    """Raised when a contribution amount is invalid."""


class OverpaymentError(SusuError):
    """Raised when a contribution exceeds the outstanding balance."""


class WeekNotFullyPaidError(SusuError):
    """Raised when a week cannot close because members still owe money."""

    def __init__(self, outstanding):
        self.outstanding = outstanding
        super().__init__(
            "The week cannot close because contributions are outstanding."
        )


class WeekAlreadyClosedError(SusuError):
    """Raised when an operation targets a week that is already closed."""


class GroupCompletedError(SusuError):
    """Raised when all members have received their payouts."""


class InvalidOperationError(SusuError):
    """Raised when an operation violates the group's rules."""


def create_group(name, weekly_contribution):
    """
    Create a Susu group with a fixed weekly contribution.
    """
    amount = _validate_positive_amount(weekly_contribution)

    return SusuGroup.objects.create(
        name=name,
        weekly_contribution=amount,
    )


def _validate_positive_amount(amount):
    """
    Convert a valid monetary value to Decimal and reject
    zero, negative, or invalid amounts.
    """
    if isinstance(amount, bool):
        raise InvalidAmountError("Amount must be a positive monetary value.")

    try:
        value = Decimal(str(amount))
    except Exception as exc:
        raise InvalidAmountError("Invalid monetary amount.") from exc

    if not value.is_finite() or value <= Decimal("0.00"):
        raise InvalidAmountError("Amount must be greater than zero.")

    if value.as_tuple().exponent < -2:
        raise InvalidAmountError(
            "Amount cannot contain more than two decimal places."
        )

    return value


def _get_group(group_id):
    """
    Retrieve a group or raise a clear business exception.
    """
    try:
        return SusuGroup.objects.get(pk=group_id)
    except SusuGroup.DoesNotExist as exc:
        raise InvalidOperationError("Susu group does not exist.") from exc


def _get_members(group):
    return list(
        Member.objects.filter(group=group).order_by("join_order")
    )


def _get_pot_amount(group):
    return group.weekly_contribution * _get_members(group).__len__()


def _get_paid_amount(group, member, week):
    """
    Return the total contributions recorded for a member in a week.
    """
    result = Contribution.objects.filter(
        group=group,
        member=member,
        week=week,
    ).aggregate(total=Sum("amount"))

    return result["total"] or Decimal("0.00")


def _get_outstanding_balances(group, week):
    """
    Return the outstanding amount for every member who owes money.
    """
    outstanding = {}

    for member in _get_members(group):
        paid = _get_paid_amount(group, member, week)
        balance = group.weekly_contribution - paid

        if balance > Decimal("0.00"):
            outstanding[member.member_id] = {
                "member_id": member.member_id,
                "name": member.name,
                "paid": paid,
                "owes": balance,
            }

    return outstanding


def _get_next_recipient(group):
    """
    Find the next member in joining order who has not received a payout.
    """
    members = _get_members(group)

    paid_out_member_ids = Payout.objects.filter(
        group=group
    ).values_list("member_id", flat=True)

    for member in members:
        if member.id not in paid_out_member_ids:
            return member

    return None

def _is_group_completed(group):
    """
    A group is complete when every registered member
    has received exactly one payout.
    """
    member_count = Member.objects.filter(group=group).count()

    if member_count == 0:
        return False

    payout_count = Payout.objects.filter(group=group).count()

    return payout_count == member_count


@transaction.atomic
def add_member(group_id, member_id, name):
    """
    Register a member before Week 1 begins.

    Joining order is assigned automatically.
    """
    group = SusuGroup.objects.select_for_update().get(pk=group_id)

    if group.current_week != 1:
        raise InvalidOperationError(
            "Members cannot be added after Week 1 has started."
        )

    if Payout.objects.filter(group=group).exists():
        raise InvalidOperationError(
            "Members cannot be added after a payout has occurred."
        )

    if not member_id or not member_id.strip():
        raise InvalidOperationError("Member ID is required.")

    if not name or not name.strip():
        raise InvalidOperationError("Member name is required.")

    if Member.objects.filter(
        group=group,
        member_id=member_id.strip(),
    ).exists():
        raise DuplicateMemberError(
            f"Member ID '{member_id}' already exists."
        )

    last_member = (
        Member.objects.filter(group=group)
        .order_by("-join_order")
        .first()
    )

    next_order = last_member.join_order + 1 if last_member else 1

    return Member.objects.create(
        group=group,
        member_id=member_id.strip(),
        name=name.strip(),
        join_order=next_order,
    )


@transaction.atomic
def record_contribution(group_id, member_id, amount):
    """
    Record a full or partial contribution for the current week.
    """
    group = SusuGroup.objects.select_for_update().get(pk=group_id)

    if _is_group_completed(group):
        raise GroupCompletedError(
            "This Susu group has completed its rotation."
        )

    value = _validate_positive_amount(amount)

    if not Member.objects.filter(
        group=group,
        member_id=member_id,
    ).exists():
        raise UnknownMemberError(
            f"Member '{member_id}' does not belong to this group."
        )

    member = Member.objects.get(
        group=group,
        member_id=member_id,
    )

    if Payout.objects.filter(
        group=group,
        week=group.current_week,
    ).exists():
        raise WeekAlreadyClosedError(
            "The current week has already been closed."
        )

    paid = _get_paid_amount(
        group,
        member,
        group.current_week,
    )

    outstanding = group.weekly_contribution - paid

    if value > outstanding:
        raise OverpaymentError(
            f"{member.name} owes GHS {outstanding:.2f}; "
            f"payment of GHS {value:.2f} is too high."
        )

    return Contribution.objects.create(
        group=group,
        member=member,
        week=group.current_week,
        amount=value,
    )


@transaction.atomic
def close_week(group_id):
    """
    Close the current week if all members have paid in full.

    If successful, record the payout and advance the group
    to the next week. If anyone owes money, no payout occurs.
    """
    group = SusuGroup.objects.select_for_update().get(pk=group_id)

    members = _get_members(group)

    if not members:
        raise InvalidOperationError(
            "A group must have at least one member before closing a week."
        )

    if Payout.objects.filter(
        group=group,
        week=group.current_week,
    ).exists():
        raise WeekAlreadyClosedError(
            "This week has already been closed."
        )

    outstanding = _get_outstanding_balances(
        group,
        group.current_week,
    )

    if outstanding:
        raise WeekNotFullyPaidError(outstanding)

    recipient = _get_next_recipient(group)

    if recipient is None:
        raise GroupCompletedError(
            "Every member has already received a payout."
        )

    payout_amount = _get_pot_amount(group)

    payout = Payout.objects.create(
        group=group,
        member=recipient,
        week=group.current_week,
        amount=payout_amount,
    )

    group.current_week += 1
    group.save(update_fields=["current_week"])

    return payout


def get_group_report(group_id):
    """
    Return the current week's payment status and payout history.
    """
    group = _get_group(group_id)

    members = _get_members(group)
    week = group.current_week

    member_statuses = []

    for member in members:
        paid = _get_paid_amount(group, member, week)
        owed = max(
            group.weekly_contribution - paid,
            Decimal("0.00"),
        )

        member_statuses.append({
            "member_id": member.member_id,
            "name": member.name,
            "join_order": member.join_order,
            "paid": paid,
            "owed": owed,
            "paid_in_full": owed == Decimal("0.00"),
        })

    payout_history = list(
        Payout.objects.filter(group=group)
        .select_related("member")
        .order_by("week")
        .values(
            "week",
            "member__member_id",
            "member__name",
            "amount",
            "paid_at",
        )
    )

    return {
        "group": group.name,
        "weekly_contribution": group.weekly_contribution,
        "current_week": week,
        "members": member_statuses,
        "payout_history": payout_history,
        "completed": _is_group_completed(group),
    }