from django.template import Template, Context

def render_email_template(template_path, context):
    with open(template_path, 'r', encoding='utf-8') as file:
        template_content = file.read()
    template = Template(template_content)
    context = Context(context)
    return template.render(context)
