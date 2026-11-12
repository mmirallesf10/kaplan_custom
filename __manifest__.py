{
    'name': 'Kaplan Custom',
    'version': '18.0.1.1.0',
    'category': 'Customizations',
    'summary': 'Personalizaciones específicas para el cliente Kaplan',
    'author': 'Css Consultores 1010 C.A.',
    'website': 'https://www.Consultores1010.com',
    'license': 'AGPL-3',
    'depends': [
        'account',       
        'product',
        'sale',           
        'sale_management',
        'point_of_sale',
        'printax_pos_18',
        'save_z_report',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/pos_session_views.xml',
    ],
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