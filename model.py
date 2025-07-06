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
            #if os.path.exists(m3ufilepath) and force == False:
            #    return SupportFile.read_file((m3ufilepath))
            if force == True or os.path.exists(m3ufilepath) == False:
                M3U_FORMAT = '#EXTINF:-1 tvg-id=\"%s\" tvg-name=\"%s\" tvg-chno=\"%s\" tvg-logo=\"%s\" group-title=\"%s\",%s'

                m3u = []
                m3u.append('#EXTM3U')
                with F.app.app_context():
                    data = cls.channel_list(only_use=True)
                ddns = F.SystemModelSetting.get('ddns')
                for c in data:
                    ins = None
                    if c.match_epg_name !='':
                        try:
                            from epg.model_channel import ModelEpgChannel
                            ins = ModelEpgChannel.get_by_name(c.match_epg_name)
                        except:
                            ins = None
                    url = c.url
                    if trans:
                        url = c.url_trans
                    m3u.append(M3U_FORMAT % (c.id, c.scan_name, c.ch_number, (ins.icon if ins is not None else ""), c.group_name, c.scan_name))
                    m3u.append(url)
                SupportFile.write_file(m3ufilepath, '\n'.join(m3u))
            return SupportFile.read_file((m3ufilepath))
            
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return '\n'.join(m3u)
    

    @classmethod
    def all_save(cls, raw):
        try:
            ret = {}
            count = 0
            deviceid = P.ModelSetting.get('base_deviceid')
            attach_ext = P.ModelSetting.get_bool('base_attach_mpeg_ext')
            tuner_name = P.ModelSetting.get('base_tuner_name')

            params = raw.split('&')
            params = [urllib.parse.unquote(x) for x in params]
            data = {}
            for param in params:
                #logger.error(param)
                tmp, value = param.split('=')
                key, id = tmp.split('|')
                if data.get(id) == None:
                    data[id] = {}
                data[id][key] = value

            for key, value in data.items():
                mc = db.session.query(cls).filter(cls.id == key).with_for_update().first()
                if mc is not None:
                    mc.use = True if value['use_checkbox'] == 'True' else False
                    mc.use_vid = True if value['use_vid_checkbox'] == 'True' else False
                    mc.set_url(deviceid, attach_ext, tuner_name)
                    mc.ch_number = int(value['ch_number'])
                    mc.scan_name = value['scan_name']
                    mc.for_epg_name = value['for_epg_name']
                    mc.group_name = value['group_name']
            db.session.commit()
            return True
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False
        
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
            
            
