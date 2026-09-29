from django.urls import path

from . import views

app_name = 'web'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('auth/google/', views.google_start, name='google_start'),
    path('auth/google/callback/', views.google_callback, name='google_callback'),
    path('account/', views.account, name='account'),

    path('scores/', views.score_list, name='scores'),
    path('scores/upload/', views.score_upload, name='score_upload'),
    path('scores/<int:pk>/', views.score_detail, name='score_detail'),
    path('scores/<int:pk>/view/', views.score_file, {'disposition': 'inline'}, name='score_view'),
    path('scores/<int:pk>/download/', views.score_file, {'disposition': 'download'}, name='score_download'),
    path('scores/<int:pk>/edit/', views.score_edit, name='score_edit'),
    path('scores/<int:pk>/versions/', views.version_upload, name='version_upload'),
    path('scores/<int:pk>/versions/<int:number>/view/', views.score_file, {'disposition': 'inline'}, name='version_view'),
    path('scores/<int:pk>/versions/<int:number>/download/', views.score_file, {'disposition': 'download'}, name='version_download'),
    path('scores/<int:pk>/versions/<int:number>/musicxml/', views.version_musicxml, name='version_musicxml'),
    path('scores/<int:pk>/versions/<int:number>/musicxml/parts/', views.version_musicxml_parts,
         name='version_musicxml_parts'),
    path('scores/<int:pk>/pages/<int:number>/', views.score_page, name='score_page'),
    path('scores/<int:pk>/versions/<int:number>/current/', views.version_make_current, name='version_make_current'),
    path('scores/<int:pk>/versions/<int:number>/delete/', views.version_delete, name='version_delete'),
    path('scores/<int:pk>/delete/', views.score_delete, name='score_delete'),

    path('setlists/', views.setlist_list, name='setlists'),
    path('setlists/<int:pk>/', views.setlist_detail, name='setlist_detail'),
    path('setlists/<int:pk>/edit/', views.setlist_edit, name='setlist_edit'),
    path('setlists/<int:pk>/delete/', views.setlist_delete, name='setlist_delete'),
    path('setlists/<int:pk>/add/', views.setlist_add, name='setlist_add'),
    path('setlists/<int:pk>/items/<int:item_id>/', views.setlist_item, name='setlist_item'),

    path('ensembles/', views.ensemble_list, name='ensembles'),
    path('ensembles/<int:pk>/', views.ensemble_detail, name='ensemble_detail'),
    path('ensembles/<int:pk>/edit/', views.ensemble_edit, name='ensemble_edit'),
    path('ensembles/<int:pk>/delete/', views.ensemble_delete, name='ensemble_delete'),
    path('ensembles/<int:pk>/members/<int:user_id>/', views.member_update, name='member_update'),
    path('ensembles/<int:pk>/members/<int:user_id>/remove/', views.member_remove, name='member_remove'),
    path('ensembles/<int:pk>/invites/', views.invite_create, name='invite_create'),
    path('ensembles/<int:pk>/invites/<int:invite_id>/revoke/', views.invite_revoke, name='invite_revoke'),

    path('activate/', views.activate, name='activate'),
    path('devices/', views.device_list, name='devices'),
    path('devices/<uuid:pk>/rename/', views.device_rename, name='device_rename'),
    path('devices/<uuid:pk>/revoke/', views.device_revoke, name='device_revoke'),
    path('devices/<uuid:pk>/sync/', views.device_sync, name='device_sync'),

    path('manage/users/', views.user_list, name='users'),
    path('manage/users/<int:pk>/', views.user_edit, name='user_edit'),

    path('join/', views.join, name='join_form'),
    path('join/<str:code>/', views.join, name='join'),
]
