import os
import re
import discord
from googletrans  import Translator
from google_trans_new import google_translator

channel_language_separator = '-_'
local_message_prefix = '//'
token = os.environ['DISCORD_BOT_TOKEN']
client = discord.Client()


@client.event
async def on_ready():
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
    編集の検知のみ利用
    '''
    if payload.data['edited_timestamp'] is not None:
        target_channel = client.get_channel(payload.channel_id)
        target_message = await target_channel.fetch_message(payload.message_id)
        if target_message.author.bot == False:
            await send_message(target_message, event_type='EDIT')
    return


@client.event
async def on_raw_message_delete(payload):
    '''
    メッセージが消去された
    '''
    source_channel = client.get_channel(payload.channel_id)
    target_channels = get_target_channels(source_channel)
    for target_channel in target_channels:
        async for target_message in target_channel.history():
            if target_message.author.bot == False:
                target_message_id = target_message.id
            else:
                target_message_data = get_message_data(target_message)
                target_message_id = target_message_data['message_id']
            if target_message_id == payload.message_id:
                await target_message.delete()
    return


@client.event
async def on_guild_channel_pins_update(channel, last_pin):
    '''
    ピン留めが更新された
    '''
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


@client.event
async def on_raw_reaction_add(payload):
    '''
    メッセージへリアクションが付けられた
    '''
    # await edit_reaction(payload.user_id, payload.channel_id, payload.message_id, payload.emoji.name, payload.event_type)
    return


@client.event
async def on_raw_reaction_remove(payload):
    '''
    メッセージからリアクションが消された
    '''
    # await edit_reaction(payload.user_id, payload.channel_id, payload.message_id, payload.emoji.name, payload.event_type)
    return


async def send_message(message, **kwargs):
    '''
    メッセージの送信・編集
    '''
    source_channel = message.channel
    source_channel_data = get_channel_data(source_channel.name)
    # 送信先のチャンネルを取得
    target_channels = get_target_channels(source_channel)
    for target_channel in target_channels:
        target_channel_data = get_channel_data(target_channel.name)
        formatted_content = None
        if len(target_channel_data) == 0:
            formatted_content = format_message(message.id, source_channel.name, message.author.display_name, message.content)
        # elif target_channel_data['base_channel'] == source_channel_data['base_channel']:
        else:
            content = google_trans_new_translate(message.content, source_channel_data['channel_language'], target_channel_data['channel_language'])
            formatted_content = format_message(message.id, source_channel.name, message.author.display_name, content)
        event_type = kwargs.get('event_type')
        # 通常
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
            # 編集
            if event_type == 'EDIT':
                async for target_message in target_channel.history():
                    if target_message.is_system() == False:
                        if target_message.author.id == client.user.id:
                            message_data = get_message_data(target_message)
                            if message_data['message_id'] == message.id:
                                await target_message.edit(content=formatted_content)
                                break
                continue
            # 返信
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


def format_message(message_id, channel_name, author, content):
    message_id_string = str(message_id)
    header = '> *Message ID: ' + message_id_string + '*\n> *Channel: ' + channel_name + ' / ' + author + ':*\n'
    return header + content

'''
async def edit_reaction(user_id, channel_id, message_id, emoji, event_type):
    if user_id != client.user.id:
        source_channel = client.get_channel(channel_id)
        source_message = await source_channel.fetch_message(message_id)
        target_message_id = None
        if source_message.author.id != client.user.id:
            target_message_id = source_message.id
        else:
            source_message_data = get_message_data(source_message.content)
            target_message_id = source_message_data['message_id']
        for channel in get_target_channels(source_channel):
            async for message in channel.history():
                msg_id = message_id
                if message.author.bot == True:
                    message_data = get_message_data(message.content)
                    msg_id = message_data['message_id']
                if msg_id == target_message_id:
                    if event_type == 'REACTION_ADD':
                        await message.add_reaction(emoji)
                    elif event_type == 'REACTION_REMOVE':
                        # 他のユーザが同じリアクションをして取り消されたときに消してしまう
                        await message.remove_reaction(emoji, client.user)
                    break
    return
    '''


def get_target_channels(channel):
    '''
    送信の対象になるチャンネルを返す
    引数に与えられたチャンネルは含まれない
    '''
    result = []
    category = channel.category
    for tmp_channel in category.channels:
        if tmp_channel.id != channel.id:
            result.append(tmp_channel)
    return result


def get_channel_data(channel_name):
    '''
    チャンネル名からベースチャンネルと言語を分離する
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
    文字列からメッセージIDとチャンネル情報を取得して返す
    利用者が送信したメッセージでも取得できるようにしたけれどBOTからのメッセージ以外で使っていない気がする
    '''
    result = {}
    channel_name = None
    if message.author.bot == False:
        # BOTが送信したメッセージではない
        result['message_id'] = message.id
        channel_name = message.channel.name
    elif message.author.id == client.user.id:
        # BOTが送信したメッセージ
        pattern = re.compile(r'(?P<message_id>(?<=>\s\*Message\sID:\s)(\d+)(?=\*))', re.DOTALL | re.MULTILINE)
        match = pattern.search(message.content)
        if match:
            message_id = match.group('message_id')
            result['message_id'] = int(message_id)
            pattern = re.compile(r'(?P<channel>(?<=>\s\*Channel:\s)(.+)(?=\s/\s.+:\*))', re.DOTALL | re.MULTILINE)
            match = pattern.search(message.content)
            if match:
                channel_name = match.group('channel')
    result['channel'] = channel_name
    if channel_name in channel_language_separator:
        channel_data = get_channel_data(channel_name)
        if len(channel_data) > 0:
            result['base_channel'] = channel_data['base_channel']
            result['channel_language'] = channel_data['channel_language']
    return result


async def armageddon(channel):
    '''
    古すぎるメッセージを消そうとするとエラーが出る
    '''
    await channel.purge()
    return


def googletrans_translate(content, src_lang, dest_lang):
    '''
    https://pypi.org/project/googletrans/
    '''
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
    '''
    https://pypi.org/project/google-trans-new/
    '''
    result = None
    translator = google_translator()
    while True:
        try:
            # 日本語⇔韓国語の翻訳をするときは英語を経由
            if(source_language == 'ko' and target_language == 'ja') or (source_language == 'ja' and target_language == 'ko'):
                google_trans_new_translate = translator.translate(content, lang_src=source_language, lang_tgt='en')
                result = translator.translate(google_trans_new_translate, lang_src='en', lang_tgt=target_language)
            else:
                result = translator.translate(content, lang_src=source_language, lang_tgt=target_language)
            break
        except  AttributeError:
            translator = google_translator()
    return result


def azure_translate():
    '''
    一通りの機能をつくり終えてから乗り換える
    https://azure.microsoft.com/ja-jp/services/cognitive-services/translator/
    '''
    return


client.run(token)
