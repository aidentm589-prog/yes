from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from vehicle_api import VehicleApiError, VehicleValueService


app = Flask(__name__)
app.json.sort_keys = False
app.secret_key = os.getenv("FLASK_SECRET_KEY", "car-flip-analyzer-dev-secret")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[assignment]
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "true").strip().lower() in {"1", "true", "yes", "on"}
service = VehicleValueService()


def canonical_host() -> str:
    return os.getenv("CANONICAL_HOST", "").strip().lower()


def public_base_url() -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    scheme = "https" if request.is_secure else "http"
    return f"{scheme}://{request.host}".rstrip("/")


def current_user() -> dict[str, Any] | None:
    return getattr(g, "current_user", None)


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        user = current_user()
        if not service.is_admin_user(user):
            return redirect(url_for("index"))
        return view(*args, **kwargs)

    return wrapped


@app.before_request
def load_current_user() -> None:
    service.ensure_background_workers()
    target_host = canonical_host()
    if (
        target_host
        and request.method in {"GET", "HEAD"}
        and not request.path.startswith("/healthz")
        and request.host
        and request.host.lower() != target_host
    ):
        destination = f"https://{target_host}{request.full_path.rstrip('?')}"
        return redirect(destination, code=308)
    user_id = session.get("user_id")
    g.current_user = service.get_user(user_id) if user_id else None


@app.get("/healthz")
def healthz():
    return jsonify({"ok": True, "status": "healthy"})


@app.context_processor
def inject_account_context() -> dict[str, Any]:
    user = current_user()
    return {
        "auth_user": user,
        "account_status": service.get_account_status(user["id"]) if user else None,
        "is_admin_user": service.is_admin_user(user),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/login")
def login():
    if current_user():
        return redirect(url_for("index"))
    return render_template("login.html", error=request.args.get("error", ""))


@app.post("/login")
def login_post():
    try:
        user = service.login_user(
            str(request.form.get("email") or ""),
            str(request.form.get("password") or ""),
        )
    except VehicleApiError as exc:
        return render_template("login.html", error=str(exc)), 400
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.get("/signup")
def signup():
    if current_user():
        return redirect(url_for("index"))
    return render_template("signup.html", error=request.args.get("error", ""))


@app.post("/signup")
def signup_post():
    try:
        user = service.create_user_account(
            str(request.form.get("first_name") or ""),
            str(request.form.get("email") or ""),
            str(request.form.get("password") or ""),
        )
    except VehicleApiError as exc:
        return render_template("signup.html", error=str(exc)), 400
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/magic-login/<token>")
def magic_login(token: str):
    try:
        user = service.login_with_magic_token(token)
    except VehicleApiError as exc:
        return render_template("login.html", error=str(exc)), 400
    session["user_id"] = user["id"]
    return redirect(url_for("index"))


@app.get("/account")
@login_required
def account():
    return render_template(
        "account.html",
        account_status=service.get_account_status(current_user()["id"]),
        test_admin=service.test_admin_credentials(),
    )


@app.get("/subscriptions")
def subscriptions():
    subscription_tiers = service.list_public_subscription_tiers()
    if current_user() and service.is_admin_user(current_user()):
        subscription_tiers = [
            {
                "tier": "admin",
                "display_name": "ADMIN",
                "monthly_price": "Custom",
                "yearly_price": "Custom",
                "marketing_copy": "Platform-level control with unlimited access, client dashboard control, and engine oversight.",
                "credits_granted": 0,
                "has_bulk_access": True,
                "has_addon_access": True,
                "is_unlimited": True,
                "is_free": False,
                "cta_label": "Apply Admin Access",
            },
            *subscription_tiers,
        ]
    return render_template("subscriptions.html", subscription_tiers=subscription_tiers)


@app.get("/credits")
def credits():
    credit_packages = [
        {
            "name": "Starter Stack",
            "credits": 10,
            "price": "$19",
            "copy": "A quick refill for a handful of personal values, Zippy runs, and premium add-ons.",
            "highlight": "Best for light scouting",
        },
        {
            "name": "Momentum Pack",
            "credits": 40,
            "price": "$69",
            "copy": "A stronger working balance for active evaluating, multiple add-ons, and repeat sessions.",
            "highlight": "Most popular",
        },
        {
            "name": "Dealer Flow",
            "credits": 120,
            "price": "$179",
            "copy": "Built for heavier operators who want room for repeated evaluations without watching the meter.",
            "highlight": "High-volume value",
        },
    ]
    return render_template("credits.html", credit_packages=credit_packages)


@app.get("/download-software")
def download_software():
    return render_template(
        "download_software.html",
        mac_download_url=url_for("static", filename="downloads/drive-and-comp-mac-native.zip"),
        windows_download_url=url_for("static", filename="downloads/drive-and-comp-windows.zip"),
    )


@app.get("/full-evaluation")
@login_required
def full_evaluation():
    return render_template("full_evaluation.html")


@app.get("/portfolio")
@login_required
def portfolio():
    return render_template("portfolio.html")


@app.get("/carvana-payout")
@login_required
def carvana_payout():
    return render_template("carvana_payout.html")


@app.get("/portfolio/<int:evaluation_id>")
@login_required
def portfolio_detail(evaluation_id: int):
    return render_template("portfolio_detail.html", evaluation_id=evaluation_id)


@app.get("/admin")
@admin_required
def admin():
    return redirect(url_for("admin_overview_page"))


@app.get("/admin/overview")
@admin_required
def admin_overview_page():
    return render_template("admin_overview.html", test_admin=service.test_admin_credentials())


@app.get("/admin/workbench")
@admin_required
def admin_workbench_page():
    return render_template("admin_workbench.html")


@app.get("/admin/clients")
@admin_required
def admin_clients_page():
    return render_template("admin_clients.html", test_admin=service.test_admin_credentials())


@app.get("/admin/subscriptions")
@admin_required
def admin_subscriptions_page():
    return redirect(url_for("admin_clients_page"))


@app.post("/api/valuation")
def valuation():
    payload = request.get_json(force=True, silent=True) or {}
    engine = str(payload.get("evaluation_engine", "resell") or "resell").strip().lower()
    mode = str(payload.get("evaluation_mode", "individual") or "individual").strip().lower()
    decision = service.authorize_evaluation_start(session.get("user_id"), engine, mode, payload)
    if not decision.allowed:
        return jsonify(
            {
                "ok": False,
                "message": decision.message,
                "account_status": service.get_account_status(decision.user["id"]) if decision.user else None,
            }
        ), decision.status_code
    try:
        result = service.run_condition_sweep(payload)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc), "account_status": service.get_account_status(session.get("user_id"))}), 400
    service.consume_credits(session.get("user_id"), decision.cost)
    return jsonify({"ok": True, **result, "account_status": service.get_account_status(session.get("user_id"))})


