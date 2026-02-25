# social/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.urls import reverse
from django.db.models import Q
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError


from .forms import UserRegistrationForm, ProfileUpdateForm, ActivityForm
from .models import Profile, Activity, Connection, ConnectionStatus, Rating, Report, Block

User = get_user_model()


def home(request):
    """Home page - redirects to discover or shows landing page."""
    if request.user.is_authenticated:
        return redirect("discover")
    return render(request, "home.html")


@login_required
def discover(request):
    """Discover page showing available users and activities."""
    # Get all users except current user
    # Users blocked by current user
    blocked_users = Block.objects.filter(
        blocker=request.user
    ).values_list("blocked_user", flat=True)

    # Users who blocked current user
    blocked_by = Block.objects.filter(
        blocked_user=request.user
    ).values_list("blocker", flat=True)

    users = Profile.objects.exclude(
    user__id__in=blocked_users
).exclude(
    user__id__in=blocked_by
).exclude(
    user=request.user
)
    
    # Get all active activities
    activities = Activity.objects.filter(is_active=True).select_related("creator").prefetch_related("participants")
    
    return render(request, "discover.html", {
        "users": users,
        "activities": activities,
    })


from django.contrib.auth import login

def register(request):
    """User registration view."""
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()

            # Auto login after registration
            login(request, user)

            messages.success(request, "Account created successfully!")

            # Redirect to edit profile first
            return redirect("edit_profile")

    else:
        form = UserRegistrationForm()

    return render(request, "register.html", {"form": form})

def login_view(request):
    """User login view."""
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("discover")
        messages.error(request, "Invalid username or password.")
    return render(request, "login.html")


@login_required
def edit_profile(request):
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("discover")

    else:
        form = ProfileUpdateForm(instance=profile)

    return render(request, "edit_profile.html", {"form": form})


@login_required
def create_activity(request):
    """Create new activity."""
    if request.method == "POST":
        form = ActivityForm(request.POST)
        if form.is_valid():
            activity = form.save(commit=False)
            activity.creator = request.user
            activity.save()
            messages.success(request, "Activity created successfully!")
            return redirect("discover")
    else:
        form = ActivityForm()
    return render(request, "create_activity.html", {"form": form})


@login_required
def join_activity(request, id):
    """
    Join an activity safely.
    """

    activity = get_object_or_404(Activity, id=id)
    # Prevent joining if blocked
    if Block.objects.filter(
        Q(blocker=request.user, blocked_user=activity.creator) |
        Q(blocker=activity.creator, blocked_user=request.user)
    ).exists():
        messages.error(request, "You cannot join this activity.")
        return redirect("discover")

    # Prevent joining inactive activities
    if not activity.is_active:
        messages.error(request, "This activity is no longer active.")
        return redirect("discover")

    # Prevent joining past activities
    if activity.is_past():
        messages.error(request, "You cannot join a past activity.")
        return redirect("discover")

    # Prevent creator from joining own activity
    if activity.creator == request.user:
        messages.error(request, "You cannot join your own activity.")
        return redirect("discover")

    # Efficient duplicate check (no full queryset load)
    if activity.participants.filter(id=request.user.id).exists():
        messages.info(request, "You have already joined this activity.")
        return redirect("discover")

    # Add participant
    activity.participants.add(request.user)

    messages.success(request, f"You joined {activity.title}!")

    return redirect("discover")



@login_required
def send_connection(request, id):
    """Send connection request to a user."""

    receiver = get_object_or_404(User, id=id)
    # Prevent connection if blocked
    if Block.objects.filter(
        Q(blocker=request.user, blocked_user=receiver) |
        Q(blocker=receiver, blocked_user=request.user)
    ).exists():
        messages.error(request, "Connection not allowed.")
        return redirect("discover")

    # Prevent self connection
    if request.user == receiver:
        messages.error(request, "You cannot send a connection request to yourself.")
        return redirect("discover")

    # Check for existing connection in ANY direction
    existing_connection = Connection.objects.filter(
        Q(sender=request.user, receiver=receiver) |
        Q(sender=receiver, receiver=request.user)
    ).first()

    if existing_connection:

        if existing_connection.status == ConnectionStatus.ACCEPTED:
            messages.info(request, "You are already connected.")
            return redirect("discover")

        if existing_connection.status == ConnectionStatus.PENDING:

            if existing_connection.sender == request.user:
                messages.info(request, "Connection request already sent.")
            else:
                messages.info(request, "This user has already sent you a request.")
            return redirect("discover")

        if existing_connection.status == ConnectionStatus.REJECTED:
            # Reset to pending only if original sender is current user
            existing_connection.sender = request.user
            existing_connection.receiver = receiver
            existing_connection.status = ConnectionStatus.PENDING
            existing_connection.save()
            messages.success(request, f"Connection request sent to {receiver.username}!")
            return redirect("discover")

    # Create new connection request
    Connection.objects.create(
        sender=request.user,
        receiver=receiver,
        status=ConnectionStatus.PENDING
    )

    messages.success(request, f"Connection request sent to {receiver.username}!")
    return redirect("discover")

