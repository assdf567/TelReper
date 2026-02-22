import asyncio
import os
import re
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors.rpcerrorlist import PhoneNumberInvalidError
from telethon import functions
from colorama import Fore
import threading
import time

class TelegramReporter:
    def __init__(self, config_manager):
        self.config = config_manager
        self.api_id = self.config.get('24597015')
        self.api_hash = self.config.get('1b1aefc2645a9275a3069ca6b7b7f7a2')
        self.sessions_dir = 'sessions'
        self.ensure_sessions_dir()
    
    def ensure_sessions_dir(self):
        """確保sessions目錄存在"""
        if not os.path.exists(self.sessions_dir):
            os.makedirs(self.sessions_dir)
    
    def get_session_files(self):
        """獲取所有session文件"""
        if not os.path.exists(self.sessions_dir):
            return []
        
        session_files = []
        for file in os.listdir(self.sessions_dir):
            if file.endswith('.session'):
                session_files.append(file)
        session_files.sort()
        return session_files
    
    def add_account(self, phone_number):
        """添加新帳戶"""
        session_files = self.get_session_files()
        
        if session_files:
            # 獲取最後一個帳戶編號
            last_account_match = re.search(r'Ac(\d+)\.session', session_files[-1])
            if last_account_match:
                next_account_number = int(last_account_match.group(1)) + 1
            else:
                next_account_number = 1
        else:
            next_account_number = 1
        
        session_name = f'Ac{next_account_number}'
        client = TelegramClient(os.path.join(self.sessions_dir, session_name), self.api_id, self.api_hash)
        
        try:
            client.start(phone_number)
            return True, f"帳戶 {session_name} 添加成功！"
        except PhoneNumberInvalidError:
            return False, "電話號碼無效！"
        except Exception as e:
            return False, f"添加帳戶時發生錯誤: {str(e)}"
    
    async def report_channel(self, client, target_channel, report_count, report_mode, progress_callback=None):
        """報告頻道"""
        try:
            async with client:
                current_user = await client.get_entity('self')
                current_user_name = current_user.first_name
                
                # 獲取最近的消息
                try:
                    recent_messages = await client.get_messages(target_channel, limit=3)
                    message_ids = [message.id for message in recent_messages]
                except ValueError:
                    return False, f"頻道鏈接無效: {target_channel}"
                
                # 檢查是否已加入頻道
                channel_exists = False
                async for dialog in client.iter_dialogs():
                    if dialog.is_channel and dialog.entity.username == target_channel:
                        channel_exists = True
                        break
                
                # 如果未加入且設置為自動加入
                if not channel_exists and self.config.get('auto_join_channel', True):
                    await client(JoinChannelRequest(target_channel))
                    await asyncio.sleep(1)
                
                # 開始報告
                success_count = 0
                for report_iteration in range(report_count):
                    try:
                        report_message = f"This channel sends offensive content - {report_mode}"
                        
                        report_result = await client(functions.messages.ReportRequest(
                            peer=target_channel,
                            id=message_ids,
                            option=b'',
                            message=report_message
                        ))
                        
                        if report_result:
                            success_count += 1
                            if progress_callback:
                                progress_callback(
                                    f"✅ 報告成功 - 帳戶: {current_user_name}, 計數: {report_iteration + 1}/{report_count}",
                                    report_iteration + 1,
                                    report_count
                                )
                        else:
                            if progress_callback:
                                progress_callback(
                                    f"❌ 報告失敗 - 帳戶: {current_user_name}, 計數: {report_iteration + 1}/{report_count}",
                                    report_iteration + 1,
                                    report_count
                                )
                        
                        # 延遲
                        delay = self.config.get('delay_between_reports', 1)
                        if delay > 0:
                            await asyncio.sleep(delay)
                    
                    except Exception as e:
                        if progress_callback:
                            progress_callback(
                                f"❌ 報告錯誤 - 帳戶: {current_user_name}, 錯誤: {str(e)}",
                                report_iteration + 1,
                                report_count
                            )
                
                return True, f"完成報告 - 成功: {success_count}/{report_count}"
        
        except Exception as e:
            return False, f"報告過程中發生錯誤: {str(e)}"
    
    async def run_reports(self, target_channel, report_count, report_mode, progress_callback=None):
        """運行所有帳戶的報告"""
        session_files = self.get_session_files()
        
        if not session_files:
            return False, "請先添加帳戶！"
        
        # 創建所有客戶端
        clients = []
        for session_file in session_files:
            session_name = session_file.replace('.session', '')
            client = TelegramClient(os.path.join(self.sessions_dir, session_name), self.api_id, self.api_hash)
            clients.append(client)
        
        # 並行執行報告
        tasks = []
        for client in clients:
            task = self.report_channel(client, target_channel, report_count, report_mode, progress_callback)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 統計結果
        success_count = 0
        total_accounts = len(clients)
        
        for result in results:
            if isinstance(result, tuple) and result[0]:
                success_count += 1
        
        return True, f"報告完成！成功帳戶: {success_count}/{total_accounts}"
    
    def run_reports_sync(self, target_channel, report_count, report_mode, progress_callback=None):
        """同步版本的報告運行器"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.run_reports(target_channel, report_count, report_mode, progress_callback)
            )
            return result
        finally:

            loop.close() 
