from django.urls import path

from .views import (
    CloseWeekView,
    ContributionCreateView,
    GroupDetailView,
    GroupListCreateView,
    GroupReportView,
    MemberListCreateView,
)


urlpatterns = [
    path(
        "groups/",
        GroupListCreateView.as_view(),
        name="group-list-create",
    ),
    path(
        "groups/<int:group_id>/",
        GroupDetailView.as_view(),
        name="group-detail",
    ),
    path(
        "groups/<int:group_id>/members/",
        MemberListCreateView.as_view(),
        name="member-list-create",
    ),
    path(
        "groups/<int:group_id>/contributions/",
        ContributionCreateView.as_view(),
        name="contribution-create",
    ),
    path(
        "groups/<int:group_id>/close-week/",
        CloseWeekView.as_view(),
        name="close-week",
    ),
    path(
        "groups/<int:group_id>/report/",
        GroupReportView.as_view(),
        name="group-report",
    ),
]