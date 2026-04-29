from django.urls import path

from api import views

app_name = "api"

urlpatterns = [
    path("auth/csrf/", views.csrf_token, name="csrf_token"),
    path("auth/login/", views.login_user, name="login_user"),
    path("auth/logout/", views.logout_user, name="logout_user"),
    path("client/dashboard/", views.client_dashboard, name="client_dashboard"),
    path("client/diary/", views.client_diary, name="client_diary"),
    path(
        "client/subscriptions/",
        views.client_subscriptions,
        name="client_subscriptions",
    ),
    path(
        "client/achievements/",
        views.client_achievements,
        name="client_achievements",
    ),
    path(
        "client/competition-results/",
        views.client_competition_results,
        name="client_competition_results",
    ),
    path("coach/dashboard/", views.coach_dashboard, name="coach_dashboard"),
    path("coach/classes/", views.coach_classes, name="coach_classes"),
    path("coach/groups/", views.coach_groups, name="coach_groups"),
    path(
        "coach/groups/<int:group_id>/",
        views.coach_group_detail,
        name="coach_group_detail",
    ),
    path(
        "coach/customers/<int:customer_id>/",
        views.coach_customer_detail,
        name="coach_customer_detail",
    ),
    path(
        "coach/customers/<int:customer_id>/subscriptions/issue/",
        views.coach_customer_issue_subscription,
        name="coach_customer_issue_subscription",
    ),
    path(
        "coach/subscriptions/options/",
        views.coach_subscription_form_options,
        name="coach_subscription_form_options",
    ),
    path(
        "coach/attendance/<int:attendance_id>/mark/",
        views.mark_attendance,
        name="mark_attendance",
    ),
    path(
        "coach/journal/<int:attendance_id>/mark/",
        views.mark_attendance,
        name="mark_journal_entry",
    ),
    path("me/", views.me, name="me"),
    path("customers/", views.customers, name="customers"),
    path("sport-categories/", views.sport_categories, name="sport_categories"),
    path("competitions/", views.competitions, name="competitions"),
    path(
        "competitions/<int:competition_id>/",
        views.competition_detail,
        name="competition_detail",
    ),
    path(
        "competitions/<int:competition_id>/results/",
        views.competition_results,
        name="competition_results",
    ),
    path(
        "competitions/<int:competition_id>/participants/",
        views.competition_participants,
        name="competition_participants",
    ),
    path(
        "competitions/<int:competition_id>/results/create/",
        views.create_result,
        name="create_result",
    ),
    path(
        "results/<int:result_id>/",
        views.result_detail,
        name="result_detail",
    ),
]
