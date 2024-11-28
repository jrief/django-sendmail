import json
from collections import defaultdict

from django.template import loader
from django.template.base import NodeList, VariableNode
from django.template.defaulttags import ForNode
from django.template.loader_tags import IncludeNode, Variable
import re

def get_variables_structure(nodelist):
    variables = {}

    for node in nodelist:
        # Process nested nodelists recursively.
        if hasattr(node, 'nodelist'):
            nested_vars = get_variables_structure(node.nodelist)
            variables.update(nested_vars)

        # Handle variable nodes.
        if isinstance(node, VariableNode):
            var_name = node.filter_expression.var.var

            is_recipient_context = False
            if '.' in var_name:
                prefix = var_name.split('.')[0]
                var_name = var_name.split('.')[1]
                is_recipient_context = prefix == 'recipient'

            if not is_recipient_context:
                variables[var_name] = ""

        # Handle for-loop nodes.
        elif isinstance(node, ForNode):
            iterable_name = node.sequence.var.var
            is_recipient_context = False

            if '.' in iterable_name:
                prefix = iterable_name.split('.')[0]
                iterable_name = iterable_name.split('.')[1]
                is_recipient_context = prefix == 'recipient'

            loop_vars = get_variables_structure(node.nodelist_loop)

            # Initialize a list if the iterable isn't already in the dictionary.
            if iterable_name not in variables and not is_recipient_context:
                variables[iterable_name] = []

            # Append the loop variables as a dictionary inside the list.
            variables[iterable_name].append(loop_vars)

        elif isinstance(node, IncludeNode):
            included_template = node.template.var
            variables.update(extract_variable_names(included_template))

    return variables


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


def extract_variable_names(template_name):
    template = loader.get_template(template_name, using='sendmail')
    nodelist = template.template.nodelist
    return get_variables_structure(nodelist)


def get_ckeditor_variables(template):
    vars = []

    for content in template.contents.all():
        vars.extend(get_custom_vars(content.content))

    vars = list(set(vars))

    return filter(lambda x: not x.startswith('recipient'), vars)


def get_custom_vars(text):
    pattern = r"#(.*?)#"
    return list(set(re.findall(pattern, text)))
