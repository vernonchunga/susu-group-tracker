from django.db import IntegrityError
from django.http import Http404

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Member, SusuGroup
from .serializers import (
    ContributionInputSerializer,
    MemberSerializer,
    SusuGroupSerializer,
)
from .services import (
    DuplicateMemberError,
    GroupCompletedError,
    InvalidAmountError,
    InvalidOperationError,
    OverpaymentError,
    UnknownMemberError,
    WeekAlreadyClosedError,
    WeekNotFullyPaidError,
    add_member,
    close_week,
    create_group,
    get_group_report,
    record_contribution,
)


def handle_service_error(exc):
    """
    Convert known business exceptions into appropriate HTTP responses.
    """
    if isinstance(exc, WeekNotFullyPaidError):
        return Response(
            {
                "error": str(exc),
                "outstanding": exc.outstanding,
            },
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, DuplicateMemberError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, OverpaymentError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, InvalidAmountError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, UnknownMemberError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_404_NOT_FOUND,
        )

    if isinstance(exc, WeekAlreadyClosedError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, GroupCompletedError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )

    if isinstance(exc, InvalidOperationError):
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response(
        {"error": "The operation could not be completed."},
        status=status.HTTP_400_BAD_REQUEST,
    )


class GroupListCreateView(APIView):
    """
    Create a group or list existing groups.
    """

    def get(self, request):
        groups = SusuGroup.objects.all()
        serializer = SusuGroupSerializer(groups, many=True)

        return Response(serializer.data)

    def post(self, request):
        serializer = SusuGroupSerializer(data=request.data)

        if not serializer.is_valid():
            errors = serializer.errors

            if "name" in errors:
                return Response(
                    {"error": errors["name"][0]},
                    status=status.HTTP_409_CONFLICT,
                )

            return Response(
                errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            group = create_group(
                name=serializer.validated_data["name"],
                weekly_contribution=serializer.validated_data[
                    "weekly_contribution"
                ],
            )
        except IntegrityError:
            return Response(
                {"error": "A group with this name already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        except (InvalidAmountError, InvalidOperationError) as exc:
            return handle_service_error(exc)

        return Response(
            SusuGroupSerializer(group).data,
            status=status.HTTP_201_CREATED,
        )


class GroupDetailView(APIView):
    """
    Retrieve one group.
    """

    def get(self, request, group_id):
        try:
            group = SusuGroup.objects.get(pk=group_id)
        except SusuGroup.DoesNotExist:
            raise Http404("Susu group not found.")

        return Response(SusuGroupSerializer(group).data)


class MemberListCreateView(APIView):
    """
    List members or register a new member.
    """

    def get(self, request, group_id):
        try:
            group = SusuGroup.objects.get(pk=group_id)
        except SusuGroup.DoesNotExist:
            raise Http404("Susu group not found.")

        members = Member.objects.filter(group=group).order_by(
            "join_order"
        )

        return Response(
            MemberSerializer(members, many=True).data
        )

    def post(self, request, group_id):
        serializer = MemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            member = add_member(
                group_id=group_id,
                member_id=serializer.validated_data["member_id"],
                name=serializer.validated_data["name"],
            )
        except (
            DuplicateMemberError,
            InvalidOperationError,
        ) as exc:
            return handle_service_error(exc)
        except SusuGroup.DoesNotExist:
            raise Http404("Susu group not found.")

        return Response(
            MemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )


class ContributionCreateView(APIView):
    """
    Record a contribution for the current week.
    """

    def post(self, request, group_id):
        serializer = ContributionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            contribution = record_contribution(
                group_id=group_id,
                member_id=serializer.validated_data["member_id"],
                amount=serializer.validated_data["amount"],
            )
        except (
            InvalidAmountError,
            OverpaymentError,
            UnknownMemberError,
            InvalidOperationError,
            WeekAlreadyClosedError,
            GroupCompletedError,
        ) as exc:
            return handle_service_error(exc)
        except SusuGroup.DoesNotExist:
            raise Http404("Susu group not found.")

        return Response(
            {
                "message": "Contribution recorded successfully.",
                "group_id": contribution.group_id,
                "member_id": contribution.member.member_id,
                "week": contribution.week,
                "amount": str(contribution.amount),
            },
            status=status.HTTP_201_CREATED,
        )


class CloseWeekView(APIView):
    """
    Close the current week and issue the payout if all members
    have paid in full.
    """

    def post(self, request, group_id):
        try:
            payout = close_week(group_id)
        except (
            WeekNotFullyPaidError,
            WeekAlreadyClosedError,
            GroupCompletedError,
            InvalidOperationError,
        ) as exc:
            return handle_service_error(exc)
        except SusuGroup.DoesNotExist:
            raise Http404("Susu group not found.")

        return Response(
            {
                "message": "Week closed successfully.",
                "week": payout.week,
                "recipient": payout.member.name,
                "member_id": payout.member.member_id,
                "amount": str(payout.amount),
            },
            status=status.HTTP_200_OK,
        )


class GroupReportView(APIView):
    """
    Return the current week's payment statuses and payout history.
    """

    def get(self, request, group_id):
        try:
            report = get_group_report(group_id)
        except InvalidOperationError:
            raise Http404("Susu group not found.")

        return Response(report)