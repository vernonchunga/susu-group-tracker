from decimal import Decimal

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Contribution, Member, Payout, SusuGroup
from .services import (
    DuplicateMemberError,
    InvalidAmountError,
    OverpaymentError,
    UnknownMemberError,
    WeekNotFullyPaidError,
    add_member,
    close_week,
    create_group,
    get_group_report,
    record_contribution,
)


class SusuServiceTests(TestCase):

    def setUp(self):
        """
        Create a fresh Susu group and three members
        before every test.
        """
        self.group = create_group(
            name="Test Susu",
            weekly_contribution=Decimal("50.00"),
        )

        self.ama = add_member(
            self.group.id,
            "AMA001",
            "Ama",
        )

        self.kofi = add_member(
            self.group.id,
            "KOFI001",
            "Kofi",
        )

        self.esi = add_member(
            self.group.id,
            "ESI001",
            "Esi",
        )

    def test_create_group_with_fixed_contribution(self):
        """
        A group should store its weekly contribution accurately.
        """
        self.assertEqual(
            self.group.weekly_contribution,
            Decimal("50.00"),
        )

    def test_members_follow_joining_order(self):
        """
        Members should be assigned joining positions in order.
        """
        self.assertEqual(self.ama.join_order, 1)
        self.assertEqual(self.kofi.join_order, 2)
        self.assertEqual(self.esi.join_order, 3)

    def test_partial_payment_is_recorded(self):
        """
        A member should be able to pay part of their contribution.
        """
        payment = record_contribution(
            self.group.id,
            "ESI001",
            Decimal("30.00"),
        )

        self.assertEqual(payment.amount, Decimal("30.00"))

        report = get_group_report(self.group.id)

        esi_status = next(
            member
            for member in report["members"]
            if member["member_id"] == "ESI001"
        )

        self.assertEqual(esi_status["paid"], Decimal("30.00"))
        self.assertEqual(esi_status["owed"], Decimal("20.00"))
        self.assertFalse(esi_status["paid_in_full"])

    def test_duplicate_member_is_rejected(self):
        """
        A member ID must not be registered twice.
        """
        with self.assertRaises(DuplicateMemberError):
            add_member(
                self.group.id,
                "AMA001",
                "Another Ama",
            )

    def test_unknown_member_is_rejected(self):
        """
        Contributions from unknown members must be rejected.
        """
        with self.assertRaises(UnknownMemberError):
            record_contribution(
                self.group.id,
                "UNKNOWN",
                Decimal("50.00"),
            )

    def test_zero_and_negative_payments_are_rejected(self):
        """
        Contributions must be greater than zero.
        """
        for amount in [
            Decimal("0.00"),
            Decimal("-10.00"),
        ]:
            with self.subTest(amount=amount):
                with self.assertRaises(InvalidAmountError):
                    record_contribution(
                        self.group.id,
                        "AMA001",
                        amount,
                    )

    def test_overpayment_is_rejected(self):
        """
        A member cannot contribute more than they owe.
        """
        with self.assertRaises(OverpaymentError):
            record_contribution(
                self.group.id,
                "AMA001",
                Decimal("60.00"),
            )

    def test_week_cannot_close_if_member_owes_money(self):
        """
        Closing a week with outstanding contributions
        must not create a payout or advance the week.
        """
        record_contribution(
            self.group.id,
            "AMA001",
            Decimal("50.00"),
        )

        record_contribution(
            self.group.id,
            "KOFI001",
            Decimal("50.00"),
        )

        record_contribution(
            self.group.id,
            "ESI001",
            Decimal("30.00"),
        )

        with self.assertRaises(WeekNotFullyPaidError) as context:
            close_week(self.group.id)

        outstanding = context.exception.outstanding

        self.assertEqual(
            outstanding["ESI001"]["owes"],
            Decimal("20.00"),
        )

        self.assertEqual(Payout.objects.count(), 0)

        self.group.refresh_from_db()

        self.assertEqual(self.group.current_week, 1)

    def test_fully_paid_week_pays_first_member(self):
        """
        When everyone pays in full, the first member
        should receive the entire pot.
        """
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        payout = close_week(self.group.id)

        self.assertEqual(payout.member, self.ama)
        self.assertEqual(payout.amount, Decimal("150.00"))
        self.assertEqual(payout.week, 1)

        self.group.refresh_from_db()

        self.assertEqual(self.group.current_week, 2)

    def test_partial_payment_can_be_completed_before_closing(self):
        """
        A partial payment followed by the outstanding balance
        should allow the week to close.
        """
        record_contribution(
            self.group.id,
            "AMA001",
            Decimal("50.00"),
        )

        record_contribution(
            self.group.id,
            "KOFI001",
            Decimal("50.00"),
        )

        record_contribution(
            self.group.id,
            "ESI001",
            Decimal("30.00"),
        )

        record_contribution(
            self.group.id,
            "ESI001",
            Decimal("20.00"),
        )

        payout = close_week(self.group.id)

        self.assertEqual(payout.member, self.ama)
        self.assertEqual(payout.amount, Decimal("150.00"))

        self.assertEqual(
            Contribution.objects.filter(
                group=self.group,
                member=self.esi,
                week=1,
            ).count(),
            2,
        )

    def test_next_week_pays_next_member(self):
        """
        The second member should receive the second week's pot.
        """
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        payout = close_week(self.group.id)

        self.assertEqual(payout.member, self.kofi)
        self.assertEqual(payout.week, 2)
        self.assertEqual(payout.amount, Decimal("150.00"))

    def test_report_contains_payout_history(self):
        """
        The report should include successful payouts.
        """
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        report = get_group_report(self.group.id)

        self.assertEqual(report["current_week"], 2)
        self.assertEqual(len(report["payout_history"]), 1)
        self.assertEqual(
            report["payout_history"][0]["member__name"],
            "Ama",
        )

    def test_cannot_add_member_after_week_one_closes(self):
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        from .services import InvalidOperationError

        with self.assertRaises(InvalidOperationError):
            add_member(
                self.group.id,
                "NEW001",
                "New Member",
            )

    def test_week_cannot_close_twice(self):
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        # A second close attempt without contributions
        # for Week 2 must fail.
        from .services import WeekNotFullyPaidError

        with self.assertRaises(WeekNotFullyPaidError):
            close_week(self.group.id)

        self.assertEqual(
            Payout.objects.filter(group=self.group).count(),
            1,
        )

    def test_amount_with_more_than_two_decimal_places_is_rejected(self):
        with self.assertRaises(InvalidAmountError):
            record_contribution(
                self.group.id,
                "AMA001",
                Decimal("10.005"),
            )

    def test_empty_group_cannot_close(self):
        empty_group = create_group(
            name="Empty Susu",
            weekly_contribution=Decimal("50.00"),
        )

        from .services import InvalidOperationError

        with self.assertRaises(InvalidOperationError):
            close_week(empty_group.id)

    def test_report_identifies_completed_group(self):
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        report = get_group_report(self.group.id)

        self.assertTrue(report["completed"])

    def test_completed_group_rejects_contributions(self):
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            record_contribution(
                self.group.id,
                member_id,
                Decimal("50.00"),
            )

        close_week(self.group.id)

        from .services import GroupCompletedError

        with self.assertRaises(GroupCompletedError):
            record_contribution(
                self.group.id,
                "AMA001",
                Decimal("10.00"),
            )

