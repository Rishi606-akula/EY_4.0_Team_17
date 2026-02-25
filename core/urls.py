# social/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views

from . import views


urlpatterns = [
    # Home / Discover
    path("", views.home, name="home"),
    path("discover/", views.discover, name="discover"),
    
    # Authentication
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile
    path("edit-profile/", views.edit_profile, name="edit_profile"),
    
    # Activity
    path("create-activity/", views.create_activity, name="create_activity"),
    path("join/<int:id>/", views.join_activity, name="join_activity"),
    
    # Connections
    path("connect/<int:id>/", views.send_connection, name="send_connection"),
    path("accept/<int:id>/", views.accept_connection, name="accept_connection"),
    path("reject/<int:id>/", views.reject_connection, name="reject_connection"),
    
    # Ratings & Reports
    path("rate/<int:activity_id>/<int:user_id>/", views.rate_user, name="rate_user"),
    path("report/<int:user_id>/", views.report_user, name="report_user"),
    
    # Blocking
    path("block/<int:user_id>/", views.block_user, name="block_user"),
    path("unblock/<int:user_id>/", views.unblock_user, name="unblock_user"),
    #print("Core URLs Loaded")
]