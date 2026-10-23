{
    'name': 'Kaplan Custom',
    'version': '18.0.1.0.0',
    'category': 'Customizations',
    'summary': 'Personalizaciones específicas para el cliente Kaplan',
    'description': """
Personalizaciones Kaplan:
    - Mostrar VAT en selector de contactos del TPV y debajo del nombre del cliente seleccionado.
    - Mostrar precio total (con impuestos) en la vista Kanban del catálogo de ventas.
    """,
    'author': 'Css Consultores 1010 C.A.',
    'website': 'https://www.Consultores1010.com',
    'license': 'AGPL-3',
    'depends': [
        'point_of_sale',
        'sale_management',
        'product',
    ],
    'data': [
        'views/product_template_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'kaplan_custom/static/src/**/*.js',
            'kaplan_custom/static/src/**/*.xml',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}