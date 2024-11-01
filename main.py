import requests
from bs4 import BeautifulSoup
import re
import random
import time
import threading
from queue import Queue
from github import Github
from datetime import datetime
import os
import json
from datetime import datetime


def ip_exists(ip):
    """检查ip是否在文件中存在"""
    try:
        with open('itv.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ip in line:
                    return True
    except FileNotFoundError:
        return False  # 如果文件不存在，返回 False
    return False

def get_ip(diqu):
    """爬取ip"""
    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "max-age=0",
        "content-type": "application/x-www-form-urlencoded",
        "upgrade-insecure-requests": "1",
        "cookie": "REFERER2=Game; REFERER1=Over",
        "Referer": "http://www.foodieguide.com/iptvsearch/hoteliptv.php",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    base_url = "http://www.foodieguide.com/iptvsearch/hoteliptv.php"
    data = {"saerch": diqu, "Submit": "+", "names": "Tom", "city": "HeZhou", "address": "Ca94122"}

    response = requests.post(base_url, headers=headers, data=data)

    ip_list = set()
    if response.status_code == 200:
        # 使用 BeautifulSoup 解析 HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 找到所有的 result div
        results = soup.find_all("div", class_="result")

        for result in results:
            # 提取 IP 地址
            ip_link = result.find("a", href=re.compile(r"hotellist\.html\?s="))
            if ip_link:
                # 从 href 中提取 IP 地址及端口
                ip_address = re.search(r"s=([\d.]+:\d+)", ip_link['href'])
                if ip_address:
                    # 提取状态
                    status_div = result.find("div", style="color: crimson;")
                    if status_div and "暂时失效" in status_div.get_text():
                        continue  # 如果状态为“暂时失效”，则跳过此 IP
                    ip_list.add(ip_address.group(1))  # 添加有效的 IP 地址

    else:
        ip_list.add(f"请求失败，状态码: {response.status_code}")

    return ip_list


def get_iptv(ip_list):
    """爬取频道信息，并过滤掉已存在的 IP"""
    # 遍历每个 IP 地址
    for ip in ip_list:
        if ip_exists(ip):
            print(f"IP {ip} 已存在，跳过爬取。")
            continue  # 如果 IP 存在，则跳过

        # 定义目标 URL，使用当前 IP 地址
        url = f"http://www.foodieguide.com/iptvsearch/allllist.php?s={ip}&y=false"

        # 设置请求头
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "x-requested-with": "XMLHttpRequest",
            "Referer": f"http://www.foodieguide.com/iptvsearch/hotellist.html?s={ip}",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }

        # 发起 GET 请求
        response = requests.get(url, headers=headers)

        # 检查请求是否成功
        if response.status_code == 200:
            # 解析网页内容
            soup = BeautifulSoup(response.text, 'html.parser')

            # 频道计数器
            channel_count = 0

            # 打开文件以追加写入数据
            with open('Origfile.txt', 'a', encoding='utf-8') as file:
                # 找到所有 class="result" 的元素
                results = soup.find_all(class_='result')
                for result in results:
                    # 初始化频道名称和 m3u8 URL
                    channel_name = None
                    m3u8_url = None

                    # 提取频道名称
                    channel = result.find('div', style='float: left;')
                    if channel:
                        channel_name = channel.get_text(strip=True)

                    # 提取 m3u8 URL
                    m3u8 = result.find('td', style='padding-left: 6px;')
                    if m3u8:
                        m3u8_url = m3u8.get_text(strip=True)

                    # 如果找到了频道名称和 URL，则写入文件
                    if channel_name and m3u8_url:
                        file.write(f"{channel_name},{m3u8_url},0\n")
                        channel_count += 1  # 增加频道计数

            # 打印每个 IP 爬取的频道数量
            print(f"IP {ip} 爬取了 {channel_count} 个频道。")
        else:
            print(f"请求失败，状态码: {response.status_code}，IP: {ip}")

    return True  # 返回 True 表示完成


