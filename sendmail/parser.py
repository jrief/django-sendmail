import re
from django import template
from django.template import loader, TemplateSyntaxError, TemplateDoesNotExist
from django.template.base import Node, NodeList, VariableNode
from django.template.context import Context
from django.template.defaulttags import ForNode
from django.template.loader import get_template
from django.template.loader_tags import ExtendsNode, IncludeNode

from sendmail.django_compressor import handle_extendsnode


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


class SendmailParser:

    def __init__(self, charset):
        self.charset = charset

    def parse(self, template_name):
        try:
            return get_template(template_name).template
        except template.TemplateSyntaxError as e:
            raise TemplateSyntaxError(str(e))
        except template.TemplateDoesNotExist as e:
            raise TemplateDoesNotExist(str(e))

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
                    loopvar = node.loopvars[0]
                    layer = (seq, loopvar)
                    iter_list = [*iter_list, layer] if iter_list else [layer]
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

def merge_nested_dicts(dict1, dict2):
    merged = dict1.copy()  # Start with a copy of the first dictionary
    for key, value in dict2.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # If the key exists in both and both values are dictionaries, merge them recursively
            merged[key] = merge_nested_dicts(merged[key], value)
        else:
            # Otherwise, overwrite or add the key-value pair
            merged[key] = value
    return merged


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
        loc = getattr(node, 'loc', [])  # Tuple of format (sequence, loopvar)
        key = node.filter_expression.var.var

        if key.startswith('recipient'):
            continue

        parts = key.split('.')

        part_found = False
        layers = []

        # Find to what list variable belong
        for seq, var in loc:
            if not part_found:
                if var == parts[0]:
                    part_found = True
                layers.append(seq)

        # If not found -> It is in global scope
        layers = layers if part_found else []

        # If part of loop -> first part is a sequence name
        m = 0 if not layers else 1
        n = len(parts) - m

        # Wrappers are objects exclude lists where element is
        wrappers = parts[-n:-1]
        key = parts[-1]
        current = structure
        for i in layers:
            if i not in current:
                current[i] = []
            if not current[i]:
                current[i].append({})
            current = current[i][-1]

        if wrappers:
            nested_dict = {key: ""}
            for wrapper in reversed(wrappers):
                nested_dict = {wrapper: nested_dict}

            if not current or not isinstance(current, dict):
                current.update(nested_dict)
            else:
                current.update(merge_nested_dicts(current, nested_dict))
        else:
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

    for content in template.contents.filter(used_template_file=template.template_file):
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
