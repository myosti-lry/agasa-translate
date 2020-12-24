import os
import re
import discord
import logging
from googletrans  import Translator
from google_trans_new import google_translator

channel_language_separator = '-_'
local_message_prefix = '//'
token = os.environ['DISCORD_BOT_TOKEN']
client = discord.Client()
logging.basicConfig(level=logging.INFO)


@client.event
async def on_ready():
    print('on_ready')
    return


@client.event
async def on_message(message):
    '''
    メッセージが送信された
    '''
    # チャンネル限定のメッセージにする
    if message.content.startswith(local_message_prefix):
        return
    # BOTからのメッセージ
    if message.author.bot:
        return
    # システムメッセージ
    if message.is_system():
        return
    # チャンネル内のメッセージをすべて消す
    if message.content == '/armageddon':
        await armageddon(message.channel)
        return
    # 返信メッセージ
    if message.reference is not None:
        await send_message(message, event_type='REPLY', reply_channel_id=message.reference.channel_id, reply_message_id=message.reference.message_id)
        return
    # 対象のチャンネルではない
    if channel_language_separator not in message.channel.name:
        return
    # 上記以外は通常の送信
    await send_message(message)
    return


@client.event
async def on_raw_message_edit(payload):
    '''
    メッセージの状態が変化したとき
    編集されたときのみ利用
    '''
    data = payload.data
    if data['edited_timestamp'] is not None:
        target_channel = client.get_channel(payload.channel_id)
        target_message = await target_channel.fetch_message(payload.message_id)
        if target_message.author.bot == False:
            await send_message(target_message, event_type='EDIT')
    return


@client.event
async def on_raw_message_delete(payload):
    '''
    メッセージが消去されたとき
    '''
    source_channel = client.get_channel(payload.channel_id)
    target_channels = get_target_channels(source_channel)
    for target_channel in target_channels:
        async for target_message in target_channel.history():
            if target_message.is_system() == True:
                continue
            if target_message.author.bot == False:
                target_message_id = target_message.id
            elif target_message.author.id == client.user.id:
                target_message_data = get_message_data(target_message)
                target_message_id = target_message_data['message_id']
            if target_message_id == payload.message_id:
                await target_message.delete()
    return


@client.event
async def on_guild_channel_pins_update(channel, last_pin):
    pinned_messages = await channel.pins()
    target_channels = get_target_channels(channel)
    if len(pinned_messages) >= 1:
        for target_channel in target_channels:
            async for target_message in target_channel.history():
                # メッセージがシステムメッセージ
                if target_message.is_system() == True:
                    continue
                # メッセージがBOTかつ自身が送信したメッセージではない
                if target_message.author.bot == True and target_message.author.id != client.user.id:
                    continue
                target_message_id = None
                if target_message.author.bot == False:
                    target_message_id = target_message.id
                else:
                    target_message_data = get_message_data(target_message)
                    target_message_id = target_message_data['message_id']
                for pinned_message in pinned_messages:
                    pinned_message_id = None
                    if pinned_message.author.bot == False:
                        pinned_message_id = pinned_message.id
                    else:
                        pinned_message_data = get_message_data(pinned_message)
                        pinned_message_id = pinned_message_data['message_id']
                    if pinned_message_id == target_message_id:
                        if target_message.pinned == False:
                            await target_message.pin()
                    else:
                        if target_message.pinned == True:
                            await target_message.unpin()
    # ピン留めの更新後にメッセージがない
    else:
        for target_channel in target_channels:
            async for target_message in target_channel.history():
                if target_message.pinned == True:
                    await target_message.unpin()
    return


