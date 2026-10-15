from decimal import Decimal
from rest_framework import serializers

from .models import Member, SusuGroup


class SusuGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = SusuGroup
        fields = [
            "id",
            "name",
            "weekly_contribution",
            "current_week",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "current_week",
            "created_at",
        ]

    def validate_weekly_contribution(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Weekly contribution must be greater than zero."
            )

        return value


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            "id",
            "member_id",
            "name",
            "join_order",
            "joined_at",
        ]
        read_only_fields = [
            "id",
            "join_order",
            "joined_at",
        ]

    def validate_member_id(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Member ID is required."
            )

        return value

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Member name is required."
            )

        return value


class ContributionInputSerializer(serializers.Serializer):
    member_id = serializers.CharField(max_length=50)

    amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    def validate_member_id(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Member ID is required."
            )

        return value