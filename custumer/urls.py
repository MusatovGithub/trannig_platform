from django.urls import path

from custumer.achievements.views import (
    assign_achievements,
    get_my_achievements,
)
from custumer.api_views import (
    home_distances,
    home_group_ratings,
    home_news,
    home_subscriptions,
    home_team_members,
    home_trainings,
)
from custumer.cabinet.views import (
    add_to_cart,
    buy_product,
    checkout_cart,
    get_cart,
    get_client_diary,
    get_competition_results,
    get_group_detail,
    get_kilometers_history,
    get_marketplace,
    get_member_achievements,
    get_member_competitions,
    get_my_competitions,
    get_my_orders,
    get_my_orders_detail,
    get_my_purchases,
    get_my_subscriptions_history,
    get_points_history,
    remove_from_cart,
    team_member_detail,
)
from custumer.cashier.views import (
    cashier_create,
    cashier_delete,
    cashier_list,
    cashier_update,
)
from custumer.docs.views import custumer_docs_all, custumer_dos_delet
from custumer.payment.views import (
    custumer_payment,
    custumer_payment_create,
    custumer_payment_delete,
    custumer_payment_history,
    get_attendances_by_group_ajax,
)
from custumer.representatives.views import (
    custumer_representatives_all,
    custumer_representatives_create,
    custumer_representatives_delete,
)
from custumer.sub_template.views import (
    subscription_template_add,
    subscription_template_all,
    subscription_template_delete,
    subscription_template_update,
)
from custumer.subscription.views import (
    close_subscription,
    custumer_subscriptions,
    custumer_subscriptions_add,
    custumer_subscriptions_detele,
    custumer_subscriptions_update,
    open_subscription,
    subscription_detail,
)
from custumer.views import (
    close_cabinet_access,
    customer_create,
    customer_list,
    custumer_detaile,
    custumer_update,
    cutsumer_delete,
    resend_client_credentials,
    send_client_credentials,
    update_balance,
)

app_name = "customer"

