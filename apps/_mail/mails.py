from typing import Literal, TypedDict, overload

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.timezone import now


class WelcomeCTX(TypedDict):
    user_display_name: str
    temporary_password: str
    login_url: str


class ResetPasswordCTX(TypedDict):
    token: str
    expire_in: str
    redirect_url: str


@overload
def send_mail(*, template: Literal["welcome.html"], ctx: WelcomeCTX, **kwargs) -> None: ...


@overload
def send_mail(
    *, template: Literal["reset_password_request.html"], ctx: ResetPasswordCTX, **kwargs
) -> None: ...


def send_mail(
    *, template: str, ctx: dict, subject: str, to: list[str], reply_to: list[str] | None = None
):
    """Send an email using a specified template, context, subject, and recipient list. The email is sent in both HTML and plain text formats."""

    ctx["current_year"] = now().year

    html_content = render_to_string(template, ctx)

    email = EmailMultiAlternatives(
        subject=subject,
        body=strip_tags(html_content),
        from_email=None,
        to=to,
        reply_to=reply_to,
    )
    email.attach_alternative(html_content, "text/html")

    email.send(fail_silently=False)
