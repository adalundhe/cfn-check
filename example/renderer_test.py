import yaml
from cfn_check.rendering import Renderer
from cfn_check.cli.utils.files import open_template, Loader, create_tag
def test():

    renderer = Renderer()
    data = {}

    tags = [
        'Ref',
        'Sub',
        'Join',
        'Select',
        'Split',
        'GetAtt',
        'GetAZs',
        'ImportValue',
        'Equals',
        'If',
        'Not',
        'And',
        'Or',
        'Condition',
        'FindInMap',
    ]

    for tag in tags:
        new_tag = create_tag(tag)
        Loader.add_constructor(f'!{tag}', new_tag)

    _, template = open_template('template.yaml')

    data = renderer.render(template)


    with open('rendered.yaml', 'w') as yml:
        yaml.safe_dump(data, yml)




test()