async def send_message(message, **kwargs):
    message_url = create_message_url(message.channel.guild.id, message.channel.id, message.id)
    source_channel = message.channel
    source_channel_data = get_channel_data(source_channel.name)
    # 送信先のチャンネルを取得
    target_channels = get_target_channels(source_channel)
    for target_channel in target_channels:
        target_channel_data = get_channel_data(target_channel.name)
        formatted_content = None
        if len(target_channel_data) == 0 or message.content.startswith('.+://'):
            formatted_content = format_message(message_url, source_channel.mention, message.author.display_name, message.content)
        # elif target_channel_data['base_channel'] == source_channel_data['base_channel']:
        else:
            content = replace_string(message.content)
            content = google_trans_new_translate(content, source_channel_data['channel_language'], target_channel_data['channel_language'])
            content = replace_link(content, message.content)
            formatted_content = format_message(message_url, source_channel.mention, message.author.display_name, content)
        event_type = kwargs.get('event_type')
        if event_type is None:
            # 添付ファイルの有無をチェック
            attachment_count = len(message.attachments)
            if attachment_count == 0:
                await target_channel.send(content=formatted_content)
            else:
                files = []
                for attachment in message.attachments:
                    file = await attachment.to_file()
                    files.append(file)
                await target_channel.send(content=formatted_content, files=files)
            continue
        else:
            if event_type == 'EDIT':
                print('Edit')
                async for target_message in target_channel.history():
                    if target_message.is_system() == False:
                        if target_message.author.id == client.user.id:
                            message_data = get_message_data(target_message)
                            if message_data['message_id'] == message.id:
                                await target_message.edit(content=formatted_content)
                                break
                continue
            if event_type == 'REPLY':
                reply_channel_id = kwargs.get('reply_channel_id')
                reply_message_id = kwargs.get('reply_message_id')
                reply_channel = client.get_channel(reply_channel_id)
                reply_message = await reply_channel.fetch_message(reply_message_id)
                if (reply_message.author.bot == True) and (reply_message.author.id == client.user.id):
                    reply_message_data = get_message_data(reply_message)
                    reply_message_id = reply_message_data['message_id']
                async for target_message in target_channel.history():
                    if target_message.is_system() == False:
                        target_message_id = None
                        if target_message.author.bot == False:
                            target_message_id = target_message.id
                        elif target_message.author.id == client.user.id:
                            target_message_data = get_message_data(target_message)
                            target_message_id = target_message_data['message_id']
                        if reply_message_id == target_message_id:
                            reference = target_message.to_reference()
                            if target_message_id == reply_message_id:
                                attachment_count = len(message.attachments)
                                if attachment_count == 0:
                                    await target_channel.send(content=formatted_content, reference=reference)
                                else:
                                    files = []
                                    for attachment in message.attachments:
                                        file = await attachment.to_file()
                                        files.append(file)
                                    await target_channel.send(content=formatted_content, files=files, reference=reference)
                                continue
                continue
    return


def format_message(message_url, channel_name, author, content):
    header = '*' + message_url + '\nChannel: ' + channel_name + ' / ' + author + ':*\n>>> '
    return header + content


def get_target_channels(channel):
    result = []
    category = channel.category
    for tmp_channel in category.channels:
        if tmp_channel.id != channel.id:
            result.append(tmp_channel)
    return result


def get_channel_data(channel_name):
    result = {}
    index = channel_name.rfind(channel_language_separator)
    if index != -1:
        result['base_channel'] = channel_name[:index]
        index += len(channel_language_separator)
        result['channel_language'] = channel_name[index:]
    return result


def get_message_data(message):
    result = {}
    channel_name = ''
    # BOTが送信したメッセージではない
    if message.author.bot == False:
        result['message_id'] = message.id
        channel_name = message.channel.name
    # 自身が送信したメッセージ
    elif message.author.id == client.user.id:
        pattern = r'(?<=^\*https\://discordapp\.com/channels/)(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)(?=$)'
        c = re.compile(pattern, re.DOTALL | re.MULTILINE)
        match = c.search(message.content)
        if match is not None:
            result['guild_id'] = int(match.group('guild_id'))
            result['channel_id'] = int(match.group('channel_id'))
            result['message_id'] = int(match.group('message_id'))
            channel = client.get_channel(result['channel_id'])
            channel_name = channel.name
    else:
        return
    result['channel'] = channel_name
    if channel_language_separator in channel_name:
        channel_data = get_channel_data(channel_name)
        if len(channel_data) > 0:
            result['base_channel'] = channel_data['base_channel']
            result['channel_language'] = channel_data['channel_language']
    return result


