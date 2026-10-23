{
    'name': 'Kaplan Custom',
    'version': '18.0.1.0.0',
    'category': 'Customizations',
    'summary': 'Personalizaciones específicas para el cliente Kaplan',
    'author': 'Css Consultores 1010 C.A.',
    'website': 'https://www.Consultores1010.com',
    'license': 'AGPL-3',
    'depends': [
        'point_of_sale',
        'sale_management',
        'product',
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'kaplan_custom/static/src/product_catalog/**/*',
        ],
        'point_of_sale._assets_pos': [
            'kaplan_custom/static/src/pos/**/*',
        ],
    },
    'application': False,
    'installable': True,
    'auto_install': False,
}