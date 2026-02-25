# social/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Profile, Rating

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create a Profile instance when a new User is created.
    """
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Ensure the Profile is saved whenever the User is saved.
    This handles cases where a Profile may have been created manually
    but not yet saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Rating)
def update_rated_user_stats(sender, instance, created, **kwargs):
    """
    Automatically update the rated_user's rating statistics when a rating is saved.
    
    Triggered on both create and update to ensure stats always reflect current data.
    Uses the Profile.update_rating_stats() method which:
    - Calculates average rating from all ratings received
    - Updates total_ratings count
    - Prevents division by zero with safe defaults
    """
    if hasattr(instance.rated_user, 'profile'):
        instance.rated_user.profile.update_rating_stats()