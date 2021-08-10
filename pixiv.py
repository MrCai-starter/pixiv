# -*- coding: utf-8 -*-
import asyncio
import os
import re
from datetime import datetime, timedelta

import aiofiles
import aiohttp
from eprogress import LineProgress
import requests

from color import Color
from help import Help

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Pixiv:
    """爬取 Pixiv 插画。"""
    # 请求头 UA 伪装。
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.62'
    }
    # 输出目录。
    output_dir = 'outputs'
    # 国内 Pixiv 的 api 地址。
    api_url = 'https://api.pixivel.moe/pixiv'
    # 一页能显示的图片数量。
    page_quantity = 30
    # 排行榜可选的模式。
    rank_modes = ('day', 'week', 'month', 'male',
                  'female', 'original', 'rookie', 'manga')
    # 功能汇总。
    functions = ('id', 'member', 'rank', 'tag', 'help')
    # 实际拿到的插画数。
    _supply = 0
    # 已下载的插画数。
    _downloaded = 0
    # 进度条实例。
    _bar = LineProgress(total=100, title='下载进度')

    def __init__(self):
        """初始化应用。"""
        # 创建输出目录。
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        # 启动异步循环。
        Pixiv.__loop = asyncio.get_event_loop()

    @staticmethod
    def __prompt(message: str, end='\n', flush=False):
        """用紫色字体在终端给出提示。

        :param message: 提示内容。
        :param end: 结束字符。
        :param flush: 是否刷新。
        """
        print(f'{Color.purple}{message}{Color.end}', end=end, flush=flush)

    @staticmethod
    def __warning(message: str):
        """用黄色字体在终端给出警告。

        :param message: 警告内容。
        """
        print(f'{Color.yellow}{message}{Color.end}')

    @staticmethod
    def __error(message: str):
        """用红色字体在终端给出报错。

        :param message: 报错内容。
        """
        print(f'{Color.red}{message}{Color.end}')

    @staticmethod
    def __to_local(url: str) -> str:
        """转换为国内地址。

        Pixiv 的图片地址无法直接访问，需要通过代理网站转换为国内可访问的地址。

        :param url: 原地址，源于 Pixiv。

        :returns: 国内可直接访问或爬取的地址。
        """
        # 将地址头改为 "proxy.pixivel.moe"。
        return re.sub('i.pximg.net', 'proxy.pixivel.moe', url)

    @classmethod
    def __get_page_num(cls, quantity: str) -> tuple[int, int]:
        """决定爬取的页数。

        网站每页只显示固定数量的插画，该函数可根据用户需要的插画数量，决定爬取几页。

        :param quantity: 用户需要的插画数量。

        :returns: 转换成整型的数量和程序需要爬取的页数。
        """
        # 检查 quantity 合法性。
        if re.fullmatch('\d+', quantity):
            quantity = int(quantity)
        else:
            cls.__error('[错误] 数量不合法哦!')
            return None, 0
        # 数量至少为1。
        if quantity < 1:
            cls.__error('[错误] 好歹得下个1幅罢(')
            return quantity, 0
        # 数量至多为100。
        if quantity > 100:
            cls.__error('[错误] 一次下载太多图片，有可能损坏别人的服务器的...')
            return quantity, 0
        # 确定爬取页面数。
        page_num = (quantity - 1) // 30 + 1
        # 同时返回整型的 quantity。
        return quantity, page_num

    @classmethod
    def __request(cls, url: str, params: dict = {}) -> requests.Response:
        """发送同步请求。

        向指定的站点发送请求，成功返回响应，失败报错。

        :param url: 目标站点地址。
        :param params: 查询字符串参数。

        :returns: 网站响应。
        """
        response = requests.get(url, headers=cls.headers, params=params)
        # 响应失败则报错：
        if response.status_code != 200:
            cls.__error(f'''[错误] 对 {url} 的请求失败了!
            状态码: {response.status_code}''')
            return None
        # 响应成功则返回响应。
        else:
            return response

    @classmethod
    async def __download_image(cls, url: str, filepath: str):
        """异步下载图片。

        对图片链接发起异步请求，保存到指定路径。

        :param url: 图片链接。
        :param filepath: 存储路径。
        """
        # 创建协程对话。
        async with aiohttp.ClientSession() as session:
            # 异步获取响应。
            async with await session.get(url, headers=cls.headers) as response:
                # 响应失败：
                if response.status != 200:
                    # 报错。
                    cls.__error(f'''[错误] 对 {url} 的请求失败了!
                    状态码: {response.status}''')
                # 响应成功：
                else:
                    # 以字节形式读取响应。
                    content = await response.read()
                    # 持久化存储。
                    try:
                        async with aiofiles.open(filepath, 'wb') as fw:
                            await fw.write(content)
                    except FileNotFoundError:
                        if not os.path.exists(cls.output_dir):
                            os.mkdir(cls.output_dir)
        # 更新进度条。
        cls._downloaded += 1
        percent = cls._downloaded / cls._supply * 100
        cls._bar.update(percent)

    @classmethod
    def __get_image_pairs(cls, illust: dict) -> list[tuple[str, str]]:
        """解析插画下载链接。

        从存储插画数据的字典中，解析出每张分P的图片路径（可直接下载）。

        :param illust: 存储插画数据的字典。

        :returns: 元组列表，每个二元元组由图片链接、存储路径组成。
        """
        # 如果插画字典为空，报错。
        if len(illust) == 0:
            return []
        # 如果不可见，则报错。
        if not illust['visible']:
            cls.__warning('[提示] 这幅插画对您不可见，也许只有画师的好友能看到?')
            return []
        # 解析插画 ID。
        id = illust['id']
        # 解析插画的标题。
        title = illust['title']
        # 去除题目中无法作为文件或文件夹名的字符。
        title = re.sub('[\|/:*?"<>]', ' ', title)
        # 如果该插画只有1P，那么图片链接会存储在"meta_single_page"字典里。
        if illust['page_count'] == 1:
            # 拿到可直接下载的图片链接。
            image_url = cls.__to_local(
                illust['meta_single_page']['original_image_url'])
            # 直接存储在输出目录下，图片名称为标题。
            filepath = os.path.join(cls.output_dir, f'{title}-{id}.png')
            # 保存至元组列表。
            image_pairs = [(image_url, filepath)]
        # 如果该插画不止1P，那么图片链接会存储在"meta_pages"字典里。
        else:
            # 拿到可直接下载的图片链接列表。
            image_urls = [cls.__to_local(page['image_urls']['original'])
                          for page in illust['meta_pages']]
            # 创建二级输出目录，目录名为标题。
            target_dir = os.path.join(cls.output_dir, f'{title}-{id}')
            if not os.path.exists(target_dir):
                os.mkdir(target_dir)
            # 创建每张分P的存储路径列表，图片名称为分P序号。
            filepaths = [os.path.join(
                target_dir, f'{str(index+1).zfill(3)}.png') for index in range(len(image_urls))]
            # 关联链接和路径。
            image_pairs = list(zip(image_urls, filepaths))
        # 返回元组列表。
        return image_pairs

    @classmethod
    def __save(cls, illusts: list[dict]):
        """异步保存图片。

        为每张图片注册下载任务并启动异步循环。

        :param illusts: 字典列表，每个字典都存储一组插画的数据。
        """
        # 解析字典，拿到链接列表。
        image_pairs = [
            pair for illust in illusts for pair in cls.__get_image_pairs(illust)]
        # 如果一张图片都没有，就直接退出。
        if len(image_pairs) == 0:
            cls.__error('[错误] 找不到这幅图哦!')
            return
        # 更新进度条。如果设为0，进度条不会更新，所以设成0.1。
        cls._bar.update(0.1)
        # 更新类变量。
        cls._supply = len(image_pairs)
        # 为每张图片注册下载任务。
        tasks = [cls.__download_image(url, filepath)
                 for (url, filepath) in image_pairs]
        # 开始异步运行。
        cls.__loop.run_until_complete(asyncio.wait(tasks))
        # 全部下载完成后，准备下一轮。
        cls.__clear()

    @classmethod
    def __search_by_id(cls, id: str):
        """根据插画 ID 下载图片。

        :param id: 插画 ID。
        """
        # 验证 ID 合法性。
        if re.fullmatch('\d{1,10}', id) is None:
            cls.__error('[错误] ID不合法哦!')
            return
        # 插画的数据在下面这个字典（一元）列表里。
        illusts = [cls.__request(cls.api_url, params={
            'type': 'illust',
            'id': id
        }).json().get('illust', {})]
        # 调用存储函数。
        cls.__save(illusts)

    @classmethod
    def __search_by_member(cls, id: str, quantity: str):
        """根据画师 ID 下载图片。

        搜索指定画师的最新图片。可指定下载张数，默认下载最新5张。

        :param id: 画师 ID。
        :param quantity: 下载图片数量，默认为5，区间在[1, 100]。
        """
        # 验证 ID 合法性。
        if re.fullmatch('\d{1,10}', id) is None:
            cls.__error('[错误] ID不合法哦!')
            return
        # 验证数量合法性，以及确定爬取页面数。
        quantity, page_num = cls.__get_page_num(quantity)
        # 如果不需要爬，就提前退出。
        if page_num == 0:
            return
        # 画师信息在这个字典里。
        illustrator = cls.__request(cls.api_url, params={
            'type': 'member',
            'id': id
        }).json().get('user', {})
        # 如果不存在该画师，报错。
        if illustrator == {}:
            cls.__error(f'[错误] 找不到[{id}]这位画师诶?')
            return
        # 获取画师名字。
        name = illustrator.get('name', 'Not found')
        cls.__prompt(f'这位画师叫: {name}')
        # 每幅插画的数据将存储在下面这个字典列表里。
        illusts = []
        # 依次爬取每一页。
        for page in range(page_num):
            # 该页所有插画的列表。
            cur_page_illusts = cls.__request(cls.api_url, params={
                'type': 'member_illust',
                'id': id,
                'page': page
            }).json().get('illusts', [])
            # 如果该页没有插画，说明接下来也不会有了。
            if len(cur_page_illusts) == 0:
                break
            # 确定想要从这一页下载几幅插画。
            # - 需求还剩几张？
            # - 该页还剩几张？
            # 从这两个数中选最小的。
            desire_len = min(quantity - page *
                             cls.page_quantity, len(cur_page_illusts))
            # 将对应数量的插画加入列表。
            illusts.extend(cur_page_illusts[:desire_len])
        # 如果拿到了，但是插画数量不达标，给出警告。
        if 0 < len(illusts) < quantity:
            cls.__warning(
                f'[提示] 我只找到了{len(illusts)}幅插画...')
        # 调用存储函数。
        cls.__save(illusts)

    @classmethod
    def __search_by_rank(cls, mode: str = 'day', quantity: str = '30'):
        """按排行榜下载。

        下载指定日期、指定排行榜榜顶的指定数量的插画。默认下载日榜前30张。

        :param mode: 排行模式。
            - "day" --------- 日榜
            - "week" -------- 周榜
            - "month" ------- 月榜
            - "male" -------- 男性日榜
            - "female" ------ 女性日榜
            - "original" ---- 原创作品榜
            - "rookie" ------ 新人榜
            - "manga" ------- 漫画日榜
        :param quantity: 下载图片数量，默认为30，区间在[1, 100]。
        """
        # 判断模式是否合法。
        if mode not in cls.rank_modes:
            cls.__error('[错误] 模式不合法哦!')
            return
        # 修正模式。
        if mode in ('male', 'female', 'manga'):
            mode = f'day_{mode}'
        elif mode in ('original', 'rookie'):
            mode = f'week_{mode}'
        # 确定爬取页面数。
        quantity, page_num = cls.__get_page_num(quantity)
        # 如果不需要爬，就提前退出。
        if page_num == 0:
            return
        # 将每幅插画的字典放入列表。
        illusts = []
        for day_delta in range(3):
            # 指定日期。
            date = (datetime.now() - timedelta(days=day_delta)).strftime("%F")
            # 对每页发起请求。
            for page in range(page_num):
                # 拿到该页所有插画的列表。
                cur_page_illusts = cls.__request(cls.api_url, params={
                    'type': 'rank',
                    'page': page,
                    'mode': mode,
                    'date': date
                }).json().get('illusts', [])
                # 该页插画数量。
                cur_page_len = len(cur_page_illusts)
                # 如果该页没有插画，说明接下来也不会有了。
                if cur_page_len == 0:
                    break
                # 确定想要从这一页下载几幅插画。
                # - 需求还剩几张？
                # - 该页还剩几张？
                # 从这两个数中选最小的。
                desire_len = min(
                    quantity - page*cls.page_quantity, cur_page_len)
                # 将对应数量的插画加入列表。
                illusts.extend(cur_page_illusts[:desire_len])
            # 如果拿到了，就不用继续循环了。
            if len(illusts) != 0:
                break
        # 调用存储函数。
        cls.__save(illusts)

    @classmethod
    def __search_by_tag(cls, tags: list, quantity: str, popularity: int = 0):
        """按标签下载。

        搜索指定的多个标签、指定数量、指定人气的插画。

        :param tags: 标签组列表。
        :param quantity: 需求数量，区间为[1, 100]。
        :param popularity: 人气最低值，默认为0。
        """
        # 检验数量合法性。
        quantity, _ = cls.__get_page_num(quantity)
        if _ == 0:
            return
        # 检查是否需要 R-18 图片。
        is_r18 = True if 'R-18' in tags else False
        # 修正标签。
        tags = ' '.join(tags)
        # 用"users入り"方法先找一遍。
        illusts = cls.__get_illusts_by_tags(
            f'{tags} {popularity}users入り', quantity, is_r18=is_r18, is_traverse=False)
        # 如果没拿到，就转用遍历法搜索。
        if len(illusts) == 0:
            illusts = cls.__get_illusts_by_tags(
                tags, quantity, is_r18=is_r18, is_traverse=True, popularity=popularity)
        # 如果拿到了，但是插画数不足，就给出警告。
        if 0 < len(illusts) < quantity:
            cls.__warning(
                f'\r[提示] 我只找到了{len(illusts)}幅插画...')
        # 调用存储函数。
        cls.__save(illusts)

    @classmethod
    def __get_illusts_by_tags(cls, tags: str, quantity: int, is_r18: bool, is_traverse: bool, popularity: int = 0) -> list[dict]:
        """为按标签搜索的函数找到插画列表。

        搜索指定的多个标签、指定数量、指定人气的插画。

        :param tags: 标签字符串。
        :param quantity: 需求数量，区间为[1, 100]。
        :param is_r18: 是否需要 R-18 图片。
        :param is_traverse: 是否按照遍历法搜索。
        :param popularity: 人气最低值，默认为0。

        :returns: 插画字典列表。
        """
        # 存储插画字典的列表。
        illusts = []
        # 依次向各页发送请求，寻找人气高于指定值的插画链接，直到达到指定数量。
        at_hand = 0
        cur_page = 0
        quit = False
        while not quit:
            cls.__prompt(
                f'\r正在第{cur_page}页里查找...', end='', flush=True)
            # 该页所有插画的列表。
            cur_page_illusts = cls.__request(cls.api_url, params={
                'type': 'search',
                'word': tags,
                'page': cur_page,
                'mode': 'partial_match_for_tags'
            }).json().get('illusts', [])
            # 如果当前页的插画数已不足需求，就提前退出。
            if len(cur_page_illusts) < min(quantity - at_hand, cls.page_quantity):
                quit = True
            # 检查每幅插画的人气。
            for illust in cur_page_illusts:
                # 如果 R-18 与需求不一致，就检查下一幅。
                if ('R-18' in [tags['name'] for tags in illust['tags']]) ^ is_r18:
                    continue
                # 如果我需要一张张检查人气，并且人气不达标，也检查下一幅。
                if is_traverse and (illust['total_bookmarks'] < popularity):
                    continue
                # 如果与需求一致，就加入列表。
                illusts.append(illust)
                at_hand += 1
                # 如果数量达标，就退出循环。
                if at_hand == quantity:
                    quit = True
                    break
            # 进入下一页。
            cur_page += 1
        # 返回插画列表。
        return illusts

    @classmethod
    def __clear(cls):
        """清空与进度条相关的变量，准备下一轮。"""
        cls._supply = 0
        cls._downloaded = 0
        # 从进度条处换行。
        print('')

    @classmethod
    def __quit(cls):
        """退出应用。"""
        # 退出异步循环。
        cls.__loop.close()

    @classmethod
    def parse_command_id(cls, args: list):
        """解析按插画 ID 搜索的指令。

        :param args: 指令参数列表。
        """
        # 必须只能传1个参数。
        if len(args) == 1:
            cls.__search_by_id(args[0])
        # 不是1个参数，就报错。
        else:
            cls.__error('[错误] 指令不对哦!要不再看一眼help?')

    @classmethod
    def parse_command_member(cls, args: list):
        """解析按画师 ID 搜索的指令。

        :param args: 指令参数列表。
        """
        # 必须有2个参数，id、数量：
        if len(args) == 2:
            cls.__search_by_member(args[0], args[1])
        # 不是2个参数，就报错。
        else:
            cls.__error('[错误] 指令不对哦!要不再看一眼help?')

    @classmethod
    def parse_command_rank(cls, args: list):
        """解析按排行榜搜索的指令。

        :param args: 指令参数列表。
        """
        # 如果没给参数，就按默认的来。
        if len(args) == 0:
            cls.__search_by_rank()
        # 如果有1个参数：
        elif len(args) == 1:
            arg = args[0]
            # 如果它是数字，说明是数量。
            if re.fullmatch('\d+', arg):
                cls.__search_by_rank(quantity=arg)
            # 如果它不是数字，说明是模式。
            else:
                cls.__search_by_rank(mode=arg)
        # 如果有2个参数，它们分别就是模式和数量。
        elif len(args) == 2:
            cls.__search_by_rank(mode=args[0], quantity=args[1])
        else:
            cls.__error('[错误] 指令不对哦!要不再看一眼help?')

    @classmethod
    def parse_command_tag(cls, args: list):
        """解析按标签搜索的指令。

        :param args: 指令参数列表。
        """
        # 参数至少需要2个：
        if len(args) >= 2:
            # 挑出最后2个检查，前面的全都看作标签。
            *tags, last_1, last_2 = args
            # 如果全是数字，说明一个是数量，一个是人气。
            if re.fullmatch('\d+', f'{last_1}{last_2}'):
                cls.__search_by_tag(tags, last_1, popularity=int(last_2))
            # 如果不全是数字，说明未指定人气，可推出倒数第2个也是标签，最后1个是数量。
            else:
                tags.append(last_1)
                cls.__search_by_tag(tags, last_2)
        # 如果不足2个，就报错。
        else:
            cls.__error('[错误] 指令不对哦!要不再看一眼help?')

    @classmethod
    def parse_command_help(cls, args: list):
        """解析帮助的指令。

        :param args: 指令参数列表。
        """
        if len(args) == 0:
            print(Help.help_help)
        elif len(args) == 1:
            print(eval(f'Help.help_{args[0]}'))
        else:
            cls.__error('[错误] 指令不对哦!要不再看一眼help?')

    @classmethod
    def run_on_terminal(cls):
        """在终端运行程序。"""
        while True:
            command = input('>>> ').split()
            if len(command) == 0:
                continue
            elif command[0] == 'quit':
                break
            elif command[0] in cls.functions:
                eval(f'cls.parse_command_{command[0]}(command[1:])')
            else:
                cls.__error('[错误] 指令不对哦!要不再看一眼help?')

        cls.__quit()


if __name__ == '__main__':
    app = Pixiv()
    app.run_on_terminal()
