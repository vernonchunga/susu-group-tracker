from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class SusuGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)

    weekly_contribution = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    current_week = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Member(models.Model):
    group = models.ForeignKey(
        SusuGroup,
        on_delete=models.PROTECT,
        related_name="members",
    )

    member_id = models.CharField(max_length=50)

    name = models.CharField(max_length=100)

    join_order = models.PositiveIntegerField()

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["join_order"]

        constraints = [
            models.UniqueConstraint(
                fields=["group", "member_id"],
                name="unique_member_id_per_group",
            ),
            models.UniqueConstraint(
                fields=["group", "join_order"],
                name="unique_join_order_per_group",
            ),
            models.CheckConstraint(
                condition=models.Q(join_order__gte=1),
                name="member_join_order_positive",
            ),
        ]

    def __str__(self):
        return f"{self.member_id} - {self.name}"


class Contribution(models.Model):
    group = models.ForeignKey(
        SusuGroup,
        on_delete=models.PROTECT,
        related_name="contributions",
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="contributions",
    )

    week = models.PositiveIntegerField()

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recorded_at", "id"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(week__gte=1),
                name="contribution_week_positive",
            ),
        ]

    def __str__(self):
        return (
            f"{self.member.name} - "
            f"Week {self.week} - GHS {self.amount}"
        )


class Payout(models.Model):
    group = models.ForeignKey(
        SusuGroup,
        on_delete=models.PROTECT,
        related_name="payouts",
    )

    member = models.ForeignKey(
        Member,
        on_delete=models.PROTECT,
        related_name="payouts",
    )

    week = models.PositiveIntegerField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    paid_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["week"]

        constraints = [
            models.UniqueConstraint(
                fields=["group", "week"],
                name="one_payout_per_group_week",
            ),
            models.UniqueConstraint(
                fields=["group", "member"],
                name="one_payout_per_member_per_group",
            ),
        ]

    def __str__(self):
        return (
            f"Week {self.week}: "
            f"{self.member.name} received GHS {self.amount}"
        )