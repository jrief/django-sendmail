from django.template.base import NodeList
from django.template.loader_tags import IncludeNode
from django.template import loader


def get_placeholders_names_from_nodes(nodelist):
    placeholders_names = []

    for node in nodelist:
        if hasattr(node, 'nodelist'):
            placeholders_names.extend(get_placeholders_names_from_nodes(node.nodelist))
        if hasattr(node, 'nodelist_loop'):
            placeholders_names.extend(get_placeholders_names_from_nodes(node.nodelist_loop))
        if isinstance(node, NodeList):
            placeholders_names.extend(get_placeholders_names_from_nodes(node))

        elif hasattr(node, 'token') and 'placeholder' in node.token.contents:
            token_parts = node.token.contents.split()
            if len(token_parts) >= 2 and token_parts[0] == 'placeholder':
                placeholder_name = token_parts[1].strip("'\"")
                placeholders_names.append(placeholder_name)

        elif isinstance(node, IncludeNode):
            included_template = node.template.var
            placeholders_names.extend(process_template(included_template))

        # elif isinstance(node, ExtendsNode):
        #     parent_template = node.get_parent(None)
        #     placeholders_names.extend(process_template(parent_template.name))

    return placeholders_names


def process_template(template_name):
    template = loader.get_template(template_name, using='sendmail')
    nodelist = template.template.nodelist
    return get_placeholders_names_from_nodes(nodelist)
