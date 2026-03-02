import urllib
import urllib.parse

from click import group
from support import SupportFile

from .setup import *


class ModelHDHomerunChannel(ModelBase):
    P = P
    __tablename__ = f'{P.package_name}_channel'
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = P.package_name

    id = db.Column(db.Integer, primary_key=True)
    json = db.Column(db.JSON)
    created_time = db.Column(db.DateTime)

    ch_type = db.Column(db.String) # hdhomerun, custom

    # scan 정보
    scan_vid = db.Column(db.String)
    scan_name = db.Column(db.String)
    scan_frequency = db.Column(db.String) 
    scan_program = db.Column(db.String)
    scan_ch = db.Column(db.String)

    # m3u & epg
    for_epg_name = db.Column(db.String)
    group_name = db.Column(db.String)

    use_vid = db.Column(db.Boolean) 
    use = db.Column(db.Boolean)
    ch_number = db.Column(db.Integer)
    # custom url 
    url = db.Column(db.String) 
    url_trans = db.Column(db.String) 
    match_epg_name = db.Column(db.String)
    current_program = db.Column(db.String) 


    def __init__(self):
        # for ui
        # match_epg_name
        self.match_epg_name = ''
        self.created_time = datetime.now()
        self.ch_number = 0
        self.group_name = ''
        self.url = ''
        self.url_trans = ''


    @classmethod
    def channel_list(cls, only_use=False, as_dict=False):
        try:
            query = db.session.query(cls)
            if only_use:
                query = query.filter_by(use=True)
            query = query.order_by(cls.ch_number)
            query = query.order_by(cls.id)
            if as_dict:
                tmp = query.all()
                return [x.as_dict() for x in tmp]
            else:
                return  query.all()
            #return [item.as_dict() for item in lists]
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @classmethod
    def load_data(self):
        try:
            mod_name = 'base'
            data = SupportFile.read_file(P.ModelSetting.get(f"{mod_name}_data_filename"))
            ret = {}
            if data == None:
                return
            with F.app.app_context():
                data = data.splitlines()
                deviceid = data[0].strip()
                tmp = deviceid.find('192')
                deviceid = deviceid[tmp:]
                
                P.ModelSetting.set(f'{mod_name}_deviceid', deviceid)
                logger.debug('deviceid:%s', deviceid)
                logger.debug('deviceid:%s', len(deviceid))

                ModelHDHomerunChannel.query.delete()
                channel_list = []
                for item in data[1:]:
                    if item.strip() == '':
                        continue
                    m = ModelHDHomerunChannel()
                    m.init_data(item)
                    db.session.add(m)
                    m.set_url(deviceid, P.ModelSetting.get_bool(f'{mod_name}_attach_mpeg_ext'), P.ModelSetting.get(f'{mod_name}_tuner_name'))
                    channel_list.append(m)
                no = 1
                for m in channel_list:
                    if m.use:
                        m.ch_number = no
                        no += 1
                for m in channel_list:
                    if not m.use:
                        m.ch_number = no
                        no += 1
                
                db.session.commit()
                return ModelHDHomerunChannel.channel_list(as_dict=True)
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret['ret'] = 'exception'
            ret['log'] = str(e)
        return ret


    def init_data(self, data):
        self.ch_type = 'hdhomerun'
        self.use_vid = False
        tmp = data.split('|')
        self.scan_vid = tmp[0].strip()
        #self.ch_number = tmp[0]
        self.scan_name = tmp[1].strip()
        self.for_epg_name = tmp[1].strip()
        self.scan_frequency = tmp[2].strip()
        self.scan_program = tmp[3].strip()
        self.scan_ch = tmp[4].strip()
        self.scan_modulation = tmp[5].strip()
        self.use = True
        if self.scan_vid == '0' or self.scan_name == '':
            self.use = False
        
        tmp = ['encrypted', 'no data', '데이터 방송', 'control']
        for t in tmp:
            if self.scan_name.find(t) != -1:
                self.use = False
                break
        #if self.use:
        #    self.match_epg()


    def match_epg(self):
        try:
            from epg.model_channel import ModelEpgChannel
            ret = ModelEpgChannel.get_by_prefer(self.for_epg_name)
            if ret is not None:
                self.match_epg_name = ret.name
                self.group_name = ret.category
                logger.debug(f"Find: {self.for_epg_name} epg:{ret.name} {ret.category}")
                self.save()
                return True
            logger.debug(f"NOT Find: {self.for_epg_name}")
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False


    def set_url(self, deviceid, attach_mpeg_ext, tuner_name):
        if self.use_vid:
            self.url = 'http://%s:5004/%s/v%s' % (deviceid, tuner_name, self.scan_vid)
        else:
            self.url = 'http://%s:5004/%s/ch%s-%s' % (deviceid, tuner_name, self.scan_frequency, self.scan_program)
            if attach_mpeg_ext:
                self.url += '.mpeg'
        self.url_trans = self.get_trans()
        
    
    def get_trans(self):
        url = '/hdhomerun/api/trans.ts?source=' + urllib.parse.quote_plus(self.url)
        return ToolUtil.make_apikey_url(url)


    @classmethod
    def get_m3u(cls, trans=False, force=False):
        try:
            if trans:
                m3ufilepath = os.path.join(os.path.dirname(__file__), 'files', 'hdhomerun_trans.m3u')
            else:
                m3ufilepath = os.path.join(os.path.dirname(__file__), 'files', 'hdhomerun.m3u')
            
            if force == True or os.path.exists(m3ufilepath) == False:
                # 1. tvg-url 항목에 사용자님의 myepg 주소를 강제로 삽입합니다.
                apikey = F.SystemModelSetting.get('apikey')
                ddns = F.SystemModelSetting.get('ddns')
                my_epg_url = f"{ddns}/myepg/api/epgall?apikey={apikey}"
                
                # M3U 헤더에 x-tvg-url 추가
                m3u = []
                m3u.append(f'#EXTM3U x-tvg-url="{my_epg_url}"')
                
                # 채널 정보 포맷 (아이콘은 myepg 연동을 위해 로직 수정 필요)
                M3U_FORMAT = '#EXTINF:-1 tvg-id=\"%s\" tvg-name=\"%s\" tvg-chno=\"%s\" tvg-logo=\"%s\" group-title=\"%s\",%s'

                with F.app.app_context():
                    data = cls.channel_list(only_use=True)
                
                for c in data:
                    ins_icon = ""
                    # 2. 아이콘 정보를 epg 대신 myepg 모델에서 가져오거나, 
                    # 매칭된 이름 기반의 기본 아이콘 경로를 설정합니다.
                    if c.match_epg_name != '':
                        try:
                            # 기존 epg 플러그인 참조 대신, 채널명 기반 아이콘 경로가 있다면 그대로 사용
                            from epg.model_channel import ModelEpgChannel
                            ins = ModelEpgChannel.get_by_name(c.match_epg_name)
                            if ins:
                                ins_icon = ins.icon
                        except:
                            ins_icon = ""
                    
                    url = c.url
                    if trans:
                        url = c.url_trans
                    
                    # M3U 라인 생성
                    m3u.append(M3U_FORMAT % (c.id, c.scan_name, c.ch_number, ins_icon, c.group_name, c.scan_name))
                    m3u.append(url)
                
                SupportFile.write_file(m3ufilepath, '\n'.join(m3u))
            
            return SupportFile.read_file((m3ufilepath))
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return ""
        
    @classmethod
    def group_sort(cls):
        try:
            items = cls.channel_list()
            orders = [x.strip() for x in P.ModelSetting.get('base_group_sort').split(',')]
            orders.append('except')
            data = {}
            for o in orders:
                data[o] = []

            for channel in items:
                if channel.group_name in data:
                    data[channel.group_name].append(channel)
                else:
                    data['except'].append(channel)

            ret = []
            for o in orders:
                for t in data[o]:
                    ret.append(t.as_dict())

            #return [item.as_dict() for item in ret]
            return ret
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
    
    @classmethod
    def find_current_program(cls):
        try:
            with F.app.app_context():
                items = cls.channel_list()
                from epg.model_program import ModelEpgProgram
                for ch in items:
                    if ch.use == False or ch.match_epg_name == '':
                        continue
                    title = ModelEpgProgram.get_program(ch.match_epg_name)
                    if title != None:
                        ch.current_program = title
                        F.db.session.add(ch)
                F.db.session.commit()

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            
            