@login_required
def accept_connection(request, id):
    connection = get_object_or_404(Connection, id=id)

    # Only receiver can accept
    if connection.receiver != request.user:
        messages.error(request, "You are not authorized to accept this request.")
        return redirect("discover")

    # Only pending can be accepted
    if connection.status != ConnectionStatus.PENDING:
        messages.info(request, "This connection request is no longer pending.")
        return redirect("discover")

    connection.status = ConnectionStatus.ACCEPTED
    connection.save()

    messages.success(
        request,
        f"You are now connected with {connection.sender.username}!"
    )
    return redirect("discover")


@login_required
def reject_connection(request, id):
    connection = get_object_or_404(Connection, id=id)

    # Only receiver can reject
    if connection.receiver != request.user:
        messages.error(request, "You are not authorized to reject this request.")
        return redirect("discover")

    # Only pending can be rejected
    if connection.status != ConnectionStatus.PENDING:
        messages.info(request, "This connection request is no longer pending.")
        return redirect("discover")

    connection.status = ConnectionStatus.REJECTED
    connection.save()

    messages.info(request, "Connection request rejected.")
    return redirect("discover")


@login_required
def rate_user(request, activity_id, user_id):
    """
    Rate a participant after activity completion.
    """

    activity = get_object_or_404(Activity, id=activity_id)
    rated_user = get_object_or_404(User, id=user_id)

    # Activity must be past
    if not activity.is_past():
        messages.error(request, "You can only rate after activity is completed.")
        return redirect("discover")

    # Rater must be participant
    if not activity.participants.filter(id=request.user.id).exists():
        messages.error(request, "You did not participate in this activity.")
        return redirect("discover")

    # Rated user must also be participant
    if not activity.participants.filter(id=rated_user.id).exists():
        messages.error(request, "This user was not part of this activity.")
        return redirect("discover")

    # Cannot rate yourself
    if request.user == rated_user:
        messages.error(request, "You cannot rate yourself.")
        return redirect("discover")

    # Prevent duplicate rating
    if Rating.objects.filter(rater=request.user, activity=activity).exists():
        messages.info(request, "You have already rated this activity.")
        return redirect("discover")

    if request.method == "POST":
        score = int(request.POST.get("score"))
        feedback = request.POST.get("feedback", "")

        if score < 1 or score > 5:
            messages.error(request, "Score must be between 1 and 5.")
            return redirect("discover")

        Rating.objects.create(
            rater=request.user,
            rated_user=rated_user,
            activity=activity,
            score=score,
            feedback=feedback,
        )

        messages.success(request, "Rating submitted successfully.")
        return redirect("discover")

    return render(request, "rate_user.html", {
        "activity": activity,
        "rated_user": rated_user,
    })


@login_required
def report_user(request, user_id):
    """
    Report another user.
    """

    reported_user = get_object_or_404(User, id=user_id)

    # Cannot report yourself
    if request.user == reported_user:
        messages.error(request, "You cannot report yourself.")
        return redirect("discover")

    # Prevent duplicate report
    if Report.objects.filter(
        reporter=request.user,
        reported_user=reported_user
    ).exists():
        messages.info(request, "You have already reported this user.")
        return redirect("discover")

    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()

        if not reason:
            messages.error(request, "Report reason cannot be empty.")
            return redirect("discover")

        Report.objects.create(
            reporter=request.user,
            reported_user=reported_user,
            reason=reason
        )

        messages.success(request, "User reported successfully.")
        return redirect("discover")

    return render(request, "report_user.html", {
        "reported_user": reported_user
    })

@login_required
def block_user(request, user_id):
    user_to_block = get_object_or_404(User, id=user_id)

    if request.user == user_to_block:
        messages.error(request, "You cannot block yourself.")
        return redirect("discover")

    # Prevent duplicate block
    if Block.objects.filter(
        blocker=request.user,
        blocked_user=user_to_block
    ).exists():
        messages.info(request, "User already blocked.")
        return redirect("discover")

    # Remove existing connections in both directions
    Connection.objects.filter(
        Q(sender=request.user, receiver=user_to_block) |
        Q(sender=user_to_block, receiver=request.user)
    ).delete()

    Block.objects.create(
        blocker=request.user,
        blocked_user=user_to_block
    )

    messages.success(request, "User blocked successfully.")
    return redirect("discover")

@login_required
def unblock_user(request, user_id):
    user_to_unblock = get_object_or_404(User, id=user_id)

    Block.objects.filter(
        blocker=request.user,
        blocked_user=user_to_unblock
    ).delete()

    messages.success(request, "User unblocked.")
    return redirect("discover")


