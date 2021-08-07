# -*- coding: utf-8 -*-
# TODO 增加提示
# TODO 请求报错时，显示哪张照片出了问题
# TODO 增加 help 指令，辅助用户填写。
import asyncio
import os
import re
from datetime import datetime, timedelta

import aiofiles
import aiohttp
import requests

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Color:
    red = '\033[1;31m'
    yellow = '\033[1;33m'
    purple = '\033[1;35m'
    end = '\033[0m'


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
    # 标签搜索可选的模式。
    search_modes = ('exact', 'partial')

    def __init__(self):
        """初始化应用。"""
        # 创建输出目录。
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)
        # 启动异步循环。
        Pixiv.loop = asyncio.get_event_loop()

    @staticmethod
    def hint(message: str):
        """用灰色字体在终端给出提示。

        :param message: 提示内容。
        """
        print(f'{Color.purple}{message}{Color.end}')

    @staticmethod
    def warning(message: str):
        """用黄色字体在终端给出警告。

        :param message: 警告内容。
        """
        print(f'{Color.yellow}{message}{Color.end}')

    @staticmethod
    def error(message: str):
        """用红色字体在终端给出报错。

        :param message: 报错内容。
        """
        print(f'{Color.red}{message}{Color.end}')

    @staticmethod
    def to_local(url: str) -> str:
        """转换为国内地址。

        Pixiv 的图片地址无法直接访问，需要通过代理网站转换为国内可访问的地址。

        :param url: 原地址，源于 Pixiv。

        :returns: 国内可直接访问或爬取的地址。
        """
        # 将地址头改为 "proxy.pixivel.moe"。
        return re.sub('i.pximg.net', 'proxy.pixivel.moe', url)

    @staticmethod
    def get_page_num(quantity: int) -> int:
        """决定爬取的页数。

        网站每页只显示固定数量的插画，该函数可根据用户需要的插画数量，决定爬取几页。

        :param quantity: 用户需要的插画数量。

        :returns: 程序需要爬取的页数。
        """
        # 数量至少为1。
        if quantity < 1:
            Pixiv.error('[Error] Download at least 1 illustration.')
            return 0
        # 数量至多为100。
        if quantity > 100:
            Pixiv.error('[Error] Too many requests may damage the server.')
            return 0
        # 确定爬取页面数。
        return (quantity - 1) // 30 + 1

    @classmethod
    def request(cls, url: str, params: dict = {}) -> requests.Response:
        """发送同步请求。

        向指定的站点发送请求，成功返回响应，失败报错。

        :param url: 目标站点地址。
        :param params: 查询字符串参数。

        :returns: 网站响应。
        """
        response = requests.get(url, headers=cls.headers, params=params)
        # 响应失败：
        if response.status_code != 200:
            # 报错。
            Pixiv.error(
                f'[Error] Request failed with code: {response.status_code}')
            return None
        else:
            # 返回响应。
            return response

    @classmethod
    def save(cls, urls: list[str, str]):
        """异步保存图片。

        为每张图片注册下载任务并启动异步循环。

        :param urls: 元组列表，每个二元元组由图片链接、存储路径组成。
        """
        # 如果传了一个空列表，就直接退出。
        if len(urls) == 0:
            Pixiv.error('[Error] No image found.')
            return
        # 终端提示开始下载。
        Pixiv.hint('Start downloading.')
        # 为每张图片注册下载任务。
        tasks = [cls.download_image(url, filepath)
                 for url, filepath in urls]
        # 开始异步运行。
        cls.loop.run_until_complete(asyncio.wait(tasks))

    @classmethod
    async def download_image(cls, url: str, filepath: str):
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
                    Pixiv.error(
                        f'[Error] Requests failed with code: {response.status}')
                # 响应成功：
                else:
                    # 以字节形式读取响应。
                    content = await response.read()
                    # 持久化存储。
                    async with aiofiles.open(filepath, 'wb') as fw:
                        await fw.write(content)
        # 捕获相对路径，终端提示完成。
        title = re.search(r'.*?[\\/]+(.*)', filepath).group(1)
        print(f'Finished: {title}')

    @classmethod
    def get_io_pairs(cls, img: dict) -> list[str, str]:
        """解析插画下载链接。

        从存储插画数据的字典中，解析出每张分P的图片路径（可直接下载）。

        :param img: 存储插画数据的字典。

        :returns: 元组列表，每个二元元组由图片链接、存储路径组成。
        """
        # 如果插画字典为空，报错。
        if len(img) == 0:
            return []
        # 如果不可见，则报错。
        if not img['visible']:
            Pixiv.warning('''[Warning] This image is currently invisble to you.
            Maybe it's only open to the illustrator's friends.''')
            return []
        # 解析插画 ID。
        id = img['id']
        # 解析插画的标题。
        title = img['title']
        # 去除题目中无法作为文件夹名的字符。
        title = re.sub('[\|/.*?"<>]', ' ', title)
        # 如果该插画只有1P，那么图片链接会存储在 "meta_single_page" 字典里。
        if len(img['meta_single_page']) != 0:
            # 拿到可直接下载的图片链接。
            img_url = cls.to_local(
                img['meta_single_page']['original_image_url'])
            # 直接存储在输出目录下，图片名称为标题。
            filepath = os.path.join(cls.output_dir, f'{title}-{id}.png')
            # 保存至元组列表。
            io_pairs = [(img_url, filepath)]
        else:
            # 拿到可直接下载的图片链接列表。
            img_urls = [cls.to_local(page['image_urls']['original'])
                        for page in img['meta_pages']]
            # 创建二级输出目录，目录名为标题。
            target_dir = os.path.join(cls.output_dir, f'{title}-{id}')
            if not os.path.exists(target_dir):
                os.mkdir(target_dir)
            # 创建每张分P的存储路径列表，图片名称为分P序号。
            filepaths = [os.path.join(
                target_dir, f'{str(index+1).zfill(3)}.png') for index in range(len(img_urls))]
            # 关联链接和路径。
            io_pairs = list(zip(img_urls, filepaths))
        # 返回元组列表。
        return io_pairs

    @classmethod
    def search_by_id(cls, id: str):
        """根据插画 ID 下载图片。

        :param id: 插画 ID。
        """
        # 验证 ID 合法性。
        if re.fullmatch('\d+', id) is None:
            Pixiv.error('[Error] Illegal id.')
            return
        # 插画的数据在下面这个字典里。
        illust = cls.request(cls.api_url, params={
            'type': 'illust',
            'id': f'{id}'
        }).json().get('illust', {})
        # 解析字典，拿到链接列表。
        io_pairs = cls.get_io_pairs(illust)
        # 调用存储函数。
        cls.save(io_pairs)

    @classmethod
    def search_by_member(cls, id: str, quantity: int = 5):
        """根据画师 ID 下载图片。

        搜索指定画师的最新图片。可指定下载张数，默认下载最新5张。

        :param id: 画师 ID。
        :param quantity: 下载图片数量，默认为5，区间在[1, 100]。
        """
        # 验证 ID 合法性。
        if re.fullmatch('\d+', id) is None:
            Pixiv.error('[Error] Illegal id.')
            return
        # 画师信息在这个字典里。
        illustrator = cls.request(cls.api_url, params={
            'type': 'member',
            'id': id
        }).json().get('user', {})
        # 如果不存在该画师，报错。
        if illustrator == {}:
            Pixiv.error(f'[Error] No such illustrator [{id}].')
            return
        # 获取画师名字。
        name = illustrator.get('name', 'Not found')
        Pixiv.hint(f'Name of illustrator: {name}')
        # 确定爬取页面数。
        page_num = cls.get_page_num(quantity)
        # 如果不需要爬，就提前退出。
        if page_num == 0:
            return
        # 每幅插画的数据将存储在下面这个字典列表里。
        illusts = []
        # 依次爬取每一页。
        for page in range(page_num):
            # 该页所有插画的列表。
            cur_page_illusts = cls.request(cls.api_url, params={
                'type': 'member_illust',
                'id': id,
                'page': page
            }).json().get('illusts', [])
            # 获取当前页插画数。
            cur_page_len = len(cur_page_illusts)
            # 如果该页没有插画，说明接下来也不会有了。
            if cur_page_len == 0:
                break
            # 确定想要从这一页下载几幅插画。
            # - 需求还剩几张？
            # - 该页还剩几张？
            # 从这两个数中选最小的。
            desire_len = min(quantity - page * cls.page_quantity, cur_page_len)
            # 将对应数量的插画加入列表。
            illusts.extend(cur_page_illusts[:desire_len])
        # 如果插画数量不达标，给出警告。
        if len(illusts) < quantity:
            Pixiv.warning(
                f'[Warning] We only found {len(illusts)} illustration(s).')
        # 拿到所有图片的链接。
        io_pairs = [
            pair for illust in illusts for pair in cls.get_io_pairs(illust)]
        # 调用存储函数。
        cls.save(io_pairs)

    @classmethod
    def search_by_rank(cls, mode: str = 'day', quantity: int = 30):
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
            Pixiv.error('[Error] Illegal mode.')
            return
        # 修正模式。
        if mode in ('male', 'female', 'manga'):
            mode = f'day_{mode}'
        elif mode in ('original', 'rookie'):
            mode = f'week_{mode}'
        # 确定爬取页面数。
        page_num = cls.get_page_num(quantity)
        # 如果不需要爬，就提前退出。
        if page_num == 0:
            return
        # 指定日期。
        date = (datetime.now() - timedelta(days=2)).strftime("%F")
        # 将每幅插画的字典放入列表。
        illusts = []
        # 对每页发起请求。
        for page in range(page_num):
            # 拿到该页所有插画的列表。
            cur_page_illusts = cls.request(cls.api_url, params={
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
        # 拿到所有图片的链接。
        io_pairs = [
            pair for illust in illusts for pair in cls.get_io_pairs(illust)]
        # 调用存储函数。
        cls.save(io_pairs)

    @classmethod
    def search_by_tags(cls, tags: list, quantity: int = 10, popu: int = 0):
        # 修正标签。
        tags = ' '.join(tags)
        # 依次向各页发送请求，寻找人气高于指定值的插画链接，直到达到指定数量。
        illusts = []
        at_hand = 0
        cur_page = 0
        quit = False
        while not quit:
            Pixiv.hint(f'[Hint] Searching page {cur_page}.')
            # 该页所有插画的列表。
            cur_page_illusts = cls.request(cls.api_url, params={
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
                # 如果超过指定值，就将插画加入列表。
                if illust['total_bookmarks'] >= popu:
                    illusts.append(illust)
                    at_hand += 1
                # 如果数量达标，就退出循环。
                if at_hand == quantity:
                    quit = True
                    break
            # 进入下一页。
            cur_page += 1
        # 如果最终拿到的插画数不足，就给出警告。
        if 0 < len(illusts) < quantity:
            Pixiv.warning(
                f'[Warning] Only found {at_hand} illustration(s).')
        # 拿到所有插画的链接。
        io_pairs = [
            pair for illust in illusts for pair in cls.get_io_pairs(illust)]
        # 调用存储函数。
        cls.save(io_pairs)

    @classmethod
    def quit(cls):
        """退出应用。"""
        # 退出异步循环。
        cls.loop.close()
        print('Quit.')

    @classmethod
    def parse_command_member(cls, args: list):
        if len(args) == 1:
            cls.search_by_member(args[0])
        elif len(args) == 2:
            id, quantity = args
            if re.fullmatch('\d+', quantity):
                cls.search_by_member(id, quantity=int(quantity))
            else:
                Pixiv.error('[Error] Illegal quantity.')
        else:
            Pixiv.error('[Error] Illegal command.')

    @classmethod
    def parse_command_rank(cls, args: list):
        if len(args) == 0:
            cls.search_by_rank()
        elif len(args) == 1:
            arg = args[0]
            if re.fullmatch('\d+', arg):
                cls.search_by_rank(quantity=int(arg))
            else:
                cls.search_by_rank(mode=arg)
        elif len(args) == 2:
            first, second = args
            if re.fullmatch('\d+', first):
                cls.search_by_rank(mode=second, quantity=int(first))
            elif re.fullmatch('\d+', second):
                cls.search_by_rank(mode=first, quantity=int(second))
            else:
                Pixiv.error('[Error] Illegal command.')
        else:
            Pixiv.error('[Error] Illegal command.')

    @classmethod
    def parse_command_tags(cls, args: list):
        if len(args) == 1:
            cls.search_by_tags(args)
        elif len(args) == 2:
            *tag, quantity = args
            if re.fullmatch('\d+', quantity):
                cls.search_by_tags(tag, quantity=int(quantity))
            else:
                cls.search_by_tags(args)
        elif len(args) >= 3:
            *tags, last_1, last_2 = args
            if re.fullmatch('\d+', last_2):
                if re.fullmatch('\d+', last_1):
                    cls.search_by_tags(tags, quantity=int(
                        last_1), popu=int(last_2))
                else:
                    tags.append(last_1)
                    cls.search_by_tags(tags, quantity=int(last_2))
            else:
                cls.search_by_tags(args)


def run():
    app = Pixiv()

    while True:
        command = input('>>> ').split()
        if command[0] == 'id':
            app.search_by_id(command[-1])
        elif command[0] == 'member':
            app.parse_command_member(command[1:])
        elif command[0] == 'rank':
            app.parse_command_rank(command[1:])
        elif command[0] == 'tag':
            app.parse_command_tags(command[1:])
        elif command[0] == 'quit':
            break
        else:
            Pixiv.error('[Error] Illegal command.')

    app.quit()


if __name__ == '__main__':
    run()