@app.get("/api/vehicle-suggestions")
def vehicle_suggestions():
    query = str(request.args.get("q") or "").strip()
    limit_raw = request.args.get("limit", "8")
    try:
        limit = int(limit_raw)
    except ValueError:
        limit = 8
    try:
        items = service.get_vehicle_input_suggestions(query, limit=limit)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc), "items": []}), 400
    return jsonify({"ok": True, "items": items})


@app.post("/api/potential-upgrades")
@login_required
def potential_upgrades():
    account_status = service.get_account_status(current_user()["id"])
    if not account_status or not account_status.get("has_addon_access"):
        return jsonify({
            "ok": False,
            "message": "Your current tier does not include Personal Value add-ons yet.",
            "account_status": account_status,
        }), 403
    payload = request.get_json(force=True, silent=True) or {}
    baseline_value = payload.get("baseline_value")
    try:
        baseline_float = float(str(baseline_value).replace("$", "").replace(",", ""))
    except Exception:  # noqa: BLE001
        return jsonify({"ok": False, "message": "A valid baseline value is required."}), 400
    body_style = str(payload.get("body_style") or "").strip()
    focus = str(payload.get("focus") or "").strip()
    vehicle_context = payload.get("vehicle_context") if isinstance(payload.get("vehicle_context"), dict) else {}
    try:
        result = service.get_potential_upgrade_candidates(
            baseline_value=baseline_float,
            body_style=body_style,
            focus=focus,
            vehicle_context=vehicle_context,
        )
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return jsonify({"ok": True, **result})


@app.post("/api/portfolio")
@login_required
def save_portfolio():
    payload = request.get_json(force=True, silent=True) or {}
    vehicle_title = str(payload.get("vehicle_title") or "").strip()
    vehicle_input = str(payload.get("vehicle_input") or "").strip()
    preview_payload = payload.get("preview") or {}
    snapshot_payload = payload.get("snapshot") or {}
    if not vehicle_title or not vehicle_input or not isinstance(preview_payload, dict) or not isinstance(snapshot_payload, dict):
        return jsonify({"ok": False, "message": "Missing portfolio payload."}), 400
    evaluation_id = service.save_evaluation(
        user_id=current_user()["id"],
        vehicle_title=vehicle_title,
        vehicle_input=vehicle_input,
        preview_payload=preview_payload,
        snapshot_payload=snapshot_payload,
    )
    return jsonify({"ok": True, "id": evaluation_id})


@app.get("/api/portfolio")
@login_required
def list_portfolio():
    return jsonify({"ok": True, "items": service.list_saved_evaluations(user_id=current_user()["id"])})