async def armageddon(channel):
    await channel.purge()
    return


def googletrans_translate(content, src_lang, dest_lang):
    result = None
    translator = Translator()
    # 翻訳に成功するまでループ
    # https://github.com/ssut/py-googletrans/issues/234#issuecomment-722203541
    while True:
        try:
            # 日本語⇔韓国語の翻訳をするときは英語を経由
            if(src_lang == 'ko' and dest_lang == 'ja') or (src_lang == 'ja' and dest_lang == 'ko'):
                tmp = translator.translate(content, src=src_lang, dest='en')
                result = translator.translate(tmp.text, src='en', dest=dest_lang).text
            else:
                result = translator.translate(content, src=src_lang, dest=dest_lang).text
            break
        except  AttributeError:
            translator = Translator()
    return result


def google_trans_new_translate(content, source_language, target_language):
    result = ''
    translator = google_translator(url_suffix="co.jp")
    # google_trans_newは改行を捨てるようなので1行ごとに翻訳する
    lines = content.splitlines()
    for line in lines:
        while True:
            try:
                # 日本語⇔韓国語の翻訳をするときは英語を経由
                if(source_language == 'ko' and target_language == 'ja') or (source_language == 'ja' and target_language == 'ko'):
                    google_trans_new_translate = translator.translate(line, lang_src=source_language, lang_tgt='en')
                    result += translator.translate(google_trans_new_translate, lang_src='en', lang_tgt=target_language)
                else:
                    result += translator.translate(line, lang_src=source_language, lang_tgt=target_language)
                result += '\n'
                break
            except  AttributeError:
                translator = google_translator(url_suffix="co.jp")
    return result


def replace_link(content, original_content):
    '''
    翻訳後のメッセージからリンク文字列を置換する
    翻訳後のメッセージのみだと不完全なことが多いので、オリジナルのメッセージから出現順で置換する
    '''
    result = content
    # チャンネルリンク、ユーザ宛てメンション、ロール宛てメンションの置換
    pattern_list = [r'<#\s?\d+>', r'<@\s?!?\s?\d+>', r'<@\s?&?\s?\d+>']
    for pattern in pattern_list:
        c = re.compile(pattern, re.DOTALL | re.MULTILINE)
        target_iterator = c.finditer(content)
        original_iterator = c.finditer(original_content)
        if (target_iterator is not None) and (original_iterator is not None):
            for target_match in target_iterator:
                if target_match is not None:
                    original_match = next(original_iterator)
                    if original_match is not None:
                        result = result.replace(target_match.group(), original_match.group())
    # @everyone, @hereの置換
    replace_strings = {r'<@!+\s?\?+\s?901>':'@everyone', r'<@!+\s?\?+\s?902>':'@here'}
    for key, value in replace_strings.items():
        result = re.sub(key, value, result)
    return result


def create_message_url(server_id, channel_id, message_id):
    result = 'https://discordapp.com/channels/'
    result += str(server_id) + '/' + str(channel_id) + '/' + str(message_id)
    return result


def replace_string(content):
    '''
    メッセージ内の@everyone, @hereを一時的に置換する
    '''
    result = content
    replace_strings = {'@everyone':'<@!?901>', '@here':'<@!?902>'}
    for key, value in replace_strings.items():
        result = re.sub(key, value, result)
    return result


def azure_translate():
    # 一通りの機能をつくり終えてから乗り換える
    # https://azure.microsoft.com/ja-jp/services/cognitive-services/translator/
    return


client.run(token)