class SusuAPITests(APITestCase):
    """
    API-level tests for the Susu management system.
    """

    def setUp(self):
        self.group_data = {
            "name": "API Test Susu",
            "weekly_contribution": "50.00",
        }

        response = self.client.post(
            "/api/groups/",
            self.group_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.group_id = response.data["id"]

        self.ama = self.add_member("AMA001", "Ama")
        self.kofi = self.add_member("KOFI001", "Kofi")
        self.esi = self.add_member("ESI001", "Esi")

    def add_member(self, member_id, name):
        response = self.client.post(
            f"/api/groups/{self.group_id}/members/",
            {
                "member_id": member_id,
                "name": name,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        return response.data

    def pay(self, member_id, amount):
        return self.client.post(
            f"/api/groups/{self.group_id}/contributions/",
            {
                "member_id": member_id,
                "amount": amount,
            },
            format="json",
        )

    def test_create_group_returns_created(self):
        response = self.client.post(
            "/api/groups/",
            {
                "name": "Another Susu",
                "weekly_contribution": "75.00",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            response.data["weekly_contribution"],
            "75.00",
        )

    def test_duplicate_group_name_is_rejected(self):
        response = self.client.post(
            "/api/groups/",
            self.group_data,
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

    def test_list_members_returns_joining_order(self):
        response = self.client.get(
            f"/api/groups/{self.group_id}/members/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            [member["member_id"] for member in response.data],
            ["AMA001", "KOFI001", "ESI001"],
        )

    def test_unknown_member_contribution_returns_404(self):
        response = self.pay("UNKNOWN", "50.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_overpayment_returns_400(self):
        response = self.pay("AMA001", "60.00")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_week_cannot_close_with_outstanding_contribution(self):
        self.pay("AMA001", "50.00")
        self.pay("KOFI001", "50.00")
        self.pay("ESI001", "30.00")

        response = self.client.post(
            f"/api/groups/{self.group_id}/close-week/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_409_CONFLICT,
        )

        self.assertEqual(
            response.data["outstanding"]["ESI001"]["owes"],
            Decimal("20.00"),
        )

        self.assertEqual(Payout.objects.count(), 0)

        self.assertEqual(
            SusuGroup.objects.get(pk=self.group_id).current_week,
            1,
        )

    def test_successful_week_closure_returns_correct_payout(self):
        for member_id in ["AMA001", "KOFI001", "ESI001"]:
            response = self.pay(member_id, "50.00")

            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
            )

        response = self.client.post(
            f"/api/groups/{self.group_id}/close-week/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["recipient"], "Ama")
        self.assertEqual(response.data["member_id"], "AMA001")
        self.assertEqual(response.data["week"], 1)
        self.assertEqual(response.data["amount"], "150.00")

        self.assertEqual(
            SusuGroup.objects.get(pk=self.group_id).current_week,
            2,
        )

    def test_report_contains_payment_status_and_payout_history(self):
        self.pay("AMA001", "50.00")
        self.pay("KOFI001", "50.00")
        self.pay("ESI001", "50.00")

        self.client.post(
            f"/api/groups/{self.group_id}/close-week/",
            {},
            format="json",
        )

        response = self.client.get(
            f"/api/groups/{self.group_id}/report/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["current_week"], 2)
        self.assertEqual(len(response.data["payout_history"]), 1)

        ama_status = next(
            member
            for member in response.data["members"]
            if member["member_id"] == "AMA001"
        )

        self.assertEqual(ama_status["owed"], Decimal("50.00"))
        self.assertFalse(ama_status["paid_in_full"])

    def test_unknown_group_returns_404(self):
        response = self.client.get("/api/groups/999999/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_partial_payment_workflow_through_api(self):
        self.pay("AMA001", "50.00")
        self.pay("KOFI001", "50.00")

        first_payment = self.pay("ESI001", "30.00")
        second_payment = self.pay("ESI001", "20.00")

        self.assertEqual(
            first_payment.status_code,
            status.HTTP_201_CREATED,
        )

        self.assertEqual(
            second_payment.status_code,
            status.HTTP_201_CREATED,
        )

        response = self.client.post(
            f"/api/groups/{self.group_id}/close-week/",
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(response.data["recipient"], "Ama")
        self.assertEqual(response.data["amount"], "150.00")

        esi = Member.objects.get(
            group_id=self.group_id,
            member_id="ESI001",
        )

        self.assertEqual(
            Contribution.objects.filter(
                group_id=self.group_id,
                member=esi,
                week=1,
            ).count(),
            2,
        )