# -*- coding: utf-8 -*-
from color import Color


class Help:
    help_help = f'''
    应用目前支持4种功能:{Color.white}
    - id        按<插画ID>下载
    - member    按<画师ID>下载
    - rank      按<排行榜>下载
    - tag       按<标签+人气值>下载{Color.end}

    您可以输入:
    {Color.purple}>>> help [功能]{Color.end}
    来查看某一功能的具体使用说明。

    例如您输入:
    >>> help id
    就可以获取"按<插画ID>下载"的具体说明。

    最后，输入:
    >>> quit
    可以退出程序。
    '''

    help_id = f'''
    按ID查找插画并下载。

    指令格式:
    {Color.purple}>>> id [插画ID]{Color.end}

    例如您输入:
    >>> id 84026087
    就可以下载[84026087]这幅插画。
    '''

    help_member = f'''
    按ID查找画师，并下载画师最新的若干幅插画。
    我会在下载开始前告诉您这位画师的名字，以便确认TA是否是您要找的画师。

    指令格式:
    {Color.purple}>>> member [画师ID] [插画数量]{Color.end}

    例如您输入:
    >>> member 1980643 3
    就可以下载画师[1980643]的最新[3]幅插画。
    '''

    help_rank = f'''
    从排行榜上，下载最热门的若干幅插画。
    如果您没有指定排行模式，我会默认为您从日榜下载。
    如果您没有指定下载多少幅，我会默认为您下载该排行榜前<30>幅插画。
    排行模式如下:
        - "day" --------- 日榜
        - "week" -------- 周榜
        - "month" ------- 月榜
        - "male" -------- 男性日榜
        - "female" ------ 女性日榜
        - "original" ---- 原创作品榜
        - "rookie" ------ 新人榜
        - "manga" ------- 漫画日榜

    指令格式:
    {Color.purple}>>> rank{Color.end} {Color.gray}[排行模式(选填)]{Color.end} {Color.gray}[插画数量(选填)]{Color.end}

    例如您输入:
    >>> rank
    就可以默认下载[日榜]前[30]幅插画。
    再例如您输入:
    >>> rank week 10
    就可以下载[周榜]前[10]幅插画。
    '''

    help_tag = f'''
    搜索带有指定标签的，人气高于指定值的，最新的若干幅插画。
    标签随便写多少个都可以哦，但能不能搜出结果就得看Pixiv的算法了。
    如果您没有指定最低人气值，我会为您全部下载。(即指定人气值默认为0)

    指令格式:
    {Color.purple}>>> tag [标签] [插画数量]{Color.end} {Color.gray}[人气值(选填)]{Color.end}

    例如您输入:
    >>> tag miku 10
    就可以下载带有[miku]标签的最新[10]幅插画。
    再例如您输入:
    >>> tag VOCALOID miku 10 10000
    就可以下载同时带有[VOCALOID]和[miku]标签的前[10]幅插画，并且人气高于[10000]。
    '''


if __name__ == '__main__':
    while True:
        command = input('>>> ').split()
        if command[0] == 'help':
            print(eval(f'Help.help_{command[-1]}'))
        else:
            print('error')
