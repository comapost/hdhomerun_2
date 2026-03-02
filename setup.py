from plugin import *

setting = {
    'filepath' : __file__,
    'use_db': True,
    'use_default_setting': True,
    'home_module': None,
    'menu': {
        'uri': __package__,
        'name': 'HDHomerun_2',
        'list': [
            {
                'uri': 'base/setting',
                'name': '설정',
            },
            {
                'uri': 'base/channel',
                'name': '채널',
            },
            {
                'uri': 'base/current',
                'name': '현재 방송',
            },
            {
                'uri': 'manual',
                'name': '매뉴얼',
                'list': [
                    {'uri':'README.md', 'name':'ChangeLog'},
                    {'uri':'files/manual.md', 'name':'매뉴얼'}
                ]
            },
            {
                'uri': 'log',
                'name': '로그',
            },
        ]
    },
    'default_route': 'normal',
}

from plugin import *

P = create_plugin_instance(setting)

try:
    from .model import ModelHDHomerunChannel
    from .route import foo
    pass
    from .mod_base import ModuleBase
    P.set_module_list([ModuleBase])
except Exception as e:
    P.logger.error(f'Exception:{str(e)}')
    P.logger.error(traceback.format_exc())

logger = P.logger