@app.get("/api/portfolio/<int:evaluation_id>")
@login_required
def get_portfolio(evaluation_id: int):
    item = service.get_saved_evaluation(evaluation_id, user_id=current_user()["id"])
    if not item:
        return jsonify({"ok": False, "message": "Evaluation not found."}), 404
    return jsonify({"ok": True, "item": item})


@app.patch("/api/portfolio/<int:evaluation_id>")
@login_required
def update_portfolio(evaluation_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    vehicle_title = str(payload.get("vehicle_title") or "").strip()
    preview_payload = payload.get("preview") or {}
    snapshot_payload = payload.get("snapshot") or {}
    if not vehicle_title or not isinstance(preview_payload, dict) or not isinstance(snapshot_payload, dict):
        return jsonify({"ok": False, "message": "Missing portfolio payload."}), 400
    updated = service.update_saved_evaluation(
        evaluation_id=evaluation_id,
        user_id=current_user()["id"],
        vehicle_title=vehicle_title,
        preview_payload=preview_payload,
        snapshot_payload=snapshot_payload,
    )
    if not updated:
        return jsonify({"ok": False, "message": "Evaluation not found."}), 404
    return jsonify({"ok": True})


@app.delete("/api/portfolio/<int:evaluation_id>")
@login_required
def delete_portfolio(evaluation_id: int):
    deleted = service.delete_saved_evaluation(evaluation_id, user_id=current_user()["id"])
    if not deleted:
        return jsonify({"ok": False, "message": "Evaluation not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/software-chat")
def software_chat():
    payload = request.get_json(force=True, silent=True) or {}
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        return jsonify({"ok": False, "message": "Invalid chat payload."}), 400
    try:
        result = service.software_chat_reply(messages)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return jsonify({"ok": True, **result})


@app.get("/api/account/status")
def account_status():
    status = service.get_account_status(session.get("user_id"))
    return jsonify({"ok": True, "account_status": status})


@app.delete("/api/account")
@login_required
def delete_current_account():
    deleted = service.delete_user_account(current_user()["id"])
    if not deleted:
        return jsonify({"ok": False, "message": "Unable to delete account."}), 400
    session.clear()
    return jsonify({"ok": True, "message": "Account deleted."})


@app.post("/api/account/subscription-select")
@login_required
def account_subscription_select():
    payload = request.get_json(force=True, silent=True) or {}
    tier = payload.get("tier")
    if tier is None:
        return jsonify({"ok": False, "message": "Missing tier."}), 400
    try:
        if str(tier).strip().lower() == "admin":
            updated = service.assign_admin_subscription(current_user()["id"])
        else:
            updated = service.update_user_tier(current_user()["id"], int(tier))
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not updated:
        return jsonify({"ok": False, "message": "Unable to update subscription."}), 400
    return jsonify({"ok": True, "account_status": updated, "message": f"{updated['tier_label']} is now active on this account."})


@app.get("/api/subscriptions")
def public_subscriptions():
    items = service.list_public_subscription_tiers()
    if current_user() and service.is_admin_user(current_user()):
        items = [
            {
                "tier": "admin",
                "display_name": "ADMIN",
                "monthly_price": "Custom",
                "yearly_price": "Custom",
                "marketing_copy": "Platform-level control with unlimited access, client dashboard control, and engine oversight.",
                "credits_granted": 0,
                "has_bulk_access": True,
                "has_addon_access": True,
                "is_unlimited": True,
                "is_free": False,
                "cta_label": "Apply Admin Access",
            },
            *items,
        ]
    return jsonify({"ok": True, "items": items})


@app.post("/api/final-buy-offer")
@login_required
def final_buy_offer():
    payload = request.get_json(force=True, silent=True) or {}
    evaluation = payload.get("evaluation") or {}
    if not isinstance(evaluation, dict) or not evaluation:
        return jsonify({"ok": False, "message": "Missing evaluation payload."}), 400
    try:
        result = service.build_final_buy_offer(current_user()["id"], evaluation)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc), "account_status": service.get_account_status(current_user()["id"])}), 400
    return jsonify({"ok": True, **result})


@app.post("/api/carvana-payout/jobs")
@login_required
def create_carvana_payout_job():
    payload = request.get_json(force=True, silent=True) or {}
    try:
        service.validate_carvana_payout_payload(payload)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc), "account_status": service.get_account_status(current_user()["id"])}), 400
    decision = service.authorize_carvana_payout_start(current_user()["id"])
    if not decision.allowed:
        return jsonify(
            {
                "ok": False,
                "message": decision.message,
                "account_status": service.get_account_status(decision.user["id"]) if decision.user else None,
            }
        ), decision.status_code
    try:
        job = service.create_carvana_payout_job(current_user()["id"], payload)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc), "account_status": service.get_account_status(current_user()["id"])}), 400
    service.consume_credits(current_user()["id"], decision.cost)
    return jsonify({"ok": True, "job": job, "account_status": service.get_account_status(current_user()["id"])}), 201


