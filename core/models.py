# social/models.py

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import F, Q, Avg, Count
from django.core.exceptions import ValidationError
from datetime import datetime

User = get_user_model()


class Gender(models.TextChoices):
    MALE = "Male", "Male"
    FEMALE = "Female", "Female"
    PREFER_NOT_TO_SAY = "Prefer not to say", "Prefer not to say"


class ConnectionStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    ACCEPTED = "Accepted", "Accepted"
    REJECTED = "Rejected", "Rejected"


class Profile(models.Model):
    """Extended user profile for FriendZone+ with rating statistics."""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    bio = models.TextField(blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
        blank=True,
    )
    city = models.CharField(max_length=100)
    interests = models.TextField(blank=True)
    verified = models.BooleanField(default=False)
    rating = models.FloatField(default=0.0)
    average_rating = models.FloatField(default=0.0)
    total_ratings = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def update_rating_stats(self):
        """
        Calculate and update rating statistics from the Rating model.
        
        Uses Django ORM aggregation to efficiently compute:
        - average_rating: Average score of all ratings given to this user
        - total_ratings: Count of all ratings received
        
        Handles edge cases:
        - No division by zero (uses default 0.0 if no ratings exist)
        - Efficient database query with single aggregation
        """
        from .models import Rating
        
        # Aggregate ratings received by this user
        stats = Rating.objects.filter(
            rated_user=self.user
        ).aggregate(
            avg_score=Avg('score'),
            total_count=Count('id')
        )
        
        # Extract values with safe defaults to prevent division by zero
        avg_score = stats['avg_score']
        total_count = stats['total_count'] or 0
        
        # Update fields
        self.average_rating = round(avg_score, 2) if avg_score is not None else 0.0
        self.total_ratings = total_count
        
        # Save silently to avoid signal loops
        self.save(update_fields=['average_rating', 'total_ratings'])

    def __str__(self):
        return f"{self.user.username}'s profile"


class Activity(models.Model):
    """An event/activity created by a user."""
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    date = models.DateField()
    time = models.TimeField()
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_activities",
    )
    participants = models.ManyToManyField(
        User,
        related_name="joined_activities",
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def is_past(self):
        """
        Check if the activity date and time is in the past.
        Uses timezone-aware datetime for accurate comparison.
        
        Returns:
            bool: True if activity has passed, False otherwise
        """
        from datetime import datetime, time as dt_time
        
        # Combine date and time into a single datetime
        activity_datetime = datetime.combine(self.date, self.time)
        
        # Make timezone-aware using current timezone
        if timezone.is_naive(activity_datetime):
            activity_datetime = timezone.make_aware(activity_datetime)
        
        return activity_datetime < timezone.now()

    def participant_count(self):
        """
        Get the number of participants for this activity.
        
        Returns:
            int: Count of participants
        """
        return self.participants.count()

    def save(self, *args, **kwargs):
        """
        Override save to automatically deactivate past activities.
        Uses timezone-aware datetime logic.
        """
        # Check if activity is past and deactivate if necessary
        if self.is_past() and self.is_active:
            self.is_active = False
        
        super().save(*args, **kwargs)
from django.db.models import Q

class Connection(models.Model):
    """Friend request / connection between two users."""

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_connections",
    )

    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="received_connections",
    )

    status = models.CharField(
        max_length=10,
        choices=ConnectionStatus.choices,
        default=ConnectionStatus.PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            # Prevent self connection
            models.CheckConstraint(
                condition=~Q(sender=F("receiver")),
                name="prevent_self_connection",
            ),

            # Prevent duplicate pair in same direction
            models.UniqueConstraint(
                fields=["sender", "receiver"],
                name="unique_connection_pair",
            ),
        ]

    def clean(self):
        # Prevent self-connection at model level
        if self.sender == self.receiver:
            raise ValidationError("Users cannot connect with themselves.")

    def __str__(self):
        return f"{self.sender} -> {self.receiver}: {self.status}"
class Report(models.Model):
    """User‑to‑User reports for inappropriate behaviour."""
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reports_filed",
    )
    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reports_received",
    )
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report by {self.reporter} against {self.reported_user}"


class Block(models.Model):
    """User block system."""

    blocker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocks_made"
    )

    blocked_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_by"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["blocker", "blocked_user"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked_user}"


class Rating(models.Model):
    """
    Production-level Rating model for user activity ratings.
    
    Enforces:
    - One rating per activity per rater (unique constraint)
    - No self-rating
    - Score validation (1-5) at database and application level
    - Rater must be activity participant
    - Activity must be completed (past date/time)
    - Rater cannot rate if blocked or has blocked rated_user
    """
    rater = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ratings_given",
    )
    rated_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ratings_received",
    )
    activity = models.ForeignKey(
        Activity,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    score = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5),
        ],
    )
    feedback = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        
        # Unique constraint: one rating per activity per rater
        constraints = [
            # Prevent duplicate rating for the same activity by the same rater
            models.UniqueConstraint(
                fields=["rater", "activity"],
                name="unique_rating_per_activity_per_rater",
            ),
            
            # Prevent self-rating using Q and F expressions
            models.CheckConstraint(
                condition=~Q(rater=F("rated_user")),
                name="prevent_self_rating",
            ),
            
            # Database-level check: score must be 1-5
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=5),
                name="score_range_1_to_5",
            ),
        ]
        
        # Index on rated_user for faster average rating queries
        indexes = [
            models.Index(fields=["rated_user"], name="idx_rating_rated_user"),
        ]

    def clean(self):
        # Defensive checks
        if not self.activity or not self.rater or not self.rated_user:
            raise ValidationError("Invalid rating configuration.")

        # 1. Prevent self-rating first
        if self.rater == self.activity.creator:
            raise ValidationError(
                "The activity creator cannot rate themselves."
            )

        # 2. Rated user must be the creator
        if self.rated_user != self.activity.creator:
            raise ValidationError(
                "Only the activity creator can be rated."
            )

        # 3. Rater must be participant
        if not self.activity.participants.filter(pk=self.rater.pk).exists():
            raise ValidationError(
                "Only participants of this activity can rate the creator."
            )

        # 4. Activity must be completed
        if not self.activity.is_past():
            raise ValidationError(
                "Cannot rate an activity that has not yet been completed."
            )

        # 5. Block checks
        if Block.objects.filter(
            blocker=self.rater,
            blocked_user=self.activity.creator
        ).exists():
            raise ValidationError(
                "You have blocked this user."
            )

        if Block.objects.filter(
            blocker=self.activity.creator,
            blocked_user=self.rater
        ).exists():
            raise ValidationError(
                "This user has blocked you."
            )

    def save(self, *args, **kwargs):
        """
        Override save to call full_clean() for comprehensive validation.
        
        Ensures all model-level and application-level validations are enforced
        before persisting the rating to the database.
        """
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rater.username} rated {self.rated_user.username} for {self.activity.title}: {self.score}/5"

class Block(models.Model):
    """User block system."""

    blocker = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocks_made"
    )

    blocked_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blocked_by"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["blocker", "blocked_user"]]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked_user}"

class Meta:
    ordering = ["-created_at"]
    unique_together = [["reporter", "reported_user"]]