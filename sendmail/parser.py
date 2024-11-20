from django.template import loader
from django.template.base import NodeList, VariableNode
from django.template.loader_tags import IncludeNode, Variable
import re


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


def get_variables_names(nodelist):
    variables_names = []

    for node in nodelist:
        if hasattr(node, 'nodelist'):
            variables_names.extend(get_variables_names(node.nodelist))

        if hasattr(node, 'nodelist_loop'):
            variables_names.extend(get_variables_names(node.nodelist_loop))

        if isinstance(node, NodeList):
            variables_names.extend(get_variables_names(node))

        elif isinstance(node, VariableNode):
            variables_names.append(node.filter_expression.var.var)

        elif isinstance(node, IncludeNode):
            included_template = node.template.var
            variables_names.extend(extract_variable_names(included_template))

    return variables_names


def process_template(template_name):
    template = loader.get_template(template_name, using='sendmail')
    nodelist = template.template.nodelist
    return get_placeholders_names_from_nodes(nodelist)


def extract_variable_names(template_name):
    template = loader.get_template(template_name, using='sendmail')
    nodelist = template.template.nodelist
    return get_variables_names(nodelist)


def get_ckeditor_variables(template):
    vars = []

    for content in template.contents.all():
        vars.extend(get_custom_vars(content.content))

    return list(set(vars))


def get_custom_vars(text):
    pattern = r"#(.*?)#"
    return list(set(re.findall(pattern, text)))
