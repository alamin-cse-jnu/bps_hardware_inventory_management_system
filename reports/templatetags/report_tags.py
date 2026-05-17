from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Access a dict value by a variable key in templates."""
    return dictionary.get(key, "")
