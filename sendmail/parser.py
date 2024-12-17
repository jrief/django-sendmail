import re

from django.template import loader
from django.template.base import Node, NodeList, VariableNode
from django.template.context import Context
from django.template.defaulttags import ForNode
from django.template.loader_tags import ExtendsNode, IncludeNode

from compressor.offline.django import DjangoParser, handle_extendsnode


def get_variables_structure(nodelist):
    """
    Analyzes a list of nodes and constructs a dictionary representing the
    structure of variables referenced within those nodes. This function
    processes different types of nodes, such as variable nodes, for-loop
    nodes, and include nodes, to collect variable names and their
    corresponding contexts within the process. Variable nodes are added to
    the dictionary directly, while for-loop nodes add nested structures in
    the form of lists. The function also handles nested nodelists
    recursively.

    Parameters:
    nodelist : list
        A list of nodes to be analyzed for variable structure.

    Returns:
    dict
        A dictionary with variable names as keys and their corresponding
        contexts as values. The values could be empty strings for standalone
        variables, or lists of dictionaries for variables involved in loops.
    """
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
    """
    Recursively extracts placeholder names from a given list of nodes. This function
    traverses and processes nodes to collect all placeholder names present in the node
    list and any nested nodes. It handles various possible node attributes and types,
    such as `nodelist`, `nodelist_loop`, `NodeList`, token attributes with placeholders,
    and the `IncludeNode`.

    Args:
        nodelist: A list of nodes to be processed.

    Returns:
        A list of extracted placeholder names found within the nodes.
    """
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


def handle_includenode(includenode, context):
    """
    Process an IncludeNode to include the content of the referenced template.

    Args:
        includenode (IncludeNode): The IncludeNode to process.
        context (Context): The context in which to render the included template.

    Returns:
        NodeList: The nodelist of the included template.
    """
    included_template = includenode.template.resolve(context)
    if isinstance(included_template, str):
        included_template = loader.get_template(included_template)
    return included_template.template.nodelist


class SendmailParser(DjangoParser):
    def get_nodelist(self, node, original, context=None):
        if isinstance(node, ExtendsNode):
            if context is None:
                context = Context()
            context.template = original
            return handle_extendsnode(node, context)

        if isinstance(node, IncludeNode):
            if context is None:
                context = Context()
            context.template = original
            return handle_includenode(node, context)

        # Check if node is an ``{% if ... %}`` switch with true and false branches
        nodelist = []
        if isinstance(node, Node):
            for attr in node.child_nodelists:
                # see https://github.com/django-compressor/django-compressor/pull/825
                # and linked issues/PRs for a discussion on the `None) or []` part
                nodelist.extend(getattr(node, attr, None) or [])
        else:
            nodelist = getattr(node, "nodelist", [])
        return nodelist

    def walk_nodes(self, node, original=None, context=None):
        from sendmail.templatetags.sendmail import PlaceholderNode

        if original is None:
            original = node
        for node in self.get_nodelist(node, original, context):
            if isinstance(node, PlaceholderNode):
                yield node
            else:
                for node in self.walk_nodes(node, original, context):
                    yield node


def process_template(template_name):
    """
    Process a template to extract placeholder names.

    This function loads a template using the provided template name
    and extracts the placeholder names from its node list. It's useful
    for analyzing template content to identify which placeholders are
    being used, which can aid in dynamically populating templates
    before they are rendered.

    Args:
        template_name: The name of the template to process. It's used
                       to load and identify the specific template.

    Returns:
        list[str]: A list of placeholder names extracted from the nodes of the
        specified template.
    """
    parser = SendmailParser(charset='utf-8')
    template = parser.parse(template_name)
    nodes = parser.walk_nodes(template, original=template)
    return map(lambda node: node.name, nodes)


def extract_variable_names(template_name):
    """
    Extract variable names from a given template.

    This function loads a specified template using the Django template loader
    with a given name and retrieves its nodelist. It then extracts the
    variable structure from the nodelist using the `get_variables_structure`
    function.

    Args:
        template_name (str): The name of the template from which to extract
        variable names.

    Returns:
        dict:The structure of variables extracted from the template's nodelist.
    """
    template = loader.get_template(template_name, using='sendmail')
    nodelist = template.template.nodelist
    return get_variables_structure(nodelist)


def get_ckeditor_variables(template):
    """
    Extracts unique custom variables from the contents of a given
    template, excluding those that start with 'recipient'.

    Args:
        template: The EmailMerge object that contains contents from which
                  custom variables are to be extracted.

    Returns:
        list[str]: A filtered list of unique custom variables not starting with
        'recipient'.
    """
    vars = []

    for content in template.contents.all():
        vars.extend(get_custom_vars(content.content))

    vars = list(set(vars))

    return filter(lambda x: not x.startswith('recipient'), vars)


def get_custom_vars(text):
    """
    Extracts and returns a list of unique custom variables from the given text. A custom
    variable is defined as any substring enclosed within hash `#` characters. This function
    utilizes regular expressions to find all occurrences of such patterns and returns them
    as a list of unique elements.

    Args:
        text (str): The input text from which to extract custom variables.

    Returns:
        list[str]: A list containing unique custom variables found within the input text.
    """
    pattern = r"#(.*?)#"
    return list(set(re.findall(pattern, text)))
