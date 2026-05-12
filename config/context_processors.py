from config.permissions import role_context


def role_flags(request):
    if request.user.is_authenticated:
        return role_context(request.user)
    return {
        "user_is_admin": False,
        "user_is_it_officer": False,
        "user_is_viewer": False,
    }
