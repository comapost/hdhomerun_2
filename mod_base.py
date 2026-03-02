import subprocess
import urllib

from flask import Response, stream_with_context
from support import SupportFile, SupportSubprocess

from .setup import *


class ModuleBase(PluginModuleBase):
    def __init__(self, P):
        super(ModuleBase, self).__init__(P, name='base', first_menu='channel', scheduler_desc="현재 방송 찾기")
        self.db_default = {
            f'{self.name}_db_version' : '1',
            f'{self.name}_data_filename' : os.path.join(os.path.dirname(__file__), 'bin', 'hdhomerun.txt'),
            f'{self.name}_group_sort' : 'TOP, 지상파, 종합편성, 연예/오락, 뉴스/경제, 드라마, 여성/패션, 스포츠, 영화, 음악, 만화, 어린이, 교양, 다큐, 교육, 레저, 공공, 종교, 홈쇼핑, 해외위성, 라디오, 기타',
            f'{self.name}_deviceid' : '',
            f'{self.name}_trans_option' : 'ffmpeg -loglevel quiet -i {URL} -vcodec libx264 -vf scale=1080:720 -c:a aac -b:a 64k -f mpegts -tune zerolatency pipe:stdout',
            f'{self.name}_attach_mpeg_ext' : 'False',
            f'{self.name}_tuner_name' : 'auto',
            f'{self.name}_program_cmd' : 'C:\\Program Files\\DAUM\\PotPlayer\\PotPlayer64.exe',
            #f'{self.name}_program_trans' : 'False',
            f'{self.name}_interval' : '5',
            f'{self.name}_auto_start' : 'True',
            f'{self.name}_user_link' : 'nplayer-{TRANS}',

        }
        self.process_list = []


    def scheduler_function(self):
        ModelHDHomerunChannel.get_m3u(force=True)
        ModelHDHomerunChannel.get_m3u(trans=True, force=True)
        ModelHDHomerunChannel.find_current_program()
    

    def process_menu(self, page, req):
        try:
            arg = P.ModelSetting.to_dict()
            arg['ddns'] = F.SystemModelSetting.get('ddns')
            arg['apikey'] = F.SystemModelSetting.get('apikey')
            if page == 'setting':
                arg['is_include'] = F.scheduler.is_include(self.get_scheduler_name())
                arg['is_running'] = F.scheduler.is_running(self.get_scheduler_name())
                arg['m3u'] = ToolUtil.make_apikey_url(f'/{P.package_name}/api/m3u')
                arg['m3u_trans'] = ToolUtil.make_apikey_url(f'/{P.package_name}/api/m3u_trans')
                arg['xmltv'] = ToolUtil.make_apikey_url(f'/epg/api/xml/{P.package_name}')
                arg['proxy'] = f"{F.SystemModelSetting.get('ddns')}/{P.package_name}/proxy"
            elif page == 'video':
                arg['play_title'] = request.form['play_title']
                arg['play_source_src'] = request.form['play_source_src']
                arg['play_source_type'] = request.form['play_source_type']
                # 패키지명을 "hdhomerun_2"로 직접 박아버립니다.
                return render_template(f'hdhomerun_2_{self.name}_{page}.html', arg=arg)
        except Exception as e:
            logger.error(f"Exception:{str(e)}")
            logger.error(traceback.format_exc())
            return render_template('sample.html', title=f"PluginModuleBase-process_menu{self.P.package_name}/{self.name}/{page}")

        
    def process_command(self, command, arg1, arg2, arg3, req):
        try:
            ret = {'ret':'success'}
            if command == 'read_data':
                ret['title'] = arg1
                ret['modal'] = SupportFile.read_file(arg1)
            elif command == 'load_data':
                ret['data'] = ModelHDHomerunChannel.load_data()
                ret['msg'] = "로딩하였습니다."
                if ret['data'] == None:
                    ret['ret'] = 'warning'
                    ret['msg'] = "로딩 실패"
            elif command == 'load_db':
                ret = {}
                ret['setting'] = P.ModelSetting.to_dict()
                ret['data'] = ModelHDHomerunChannel.channel_list(as_dict=True)
            elif command == 'epg_channel_list':
                from epg.model_channel import ModelEpgChannel
                epg_channel_list = ModelEpgChannel.get_list()
                modal = []
                for ch in epg_channel_list:
                    _ = ch.aka.replace('\n', ' | ')
                    modal.append(f"[{ch.category:7}] - {_}")
                ret['modal'] = '\n'.join(modal)
                ret['title'] = "EPG 채널 목록"
            elif command == 'auto_epg_match':
                self.auto_epg_match()
            elif command == 'match_for_epg_name':
                channel_id = arg1
                item = ModelHDHomerunChannel.get_by_id((channel_id))
                item.for_epg_name = arg2
                if item.match_epg():
                    ret['ch'] = item.as_dict()
                    ret['msg'] = '매치 성공'
                else:
                    ret['ret'] = 'warning'
                    ret['msg'] = '매치 실패'
            elif command == 'm3u_make':
                m3u = ModelHDHomerunChannel.get_m3u(force=True)
                count = int((len(m3u.splitlines()) - 1)/2)
                ModelHDHomerunChannel.get_m3u(trans=True, force=True)
                ret['msg'] = f"{count}개 채널 생성"
            elif command == 'delete':
                if ModelHDHomerunChannel.delete_by_id(arg1):
                    ret['data'] = ModelHDHomerunChannel.channel_list(only_use=False, as_dict=True)
                    ret['msg'] = '삭제하였습니다.'
                else:
                    ret['msg'] = '삭제 실패'
            
            elif command == 'save':
                if ModelHDHomerunChannel.all_save(arg1):
                    ret['data'] = ModelHDHomerunChannel.channel_list(only_use=False, as_dict=True)
                    ret['msg'] = '저장하였습니다.'
                else:
                    ret['msg'] = '저장 실패'
            elif command == 'group_sort':
                ret['data'] = ModelHDHomerunChannel.group_sort()
            elif command == 'program':
                ch = ModelHDHomerunChannel.get_by_id(arg1)
                program = P.ModelSetting.get('base_program_cmd')
                tmppath = os.path.join(F.config['path_data'], 'tmp', f"{ch.scan_name}.m3u")
                text = f'#EXTM3U\n#EXTINF:-1 tvg-id=\"{ch.id}\" tvg-name=\"{ch.scan_name}\" tvg-chno=\"{ch.ch_number}\" tvg-logo=\"\" group-title=\"{ch.group_name}\",{ch.scan_name}\n{ch.url}'
                SupportFile.write_file(tmppath, text)
                cmd = [program, tmppath]
                cmd = SupportSubprocess.command_for_windows(cmd)
                process = subprocess.Popen(cmd)
                ret['msg'] = '실행하였습니다.'
            elif command == 'program_run':
                if arg1 == 'local':
                    cmd = [P.ModelSetting.get('base_program_cmd')]
                elif arg1 == 'scan':
                    bin_path = os.path.join(os.path.dirname(__file__), 'bin')
                    cmd = [os.path.join(bin_path, 'run_scan.bat'), bin_path]
                elif arg1 == 'config':
                    cmd = [os.path.join(os.path.dirname(__file__), 'bin', 'hdhomerun_config_gui.exe')]
                cmd = SupportSubprocess.command_for_windows(cmd)
                process = subprocess.Popen(cmd)
                ret['msg'] = '실행하였습니다.'

            return jsonify(ret)
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())
            return jsonify({'ret':'danger', 'msg':str(e)})
    
        
    def process_api(self, sub, req):
        if sub == 'm3u':
            return ModelHDHomerunChannel.get_m3u()
        elif sub == 'm3u_trans':
            return ModelHDHomerunChannel.get_m3u(trans=True)
        elif sub in ['trans.ts', 'trans.m3u8']:
            return self.trans_ts()


    def trans_ts(self):
        def generate():
            ffmpeg_command = P.ModelSetting.get('base_trans_option').strip()
            source = urllib.parse.unquote(request.args.get('source'))
            logger.debug(source)

            startTime = time.time()
            buffer = []
            sentBurst = False
           
            ffmpeg_command =  ffmpeg_command.replace('{URL}', source).split(' ')
            
            ffmpeg_command = SupportSubprocess.command_for_windows(ffmpeg_command)
            logger.debug(f'command : {ffmpeg_command}')
            with subprocess.Popen(ffmpeg_command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, bufsize = -1) as process:
                while True:
                    line = process.stdout.read(1024)
                    #print(line)
                    buffer.append(line)
                    if sentBurst is False and time.time() > startTime + 1 and len(buffer) > 0:
                        sentBurst = True
                        for i in range(0, len(buffer) - 2):
                            yield buffer.pop(0)
                    elif time.time() > startTime + 1 and len(buffer) > 0:
                        yield buffer.pop(0)
                    process.poll()
                    if isinstance(process.returncode, int):
                        if process.returncode > 0:
                            logger.debug('FFmpeg Error :%s', process.returncode)
                        else:
                            logger.debug('FFmpeg normal finish..')  
                        break
            #del process_list[process]
        return Response(stream_with_context(generate()), mimetype = "video/MP2T")  


    ################################################
    def auto_epg_match(self):
        import unicodedata
        try:
            def width(s):
                name_length = 0
                for char in s:
                    if ord('가') <= ord(char) <= ord('힣'):  # 한글 문자인 경우
                        name_length += 2
                    #elif ord('0') <= ord(char) <= ord('9'):
                    #    pass
                    else:
                        name_length += 1
                return name_length

            def add_text(msg):
                F.socketio.emit("command_modal_add_text", msg, namespace='/framework')
            
            F.socketio.emit("command_modal_clear", None, namespace='/framework')
            F.socketio.emit("command_modal_show", 'EPG 매칭', namespace='/framework')
            add_text('EPG 매칭을 시작합니다.\n\n')

            ch_list = ModelHDHomerunChannel.channel_list()

            add_text(f"총 사용 채널: {len(ch_list)}\n")
            add_text(f"=================================================================================\n")
            cols = ['IDX', '전체', '채널', 'EPG검색']
            add_text(f"{cols[0]:>3} / {cols[1]:<3}  {cols[2]}\t{cols[3]:12}\n")
            add_text(f"=================================================================================\n")
            def func():
                for idx, ch in enumerate(ch_list):
                    w = ["\t", "\t", "\t"]
                    w1 = width(ch.scan_name)
                    w2 = width(ch.for_epg_name)
                    #print([w1, w2])
                    if w1 <= 3:
                        w[0] = '\t\t'
                    if w1 + w2 <= 16:
                        w[1] = '\t\t'
                    add_text(f"{str((idx+1)).zfill(3):>3} / {str(len(ch_list)).zfill(3):>3}   {ch.scan_name}{w[0]}{ch.for_epg_name}{w[1]}")
                    ret = True
                    if ch.match_epg_name == '' or ch.group_name == '':
                        ret = ch.match_epg()
                        time.sleep(0.1)
                    if ret:
                        w3 = width(ch.match_epg_name)
                        if w1+w2+w3 <= 22:
                            w[2] = '\t\t'
                        add_text(f"{ch.match_epg_name}{w[2]}{ch.group_name}\n")
                    else:
                        add_text(f"---- 매칭 실패\n")
                    
            thread = threading.Thread(target=func, args=())
            thread.setDaemon(True)
            thread.start()
            return ''
        except Exception as e: 
            add_text(f"에러발생\n")
            add_text(f"Exception:{str(e)}\n")
            add_text(str(traceback.format_exc()))
