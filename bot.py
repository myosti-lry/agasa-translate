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
    logging.info('on_ready')
    return


@client.event
async def on_message(message):
    '''
    メッセージが送信された
    '''
    logging.info('on_message')
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
    メッセージの状態が変更されたとき(編集・ピン留め)
    '''
    logging.info('on_raw_message_edit')
    data = payload.data
    channel = client.get_channel(payload.channel_id)
    source_message = await channel.fetch_message(payload.message_id)
    source_message_data = get_message_data(source_message)
    if data['edited_timestamp'] is not None:
        if source_message.author.bot == False:
            await send_message(source_message, event_type='EDIT', edited_timestamp=data['edited_timestamp'])
    # ピン留め
    for target_channel in get_target_channels(channel):
        async for target_message in target_channel.history():
            if target_message.is_system() == True:
                continue
            target_message_data = get_message_data(target_message)
            if target_message_data['message_id'] == source_message_data['message_id']:
                # ピン留めがすでにあったとき
                if (source_message.pinned == False) and (target_message.pinned == True):
                    await target_message.unpin()
                    break
                elif (source_message.pinned == True) and (target_message.pinned == False):
                    await target_message.pin()
                    break
    return


async def update_pinned_messages():
    '''
    '''
    logginginfo('')
    return


async def remove_pinned_messages(channel):
    '''
    '''
    logginginfo('')
    target_channels = get_target_channels(channel)
     
    return


@client.event
async def on_raw_message_delete(payload):
    '''
    メッセージが消去された
    
    '''
    logging.info('on_raw_message_delete')
    source_channel = client.get_channel(payload.channel_id)
    target_channels = get_target_channels(source_channel)
    # 消去されたメッセージがユーザかBOTか判別できないので全てチェックする
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


async def send_message(message, **kwargs):
    '''
    メッセージを送信
    '''
    logging.info('send_message')
    is_url_start = re.search(r'^[a-zA-Z]*://', message.content, re.DOTALL)
    message_url = create_message_url(message)
    channel_mention = message.channel.mention
    author = message.author.display_name
    content_lines = replace_mention(message.content).splitlines()
    source_channel_data = get_channel_data(message.channel.name)
    # 送信先のチャンネルを取得
    target_channels = get_target_channels(message.channel)
    for target_channel in target_channels:
        target_channel_data = get_channel_data(target_channel.name)
        formatted_content = ''
        # 送信先のチャンネル名に言語コードが含まれないか、ユーザが送信したメッセージがURLと思われる文字列から始まる
        if (len(target_channel_data) == 0) or (is_url_start is not None):
            formatted_content = format_content(message_url, channel_mention, author, message.content)
        else:
            tmp_content = google_trans_new_translate(content_lines, source_channel_data['channel_language'], target_channel_data['channel_language'])
            tmp_content = replace_links(tmp_content, message.content)
            formatted_content = format_content(message_url, channel_mention, author, tmp_content)
        event_type = kwargs.get('event_type')
        # 通常のメッセージ送信
        if event_type is None:
            # 添付ファイルの有無を確認
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
            # 編集時
            if event_type == 'EDIT':
                logging.info('EDIT')
                async for target_message in target_channel.history():
                    if target_message.is_system() == False:
                        if target_message.author.id == client.user.id:
                            message_data = get_message_data(target_message)
                            if message_data['message_id'] == message.id:
                                await target_message.edit(content=formatted_content)
                                break
                continue
            # メッセージへ返信
            if event_type == 'REPLY':
                logging.info('REPLY')
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


def format_content(message_url, channel_mention , author, content):
    '''
    BOTの投稿用にメッセージを成形
    '''
    logging.info('format_content')
    return '*' + message_url + '\nChannel: ' + channel_mention + ' / ' + author + ':*\n>>> ' + content


def create_message_url(message):
    '''
    メッセージのURLを生成
    '''
    logging.info('create_message_url')
    guild_id = message.channel.guild.id
    channel_id = message.channel.id
    message_id = message.id
    result = 'https://discordapp.com/channels/'
    result += str(guild_id) + '/' + str(channel_id) + '/' + str(message_id)
    return result


def get_target_channels(channel):
    '''
    チャンネルが属するカテゴリに含まれるチャンネルを返す
    ただし自身は返さない
    '''
    result = []
    for tmp_channel in channel.category.channels:
        if tmp_channel.id != channel.id:
            result.append(tmp_channel)
    return result


def get_channel_data(channel_name):
    '''
    チャンネル名からベースのチャンネル名とチャンネルの言語を分けて返す
    '''
    result = {}
    index = channel_name.rfind(channel_language_separator)
    if index != -1:
        result['base_channel'] = channel_name[:index]
        index += len(channel_language_separator)
        result['channel_language'] = channel_name[index:]
    return result


def get_message_data(message):
    '''
    ユーザが投稿したメッセージの場合はメッセージから、自身が投稿したメッセージの場合は内容から以下の情報を返す
    ・ギルドID
    ・チャンネルID
    ・メッセージID
    ・チャンネル名
    ・チャンネルの言語
    ・メッセージの更新時間(含まれる場合)
    '''
    result = {}
    channel_name = ''
    # BOTが送信したメッセージではない
    if message.author.bot == False:
        result['message_id'] = message.id
        channel_name = message.channel.name
    # 自身が送信したメッセージ
    elif message.author.id == client.user.id:
        # ギルドID、チャンネルID、メッセージIDを取り出す
        pattern = r'(?<=^\*https\://discordapp\.com/channels/)(?P<guild_id>\d+)/(?P<channel_id>\d+)/(?P<message_id>\d+)(?=$)'
        c = re.compile(pattern, re.DOTALL | re.MULTILINE)
        match = c.search(message.content)
        if match is not None:
            result['guild_id'] = int(match.group('guild_id'))
            result['channel_id'] = int(match.group('channel_id'))
            result['message_id'] = int(match.group('message_id'))
            channel = client.get_channel(result['channel_id'])
            channel_name = channel.name
    result['channel'] = channel_name
    if channel_language_separator in channel_name:
        channel_data = get_channel_data(channel_name)
        if len(channel_data) > 0:
            result['base_channel'] = channel_data['base_channel']
            result['channel_language'] = channel_data['channel_language'] 
    return result


async def armageddon(channel):
    '''
    チャンネル内のメッセージをすべて消す
    '''
    logging.info('armageddon')
    await channel.purge()
    return


def googletrans_translate(content, src_lang, dest_lang):
    result = None
    translator = Translator()
    # 英語をに翻訳してから翻訳する言語
    through__language = {'ja', 'ko', 'ru'}
    # 翻訳に成功するまでループ
    # https://github.com/ssut/py-googletrans/issues/234#issuecomment-722203541
    while True:
        try:
            if (source_language in through__language) and (target_language in through__language):
                tmp = translator.translate(content, src=src_lang, dest='en')
                result = translator.translate(tmp.text, src='en', dest=dest_lang).text
            else:
                result = translator.translate(content, src=src_lang, dest=dest_lang).text
            break
        except  AttributeError:
            translator = Translator()
    return result


def google_trans_new_translate(content_lines, source_language, target_language):
    result = ''
    translator = google_translator(url_suffix="co.jp")
    # 英語をに翻訳してから翻訳する言語
    through__language = {'ja', 'ko', 'ru'}
    # google_trans_newは改行を捨ててしまうようなので1行ごとに翻訳する
    for line in content_lines:
        while True:
            try:
                if (source_language in through__language) and (target_language in through__language):
                    temporary_language = 'en'
                    tmp = translator.translate(line, lang_src=source_language, lang_tgt=temporary_language)
                    result += translator.translate(tmp, lang_src=temporary_language, lang_tgt=target_language)
                else:
                    result += translator.translate(line, lang_src=source_language, lang_tgt=target_language)
                result += '\n'
                break
            except  AttributeError:
                translator = google_translator(url_suffix="co.jp")
    return result


def replace_mention(content):
    '''
    文字列に含まれる@everyone, @hereを一時的に置換する
    データ上、@everyone, @hereはそれぞれ文字列になっている
    '''
    result = content
    replace_strings = {'@everyone':'<@!?901>', '@here':'<@!?902>'}
    for key, value in replace_strings.items():
        result = re.sub(key, value, result)
    return result


def replace_links(content, original_content):
    '''
    翻訳後のメッセージからリンク文字列を置換する
    翻訳後のメッセージを利用すると必要な文字列が不完全なことが多いので、オリジナルの文字列を使用して、その出現順に置換する
    '''
    result = content
    # チャンネルリンク、ユーザ宛てメンション、ロール宛てメンションの置換
    # データ上、チャンネルリンクは<#\d+>、ユーザあてメンションは<@!\d+>、ロール宛てメンションは<@&\d+>になっている
    pattern_list = [r'<[#|＃]+[ |　]*\d+>',
                    r'<[@|＠]+[ |　]*[!|！]+[ |　]*\d+>',
                    r'<[@|＠]+[ |　]*[&|＆]+[ |　]*\d+>']
    for pattern in pattern_list:
        c = re.compile(pattern, re.DOTALL)
        target_iterator = c.finditer(content)
        original_iterator = c.finditer(original_content)
        if (target_iterator is not None) and (original_iterator is not None):
            for target_match in target_iterator:
                if target_match is not None:
                    original_match = next(original_iterator)
                    if original_match is not None:
                        result = result.replace(target_match.group(), original_match.group())
    # @everyone, @hereの置換
    replace_strings = {r'<[@|＠]+[ |　]*[!|！]+[ |　]*[?|？]+[ |　]*901>':'@everyone',
                       r'<[@|＠]+[ |　]*[!|！]+[ |　]*[?|？]+[ |　]*902>':'@here'}
    for key, value in replace_strings.items():
        result = re.sub(key, value, result)
    return result


def azure_translate():
    # 一通りの機能をつくり終えてから乗り換える
    # https://azure.microsoft.com/ja-jp/services/cognitive-services/translator/
    return


client.run(token)