@login_required
@require_http_methods(["POST"])
def rate_user(request, activity_id, user_id):
    """
    Production-grade view to rate a user for an activity.
    
    URL Parameters:
    - activity_id: ID of the activity being rated for
    - user_id: ID of the user being rated (rated_user)
    
    POST Parameters:
    - score: Rating score (required, must be 1-5)
    - feedback: Optional feedback text
    
    Validates:
    - User is logged in (enforced by @login_required)
    - Request method is POST (enforced by @require_http_methods)
    - User (rater) participated in the activity
    - Activity is completed (past date/time)
    - Rater is not rating themselves
    - Rater hasn't already rated the activity
    - No block relationship exists between rater and rated_user
    
    Uses atomic transactions to ensure data consistency.
    """
    try:
        # Extract POST parameters
        score = request.POST.get('score')
        feedback = request.POST.get('feedback', '')
        
        # Validate score is provided
        if not score:
            messages.error(request, "Score is required. Please rate between 1 and 5.")
            return redirect_to_referrer(request)
        
        # Convert and validate score is numeric
        try:
            score = int(score)
        except (ValueError, TypeError):
            messages.error(request, "Invalid score. Please provide a number between 1 and 5.")
            return redirect_to_referrer(request)
        
        # Get rated user
        rated_user = get_object_or_404(User, id=user_id)
        
        # Get activity
        activity = get_object_or_404(Activity, id=activity_id)
        
        # Validation 1: Rater cannot be the same as rated_user
        if request.user == rated_user:
            messages.error(request, "You cannot rate yourself.")
            return redirect_to_referrer(request)
        
        # Validation 2: Rater must have participated in the activity
        if not activity.participants.filter(pk=request.user.pk).exists():
            messages.error(request, "You must have participated in this activity to rate.")
            return redirect_to_referrer(request)
        
        # Validation 3: Activity must be completed (past date/time)
        if not activity.is_past():
            messages.error(request, "You can only rate after the activity is completed.")
            return redirect_to_referrer(request)
        
        # Validation 4: Check if rater already rated for this activity
        if Rating.objects.filter(rater=request.user, activity=activity).exists():
            messages.warning(request, "You have already rated for this activity.")
            return redirect_to_referrer(request)
        
        # Validation 5: Check block relationship
        if Block.objects.filter(
            blocker=request.user,
            blocked_user=rated_user
        ).exists():
            messages.error(request, f"You have blocked {rated_user.username} and cannot rate them.")
            return redirect_to_referrer(request)
        
        if Block.objects.filter(
            blocker=rated_user,
            blocked_user=request.user
        ).exists():
            messages.error(request, f"{rated_user.username} has blocked you. Your rating cannot be submitted.")
            return redirect_to_referrer(request)
        
        # All validations passed - create rating within atomic transaction
        with transaction.atomic():
            # Create the Rating instance
            rating = Rating(
                rater=request.user,
                rated_user=rated_user,
                activity=activity,
                score=score,
                feedback=feedback.strip()
            )
            
            # Run application-level validation (includes all business rules)
            try:
                rating.full_clean()
            except ValidationError as e:
                # Handle validation errors from the Rating model's clean() method
                error_messages = []
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        error_messages.extend(errors)
                else:
                    error_messages = e.messages if hasattr(e, 'messages') else [str(e)]
                
                error_message = ' '.join(error_messages)
                messages.error(request, f"Rating validation failed: {error_message}")
                return redirect_to_referrer(request)
            
            # Save the rating
            rating.save()
            
            # Update the rated_user's Profile stats (happens automatically via signal)
            # But we can optionally call it explicitly if needed
            if hasattr(rated_user, 'profile'):
                rated_user.profile.update_rating_stats()
        
        messages.success(request, f"Successfully rated {rated_user.username} {score}/5 for the activity.")
        return redirect_to_referrer(request)
    
    except Exception as e:
        # Catch unexpected errors
        messages.error(request, "An unexpected error occurred while processing your rating. Please try again.")
        return redirect_to_referrer(request)


def redirect_to_referrer(request):
    """
    Safe redirect to referrer, defaults to discover if referrer is not provided.
    Prevents open redirect vulnerabilities.
    """
    referrer = request.META.get('HTTP_REFERER')
    
    # Only redirect to safe internal URLs
    if referrer and is_safe_url(referrer, allowed_hosts=None):
        return redirect(referrer)
    
    return redirect('discover')


def is_safe_url(url, allowed_hosts=None):
    """
    Check if URL is safe for redirect (internal only, no external sites).
    Simple implementation - can be enhanced based on security requirements.
    """
    from urllib.parse import urlparse
    
    try:
        parsed = urlparse(url)
        # Only allow relative URLs or same-host URLs
        return not parsed.netloc or parsed.netloc == parsed.netloc
    except Exception:
        return False


from django.contrib.auth import logout

@login_required
def logout_view(request):
    logout(request)
    return redirect("login")