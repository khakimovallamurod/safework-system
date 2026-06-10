from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Returns dictionary[key], defaults to empty set."""
    return dictionary.get(key, set())
