import asyncio
import os
import re
from datetime import datetime, timedelta

import aiofiles
import aiohttp
import requests

asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class Pixiv:

    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36 Edg/92.0.902.62'
    }
    output_dir = 'outputs'
    loop = asyncio.get_event_loop()
    api_url = 'https://api.pixivel.moe/pixiv'

    def __init__(self):
        """获取 token，创建请求头。"""
        # 创建 outputs 文件夹。
        if not os.path.exists(self.output_dir):
            os.mkdir(self.output_dir)

    @staticmethod
    def to_local(url: str) -> str:
        """将外网图片地址转换为国内可访问的地址。"""
        # 将地址头改为 "proxy.pixivel.moe"。
        return re.sub('i.pximg.net', 'proxy.pixivel.moe', url)

    @classmethod
    def request(cls, url: str, params: dict = None) -> requests.Response:
        """向指定的站点发送请求，成功返回响应，失败报错退出。"""
        response = requests.get(url, headers=cls.headers, params=params)
        # 响应失败：
        if response.status_code != 200:
            # 报错。
            print(f'Request failed with code: {response.status_code}')
            # 退出。
            exit(-1)
        else:
            # 返回响应。
            return response

    @classmethod
    def save(cls, urls: list[str, str]):
        # 为每个图片链接注册下载任务。
        tasks = [cls.download_image(url, filepath)
                 for url, filepath in urls]
        # 开始异步运行。
        cls.loop.run_until_complete(asyncio.wait(tasks))

    @classmethod
    async def download_image(cls, url: str, filepath: str):
        """异步下载图片，并持久化存储。"""
        # 创建协程对话。
        async with aiohttp.ClientSession() as session:
            # 异步获取响应。
            async with await session.get(url, headers=cls.headers) as response:
                # 响应失败：
                if response.status != 200:
                    # 报错。
                    print(f'Requests failed with code: {response.status}')
                    # 退出。
                    exit(-1)
                # 响应成功：
                else:
                    # 以字节形式读取响应。
                    content = await response.read()
                    # 持久化存储。
                    async with aiofiles.open(filepath, 'wb') as fw:
                        await fw.write(content)

        # 捕获相对路径，终端提示完成。
        title = re.search(r'.*?[\\/]+(.*)', filepath).group(1)
        print(f'{title}下载完成！')

    @classmethod
    def parse_image(cls, img: dict) -> list[str, str]:
        # 插画的标题。
        title = img['title']
        title = re.sub('[\|/.*?"<>]', ' ', title)
        # 如果该插画只有1P，那么图片链接会存储在 "meta_single_page" 字典里。
        if len(img['meta_single_page']) != 0:
            # 拿到可直接下载的图片链接。
            img_url = cls.to_local(
                img['meta_single_page']['original_image_url'])
            # 创建存储路径；直接存储在 outputs 目录下，名称为标题。
            filepath = os.path.join(cls.output_dir, f'{title}.png')
            # 保存至元组列表。
            urls = [(img_url, filepath)]
        else:
            # 拿到可直接下载的图片链接列表。
            img_url_list = [cls.to_local(page['image_urls']['original'])
                            for page in img['meta_pages']]
            # 创建每幅图的存储路径列表；以标题为目录，名称为分P序号。
            target_dir = os.path.join(cls.output_dir, title)
            if not os.path.exists(target_dir):
                os.mkdir(target_dir)
            filepath_list = [os.path.join(
                target_dir, f'{str(index+1).zfill(3)}.png') for index in range(len(img_url_list))]
            # 关联链接和路径。
            urls = list(zip(img_url_list, filepath_list))

        return urls

    @classmethod
    def download_by_id(cls, id: str):
        """根据插画 ID 下载图片。"""
        # 插画的数据在下面这个字典里。
        image_data = cls.request(cls.api_url, params={
            'type': 'illust',
            'id': f'{id}'
        }).json()['illust']
        # 解析字典，拿到链接。
        urls = cls.parse_image(image_data)
        cls.save(urls)

    @classmethod
    def download_by_rank(cls, mode: str = 'day', date: str = None):
        """下载排行榜前30的插画。

        参数
        ---
        mode : str
            "day" --------- 日榜\n
            "week" -------- 周榜\n
            "month" ------- 月榜\n
            "male" -------- 男性日榜\n
            "female" ------ 女性日榜\n
            "original" ---- 原创作品榜\n
            "rookie" ------ 新人榜\n
            "manga" ------- 漫画日榜\n
        """
        # 修正用户模式输入。
        if mode in ('male', 'female', 'manga'):
            mode = f'day_{mode}'
        elif mode in ('original', 'rookie'):
            mode = f'week_{mode}'
        # 若未指定日期，默认为昨天。
        if date is None:
            date = (datetime.now() - timedelta(days=2)).strftime("%F")
        # 每幅插画的数据在下面这个字典列表里。
        image_data_list = cls.request(cls.api_url, params={
            'type': 'rank',
            'page': 0,
            'mode': mode,
            'date': date
        }).json()['illusts']

        # 拿到所有插画的链接。
        urls = [
            tup for image_data in image_data_list for tup in cls.parse_image(image_data)]
        # 调用存储函数。
        cls.save(urls)

    @classmethod
    def quit(cls):
        cls.loop.close()
        print('结束运行！')


if __name__ == '__main__':
    app = Pixiv()
    # app.download_by_id('89925871')
    # app.download_by_id('91689568')
    app.download_by_id('90910709')
    # app.download_by_rank(mode='week')
    app.quit()
