from django.contrib import admin

from .models import Contribution, Member, Payout, SusuGroup


@admin.register(SusuGroup)
class SusuGroupAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "weekly_contribution",
        "current_week",
        "created_at",
    )


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "member_id",
        "name",
        "group",
        "join_order",
        "joined_at",
    )

    list_filter = ("group",)


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        "group",
        "member",
        "week",
        "amount",
        "recorded_at",
    )

    list_filter = ("group", "week")


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = (
        "group",
        "member",
        "week",
        "amount",
        "paid_at",
    )

    list_filter = ("group", "week")