urlpatterns = [
    path("customer/all/", customer_list, name="customer_list"),
    path("customer/add/", customer_create, name="customer_create"),
    path(
        "customer/detail/<int:pk>/", custumer_detaile, name="custumer_detaile"
    ),
    path("customer/update/<int:pk>/", custumer_update, name="custumer_update"),
    path("customer/delete/<int:pk>/", cutsumer_delete, name="cutsumer_delete"),
    path(
        "customer/close-cabinet/<int:pk>/",
        close_cabinet_access,
        name="close_cabinet_access",
    ),
    path(
        "close-sub/<int:sub_id>/",
        close_subscription,
        name="close_subscription",
    ),
    path(
        "customer/send/credentials/<int:pk>/",
        send_client_credentials,
        name="send_client_credentials",
    ),
    path(
        "customer/resend/credentials/<int:pk>/",
        resend_client_credentials,
        name="resend_client_credentials",
    ),
    path("customer/update_balance/", update_balance, name="update_balance"),
    # ------ subscriptions ---
    path(
        "customer/<int:pk>/subscriptions/",
        custumer_subscriptions,
        name="custumer_subscriptions",
    ),
    path(
        "customer/<int:pk>/subscriptions/create/",
        custumer_subscriptions_add,
        name="custumer_subscriptions_add",
    ),
    path(
        "customer/<int:custumer_id>/subscriptions/<int:sub_id>/update/",
        custumer_subscriptions_update,
        name="custumer_subscriptions_update",
    ),
    path(
        "customer/<int:custumer_id>/subscriptions/<int:sub_id>/delete/",
        custumer_subscriptions_detele,
        name="custumer_subscriptions_detele",
    ),
    path(
        "subscription/<int:sub_id>/detail/",
        subscription_detail,
        name="subscription_detail",
    ),
    path(
        "subscription/<int:sub_id>/open/",
        open_subscription,
        name="open_subscription",
    ),
    # Docs
    path(
        "customer/<int:pk>/docs/", custumer_docs_all, name="custumer_docs_all"
    ),
    path(
        "customer/<int:custumer_id>/doc/<int:doc_id>/delete/",
        custumer_dos_delet,
        name="custumer_dos_delet",
    ),
    # Representatives
    path(
        "customer/<int:pk>/representatives/",
        custumer_representatives_all,
        name="custumer_representatives_all",
    ),
    path(
        "customer/<int:pk>/representatives/create/",
        custumer_representatives_create,
        name="custumer_representatives_create",
    ),
    path(
        "customers/<int:customer_id>/representatives/<int:representative_id>/delete/",  # noqa: E501
        custumer_representatives_delete,
        name="custumer_representatives_delete",
    ),
    # Cashier
    path("cashier/list/", cashier_list, name="cashier_list"),
    path("cashier/create/", cashier_create, name="cashier_create"),
    path("cashier/<int:pk>/update/", cashier_update, name="cashier_update"),
    path("cashier/<int:pk>/delete/", cashier_delete, name="cashier_delete"),
    # Payment
    path(
        "customer/<int:pk>/payment/", custumer_payment, name="custumer_payment"
    ),
    path(
        "customer/<int:custumer_id>/payment/<int:group_id>/add/",
        custumer_payment_create,
        name="custumer_payment_create",
    ),
    path(
        "customer/<int:customer_id>/payment/<int:group_id>/ajax/",
        get_attendances_by_group_ajax,
        name="get_attendances_by_group_ajax",
    ),
    path(
        "customer/payment/history/<int:pk>/",
        custumer_payment_history,
        name="custumer_payment_history",
    ),
    path(
        "customer/<int:custumer_id>/payment/<int:payment_id>/delete/",
        custumer_payment_delete,
        name="custumer_payment_delete",
    ),
    # Subscription Templte
    path(
        "subscription/template/",
        subscription_template_all,
        name="subscription_template_all",
    ),
    path(
        "subscription/template/add/",
        subscription_template_add,
        name="subscription_template_add",
    ),
    path(
        "subscription/template/<int:pk>/update/",
        subscription_template_update,
        name="subscription_template_update",
    ),
    path(
        "subscription/template/<int:pk>/delete/",
        subscription_template_delete,
        name="subscription_template_delete",
    ),
    # Achievements
    path(
        "customer/<int:pk>/achievements/",
        assign_achievements,
        name="assign_achievements",
    ),
    path(
        "customer/cabinet/achievements/",
        get_my_achievements,
        name="my_achievements",
    ),
    # My Diary
    path(
        "customer/cabinet/diary/",
        get_client_diary,
        name="get_client_diary",
    ),
    # My Competitions
    path(
        "customer/cabinet/competitions/",
        get_my_competitions,
        name="get_my_competitions",
    ),
    # Marketplace
    path(
        "customer/cabinet/marketplace/",
        get_marketplace,
        name="get_marketplace",
    ),
    path(
        "customer/cabinet/marketplace/buy/<int:product_id>/",
        buy_product,
        name="purchase_product",
    ),
    path(
        "customer/cabinet/my_purchases/",
        get_my_purchases,
        name="get_my_purchases",
    ),
    # Cart functionality
    path(
        "customer/cabinet/cart/",
        get_cart,
        name="get_cart",
    ),
    path(
        "customer/cabinet/cart/add/<int:product_id>/",
        add_to_cart,
        name="add_to_cart",
    ),
    path(
        "customer/cabinet/cart/remove/<int:product_id>/",
        remove_from_cart,
        name="remove_from_cart",
    ),
    path(
        "customer/cabinet/cart/checkout/",
        checkout_cart,
        name="checkout_cart",
    ),
    # Мои заказы
    path(
        "customer/cabinet/orders/",
        get_my_orders,
        name="get_my_orders",
    ),
    path(
        "customer/cabinet/orders/<int:pk>/",
        get_my_orders_detail,
        name="get_my_orders_detail",
    ),
    # Points History
    path(
        "customer/cabinet/points_history/",
        get_points_history,
        name="get_points_history",
    ),
    # Subscriptions History
    path(
        "customer/cabinet/subscriptions_history/",
        get_my_subscriptions_history,
        name="get_my_subscriptions_history",
    ),
    # Team Member Detail
    path(
        "customer/cabinet/team_member/<int:member_id>/",
        team_member_detail,
        name="team_member_detail",
    ),
    path(
        "customer/cabinet/team_member/<int:member_id>/achievements/",
        get_member_achievements,
        name="get_member_achievements",
    ),
    path(
        "customer/cabinet/team_member/<int:member_id>/competitions/",
        get_member_competitions,
        name="get_member_competitions",
    ),
    path(
        "customer/cabinet/team_member/<int:member_id>/"
        "competitions/<int:competition_id>/results/",
        get_competition_results,
        name="get_competition_results",
    ),
    # Home page async endpoints
    path(
        "customer/cabinet/home/trainings/",
        home_trainings,
        name="home_trainings",
    ),
    path(
        "customer/cabinet/home/subscriptions/",
        home_subscriptions,
        name="home_subscriptions",
    ),
    path(
        "customer/cabinet/home/news/",
        home_news,
        name="home_news",
    ),
    path(
        "customer/cabinet/home/group-ratings/",
        home_group_ratings,
        name="home_group_ratings",
    ),
    path(
        "customer/cabinet/home/team-members/",
        home_team_members,
        name="home_team_members",
    ),
    path(
        "customer/cabinet/home/distances/",
        home_distances,
        name="home_distances",
    ),
    # Kilometers History
    path(
        "customer/cabinet/kilometers_history/",
        get_kilometers_history,
        name="get_kilometers_history",
    ),
    # Group Detail
    path(
        "customer/cabinet/group/<int:group_id>/",
        get_group_detail,
        name="get_group_detail",
    ),
]