@app.get("/api/carvana-payout/jobs")
@login_required
def list_carvana_payout_jobs():
    limit = int(request.args.get("limit", "15") or "15")
    return jsonify({"ok": True, "items": service.list_carvana_payout_jobs(user_id=current_user()["id"], limit=limit)})


@app.get("/api/carvana-payout/jobs/<int:job_id>")
@login_required
def get_carvana_payout_job(job_id: int):
    job = service.get_carvana_payout_job(job_id, user_id=current_user()["id"])
    if not job:
        return jsonify({"ok": False, "message": "Payout job not found."}), 404
    return jsonify({"ok": True, "job": job})


@app.post("/api/carvana-payout/jobs/<int:job_id>/retry")
@login_required
def retry_carvana_payout_job(job_id: int):
    try:
        job = service.retry_carvana_payout_job(job_id, user_id=current_user()["id"])
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not job:
        return jsonify({"ok": False, "message": "Payout job not found."}), 404
    return jsonify({"ok": True, "job": job})


@app.get("/api/admin/overview")
@admin_required
def admin_overview():
    overview = service.admin_overview()
    overview["client_count"] = len(service.list_users())
    overview["test_admin"] = service.test_admin_credentials()
    return jsonify({"ok": True, **overview})


@app.get("/api/admin/users")
@admin_required
def admin_users():
    return jsonify({"ok": True, "items": service.list_users()})


@app.post("/api/admin/magic-links/mr-obrien")
@admin_required
def create_mr_obrien_magic_link():
    payload = request.get_json(force=True, silent=True) or {}
    email = str(payload.get("email") or "").strip() or None
    result = service.create_magic_login_link(public_base_url(), email=email)
    return jsonify({"ok": True, **result}), 201


@app.get("/api/admin/subscriptions")
@admin_required
def admin_subscriptions():
    return jsonify({"ok": True, "items": service.list_subscription_tiers()})


@app.get("/api/admin/payout-jobs")
@admin_required
def admin_payout_jobs():
    return jsonify({"ok": True, "items": service.list_carvana_payout_jobs(user_id=None, limit=30)})


@app.patch("/api/admin/users/<int:user_id>")
@admin_required
def admin_update_user(user_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    tier = payload.get("tier")
    credits = payload.get("credit_balance")
    first_name = payload.get("first_name")
    try:
        updated = None
        if first_name is not None:
            updated = service.update_user_profile(user_id, str(first_name))
        if tier is not None:
            if str(tier).strip().lower() == "admin":
                updated = service.assign_admin_subscription(user_id)
            else:
                updated = service.update_user_tier(user_id, int(tier), int(credits) if credits is not None else None)
        elif credits is not None:
            updated = service.update_user_credits(user_id, int(credits))
        elif updated is None:
            return jsonify({"ok": False, "message": "Missing user updates."}), 400
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not updated:
        return jsonify({"ok": False, "message": "User not found."}), 404
    return jsonify({"ok": True, "item": updated})


@app.patch("/api/admin/subscriptions/<int:tier>")
@admin_required
def admin_update_subscription(tier: int):
    payload = request.get_json(force=True, silent=True) or {}
    try:
        updated = service.update_subscription_tier(tier, payload)
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    return jsonify({"ok": True, "item": updated})


@app.patch("/api/admin/users/<int:user_id>/role")
@admin_required
def admin_update_user_role(user_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    role = str(payload.get("role") or "").strip().lower()
    if not role:
        return jsonify({"ok": False, "message": "Missing role."}), 400
    try:
        updated = service.update_user_role(user_id, role, actor_user_id=current_user()["id"])
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not updated:
        return jsonify({"ok": False, "message": "User not found."}), 404
    return jsonify({"ok": True, "item": updated})


@app.patch("/api/admin/users/<int:user_id>/status")
@admin_required
def admin_update_user_status(user_id: int):
    payload = request.get_json(force=True, silent=True) or {}
    status = str(payload.get("status") or "").strip().lower()
    if not status:
        return jsonify({"ok": False, "message": "Missing status."}), 400
    try:
        updated = service.update_user_status(user_id, status, actor_user_id=current_user()["id"])
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not updated:
        return jsonify({"ok": False, "message": "User not found."}), 404
    return jsonify({"ok": True, "item": updated})


@app.delete("/api/admin/users/<int:user_id>")
@admin_required
def admin_delete_user(user_id: int):
    try:
        deleted = service.delete_user_account(user_id, actor_user_id=current_user()["id"])
    except VehicleApiError as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400
    if not deleted:
        return jsonify({"ok": False, "message": "User not found."}), 404
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5001"))
    debug = os.getenv("FLASK_DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"}
    app.run(host="0.0.0.0", port=port, debug=debug)
