from django.urls import path

from competitions.views import (
    add_customers_to_competition,
    create_competition,
    delete_competition,
    delete_competition_result,
    delete_customers_from_competition,
    get_competition_details,
    get_competition_results,
    get_competition_results_overview,
    get_competitions,
    save_competition_result,
    update_competition,
    update_competition_result,
)

app_name = "competitions"

urlpatterns = [
    path("create/", create_competition, name="create_competition"),
    path("list/", get_competitions, name="competitions_list"),
    path("<int:pk>/", get_competition_details, name="get_competition_details"),
    path("<int:pk>/update/", update_competition, name="update_competition"),
    path("<int:pk>/delete/", delete_competition, name="delete_competition"),
    path(
        "<int:pk>/add_customers/",
        add_customers_to_competition,
        name="add_customers_to_competition",
    ),
    path(
        "<int:pk>/delete_customers/",
        delete_customers_from_competition,
        name="delete_customers_from_competition",
    ),
    path(
        "competition/<int:competition_id>/result/<int:customer_id>/save/",
        save_competition_result,
        name="save_competition_result",
    ),
    path(
        "competition/<int:competition_id>/results/<int:customer_id>/",
        get_competition_results,
        name="get_competition_results",
    ),
    path(
        "competition/<int:competition_id>/results-overview/",
        get_competition_results_overview,
        name="get_competition_results_overview",
    ),
    path(
        "result/<int:result_id>/update/",
        update_competition_result,
        name="update_competition_result",
    ),
    path(
        "result/<int:result_id>/delete/",
        delete_competition_result,
        name="delete_competition_result",
    ),
]
