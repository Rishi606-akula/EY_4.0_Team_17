# Register your models here.
# social/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import Profile, Activity, Connection, Report, Rating


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Admin configuration for Profile model."""
    list_display = (
        "username",
        "email",
        "city",
        "verified",
        "rating",
        "created_at",
    )
    list_filter = (
        "verified",
        "gender",
        "created_at",
    )
    search_fields = (
        "user__username",
        "user__email",
        "city",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    @admin.display(description="Username")
    def username(self, obj):
        return obj.user.username

    @admin.display(description="Email")
    def email(self, obj):
        return obj.user.email


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    """Admin configuration for Activity model."""
    list_display = (
        "title",
        "creator",
        "city",
        "date",
        "time",
        "is_active",
        "participant_count",
        "created_at",
    )
    list_filter = (
        "is_active",
        "city",
        "date",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "location",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    date_hierarchy = "date"

    @admin.display(description="Creator")
    def creator(self, obj):
        return obj.creator.username

    @admin.display(description="Participants")
    def participant_count(self, obj):
        return obj.participants.count()


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    """Admin configuration for Connection model."""
    list_display = (
        "sender",
        "receiver",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "created_at",
    )
    search_fields = (
        "sender__username",
        "receiver__username",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin configuration for Report model."""
    list_display = (
        "reporter",
        "reported_user",
        "reason_preview",
        "created_at",
    )
    list_filter = (
        "created_at",
    )
    search_fields = (
        "reporter__username",
        "reported_user__username",
        "reason",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)

    @admin.display(description="Reason")
    def reason_preview(self, obj):
        return obj.reason[:50] + "..." if len(obj.reason) > 50 else obj.reason


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    """Admin configuration for Rating model."""
    list_display = (
        "rater",
        "rated_user",
        "activity",
        "score",
        "created_at",
    )
    list_filter = (
        "score",
        "created_at",
    )
    search_fields = (
        "rater__username",
        "rated_user__username",
        "activity__title",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
admin.site.site_header = "FriendZone+ Administration"
admin.site.site_title = "FriendZone+ Admin"
admin.site.index_title = "Platform Management"