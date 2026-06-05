import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import LoginAttempt

logger = logging.getLogger(__name__)


def normalize_login_email(value):
    return (value or '').strip().lower()[:254]


def get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def _get_attempt(email, ip_address):
    email = normalize_login_email(email) or 'sem-email@local.invalid'
    attempt, _created = LoginAttempt.objects.get_or_create(
        email=email,
        ip_address=ip_address,
        defaults={
            'failure_count': 0,
        },
    )
    return attempt


def get_login_lock(email, ip_address):
    email = normalize_login_email(email)
    if not email:
        return None

    try:
        attempt = LoginAttempt.objects.get(email=email, ip_address=ip_address)
    except LoginAttempt.DoesNotExist:
        return None

    if attempt.locked_until and attempt.locked_until <= timezone.now():
        attempt.failure_count = 0
        attempt.first_failure_at = None
        attempt.last_failure_at = None
        attempt.locked_until = None
        attempt.save(update_fields=['failure_count', 'first_failure_at', 'last_failure_at', 'locked_until', 'atualizado_em'])
        return None

    return attempt if attempt.is_locked else None


def is_login_locked(email, ip_address):
    return get_login_lock(email, ip_address) is not None


def record_failed_login(request, email):
    ip_address = get_client_ip(request)
    attempt = _get_attempt(email, ip_address)
    now = timezone.now()
    window_start = now - timedelta(minutes=settings.LOGIN_ATTEMPT_WINDOW_MINUTES)

    if not attempt.first_failure_at or attempt.first_failure_at < window_start:
        attempt.failure_count = 0
        attempt.first_failure_at = now
        attempt.locked_until = None

    attempt.failure_count += 1
    attempt.last_failure_at = now

    if attempt.failure_count >= settings.LOGIN_ATTEMPT_LIMIT:
        attempt.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
        logger.warning(
            'Login bloqueado por excesso de falhas. email=%s ip=%s falhas=%s bloqueado_ate=%s',
            attempt.email,
            attempt.ip_address,
            attempt.failure_count,
            attempt.locked_until,
        )
    else:
        logger.warning(
            'Falha de login. email=%s ip=%s falhas=%s',
            attempt.email,
            attempt.ip_address,
            attempt.failure_count,
        )

    attempt.save(update_fields=[
        'failure_count',
        'first_failure_at',
        'last_failure_at',
        'locked_until',
        'atualizado_em',
    ])
    return attempt


def clear_login_attempt(request, email):
    ip_address = get_client_ip(request)
    email = normalize_login_email(email)
    if not email:
        return
    LoginAttempt.objects.filter(email=email, ip_address=ip_address).delete()