def filter_channels(file_path):
    """对频道名称过滤和修改，同时保留速度信息"""

    try:
        # 读取配置文件 db.json
        with open("db.json", 'r', encoding='utf-8') as config_file:
            config = json.load(config_file)
            keywords = [keyword.lower() for keyword in config["data"]["keywords"]]
            discard_keywords = [keyword.lower() for keyword in config["data"]["discard_keywords"]]
            replace_keywords = {key.lower(): value for key, value in config["data"]["replace_keywords"].items()}

        unique_channels = {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        parts = line.strip().split(',')
                        channel_name = parts[0].strip()
                        url = parts[1].strip()
                        speed = parts[2].strip()

                        # 移除 URL 中的无效字符
                        url_cleaned = url.replace("#", "").replace(" ", "")

                        # 添加 URL 过滤条件，不包含 'http' 的 URL 将被跳过
                        if "http" not in url_cleaned or "///"  in url_cleaned:
                            continue  # 跳过该 URL，不再进行后续检查

                        # 频道名称转换为小写进行关键词过滤
                        lower_channel_name = channel_name.lower()

                        # 如果频道名称包含 discard_keywords 中的关键词，跳过该频道
                        if any(discard_keyword in lower_channel_name for discard_keyword in discard_keywords):
                            continue  # 跳过该频道，不再进行后续检查

                        # 替换频道名称中的关键词（不区分大小写）
                        for key, value in replace_keywords.items():
                            channel_name = re.sub(re.escape(key), value, channel_name, flags=re.IGNORECASE)

                        channel_name = re.sub("CHC电影", "CHC高清电影", channel_name, flags=re.IGNORECASE)

                        if "CCTV" == channel_name :
                            continue
                        if "军旅剧场"==channel_name:
                            channel_name = re.sub("军旅剧场", "NEWTV军旅剧场", channel_name, flags=re.IGNORECASE)

                        # 如果 keywords 为空，跳过关键词筛选
                        if keywords:
                            if any(keyword in lower_channel_name for keyword in keywords):
                                if url not in unique_channels:
                                    unique_channels[url] = (channel_name, speed)
                        else:
                            if url not in unique_channels:
                                unique_channels[url] = (channel_name, speed)

            # 对频道名称进行自然排序
            def natural_sort_key(channel_name):
                match = re.match(r"CCTV(\d+)", channel_name)
                if match:
                    return (0, int(match.group(1)))
                return (1, channel_name)

            # 保存过滤后的频道信息
            with open('itv.txt', 'w', encoding='utf-8') as f:
                sorted_channels = sorted(unique_channels.items(), key=lambda item: natural_sort_key(item[1][0]))
                for index, (url, (channel_name, speed)) in enumerate(sorted_channels, start=123):
                    f.write(f"{channel_name},{url},{speed}\n")

            print("名称筛选和替换完成！")
            return True  # 返回成功

        except Exception as e:
            print(f"处理失败: {e}")
            return False  # 返回失败

    except Exception as e:
        print(f"配置文件读取失败: {e}")
        return False  # 返回失败

def read_channels(filename):
    """读取频道信息，并根据 URL 去重"""
    channels = []
    seen_urls = set()  # 用于存储已处理的 URL

    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            parts = line.strip().split(',')
            name, url, speed = parts[0], parts[1], float(parts[2]) if parts[2].replace('.', '', 1).isdigit() else None
            if url not in seen_urls:
                channels.append((name, url, speed))
                seen_urls.add(url)

    return channels


def test_download_speed(url, test_duration=3):
    """
    测试下载速度，固定访问时间为 test_duration 秒
    """
    try:
        start_time = time.time()
        response = requests.get(url, timeout=test_duration + 5, stream=True)
        response.raise_for_status()

        downloaded = 0
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= test_duration:
                break

            for chunk in response.iter_content(chunk_size=4096):
                downloaded += len(chunk)
                elapsed_time = time.time() - start_time
                if elapsed_time >= test_duration:
                    break

        speed = downloaded / test_duration if test_duration > 0 else 0  # 使用固定的 test_duration
        return speed / (1024 * 1024)  # 转换为 MB/s

    except requests.RequestException:
        return 0


def measure_download_speed_parallel(channels, max_threads=8):
    """
    并行测量下载速度
    """
    results = []
    queue = Queue()
    processed_count = 0  # 记录处理的频道数

    for channel in channels:
        queue.put(channel)

    def worker():
        nonlocal processed_count  # 使用 nonlocal 声明变量
        while not queue.empty():
            channel = queue.get()
            name, url, _ = channel
            speed = test_download_speed(url)
            results.append((name, url, speed))
            processed_count += 1  # 增加已处理的频道数
            if processed_count % (len(channels) // 20) == 0:  # 每处理 5% 的频道打印一次
                print(f"已处理 {processed_count} 个频道")
            queue.task_done()

    threads = []
    for _ in range(max_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)

    queue.join()

    for thread in threads:
        thread.join()

    return results


def natural_key(string):
    """生成自然排序的键"""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', string)]

from datetime import datetime

def group_and_sort_channels(channels):
    """根据规则分组并排序频道信息，并保存到 itvlist 和 filitv"""
    groups = {
        '央视频道,#genre#': [],
        '卫视频道,#genre#': [],
        '其他频道,#genre#': []
    }

    for name, url, speed in channels:
        if 'cctv' in name.lower():
            groups['央视频道,#genre#'].append((name, url, speed))
        elif '卫视' in name or '凤凰' in name:
            groups['卫视频道,#genre#'].append((name, url, speed))
        else:
            groups['其他频道,#genre#'].append((name, url, speed))

    # 对每组进行排序
    for group in groups.values():
        group.sort(key=lambda x: (
            natural_key(x[0]),  # 名称自然排序
            -x[2] if x[2] is not None else float('-inf')  # 速度从高到低排序
        ))

    filtered_groups = {}
    overflow_groups = {}

    for group_name, channel_list in groups.items():
        seen_names = {}
        filtered_list = []
        overflow_list = []

        for channel in channel_list:
            name, url, speed = channel
            if name not in seen_names:
                seen_names[name] = 0

            if seen_names[name] < 8:
                filtered_list.append(channel)
                seen_names[name] += 1
            else:
                overflow_list.append(channel)

        filtered_groups[group_name] = filtered_list
        overflow_groups[group_name] = overflow_list

    # 保存到 itvlist.txt 文件
    with open('itvlist.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in filtered_groups.items():
            file.write(f"{group_name}:\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")  # 打印空行分隔组

    # 添加当前时间的频道到“更新时间”分组
    current_time_str = datetime.now().strftime("%m-%d-%H")
    with open('itvlist.txt', 'a', encoding='utf-8') as file:
        file.write(f"{current_time_str},#genre#:\n{current_time_str},https://git.3zx.top/https://raw.githubusercontent.com/MemoryCollection/IPTV/main/mv.mp4\n")

    # 保存溢出列表到 filitv.txt
    with open('filitv.txt', 'w', encoding='utf-8') as file:
        for group_name, channel_list in overflow_groups.items():
            file.write(f"{group_name}:\n")
            for name, url, speed in channel_list:
                file.write(f"{name},{url},{speed}\n")
            file.write("\n")  # 打印空行分隔组

    print("分组后的频道信息已保存到 itvlist.txt.")
    return groups



def upload_file_to_github(token, repo_name, file_path, branch='main'):
    """
    将结果上传到 GitHub
    """
    g = Github(token)
    repo = g.get_user().get_repo(repo_name)
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    git_path = file_path.split('/')[-1]
    try:
        contents = repo.get_contents(git_path, ref=branch)
    except:
        contents = None
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        if contents:
            repo.update_file(contents.path, current_time, content, contents.sha, branch=branch)
            print("文件已更新")
        else:
            repo.create_file(git_path, current_time, content, branch=branch)
            print("文件已创建")
    except Exception as e:
        print("文件上传失败:", e)


def read_line_count(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for _ in file)




def main():

    line_count = read_line_count('itv.txt')
    if line_count < 700:
        print("爬取IP")
        ip_list = set()
        ip_list.update(get_ip("辽宁")), ip_list.update(get_ip("北京")), ip_list.update(get_ip("CHC")),ip_list.update(get_ip("NEWTV "))

        if ip_list:
            iptv_list = get_iptv(ip_list)
            filter_channels("Origfile.txt")



    channels = read_channels('itv.txt')
    results = measure_download_speed_parallel(channels, max_threads=5)

    with open('itv.txt', 'w', encoding='utf-8') as file:
        for name, url, speed in results:
            if speed >= 0.5:  #只保存速度≥0.5的
                file.write(f"{name},{url},{speed:.2f}\n")

    print("已经完成测速！")

    channels = read_channels('itv.txt')
    if channels:
        group_and_sort_channels(channels)
        token = os.getenv("GITHUB_TOKEN")
        if token:
            upload_file_to_github(token, "IPTV", "itvlist.txt")
            upload_file_to_github(token, "IPTV", "itv.txt")

if __name__ == "__main__":
    main()

