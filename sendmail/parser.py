import re

from django.template import loader
from django.template.base import Node, NodeList, VariableNode
from django.template.context import Context
from django.template.defaulttags import ForNode
from django.template.loader_tags import ExtendsNode, IncludeNode

from compressor.offline.django import DjangoParser, handle_extendsnode


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

    def walk_context_nodes(self, node, original=None, context=None, iterable=None):

        if original is None:
            original = node

        for node in self.get_nodelist(node, original, context):
            if isinstance(node, VariableNode):
                if iterable:
                    node.loc = iterable
                yield node
            else:
                iter_list = iterable
                if isinstance(node, ForNode):
                    seq = node.sequence.var.var
                    seq = seq.split('.')[-1]
                    iter_list = [*iter_list, seq] if iter_list else [seq]
                for node in self.walk_context_nodes(node, original, context, iterable=iter_list):
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
    parser = SendmailParser(charset='utf-8')
    template = parser.parse(template_name)
    nodes = parser.walk_context_nodes(template, original=template)
    list_nodes = list(nodes)
    structure = {}
    for node in list_nodes:
        loc = getattr(node, 'loc', [])
        key = node.filter_expression.var.var

        if key.startswith('recipient'):
            continue

        key = key.split('.')[-1]
        current = structure
        for i in loc:
            if i not in current:
                current[i] = []
            if not current[i]:
                current[i].append({})
            current = current[i][-1]
        current[key] = ''

    return structure




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
