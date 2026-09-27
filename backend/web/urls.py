from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('account/', views.account, name='account'),

    path('scores/', views.score_list, name='scores'),
    path('scores/upload/', views.score_upload, name='score_upload'),
    path('scores/<int:pk>/', views.score_detail, name='score_detail'),
    path('scores/<int:pk>/view/', views.score_file, {'disposition': 'inline'}, name='score_view'),
    path('scores/<int:pk>/download/', views.score_file, {'disposition': 'download'}, name='score_download'),
    path('scores/<int:pk>/edit/', views.score_edit, name='score_edit'),
    path('scores/<int:pk>/delete/', views.score_delete, name='score_delete'),

    path('ensembles/', views.ensemble_list, name='ensembles'),
    path('ensembles/<int:pk>/', views.ensemble_detail, name='ensemble_detail'),
    path('ensembles/<int:pk>/edit/', views.ensemble_edit, name='ensemble_edit'),
    path('ensembles/<int:pk>/delete/', views.ensemble_delete, name='ensemble_delete'),
    path('ensembles/<int:pk>/members/<int:user_id>/', views.member_update, name='member_update'),
    path('ensembles/<int:pk>/members/<int:user_id>/remove/', views.member_remove, name='member_remove'),
    path('ensembles/<int:pk>/invites/', views.invite_create, name='invite_create'),
    path('ensembles/<int:pk>/invites/<int:invite_id>/revoke/', views.invite_revoke, name='invite_revoke'),

    path('join/', views.join, name='join_form'),
    path('join/<str:code>/', views.join, name='join'),
]
