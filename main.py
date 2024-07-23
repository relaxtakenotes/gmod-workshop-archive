import httpx
import re
import os
import traceback
from random import choice
from bs4 import BeautifulSoup as bs

workshop_url = "https://steamcommunity.com/id/relaxtakenotes/myworkshopfiles/"

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.3", 
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0."
]

def remove_illegal_chars(filename):
    invalid = r'<>:"/\|?*'

    for char in invalid:
        filename = filename.replace(char, '')
    
    return filename

def get_bs(url):
    page = httpx.get(url, headers={
        "User-Agent": choice(user_agents)
    })
    if page.status_code != 200:
        raise Exception(f"[ERROR: {page.status_code}] Failed to grab URL: {url}")
        return
    return bs(page, features="html.parser")

def get_page_count(url):
    page = get_bs(url)

    paging_controls = page.find("div", {"class": "workshopBrowsePagingControls"})
    if not paging_controls:
        raise Exception(f"[ERROR] Page controls not found. Unable to get page count.")
        return

    matches = re.findall(r"\d", str(paging_controls))
    numbers = []
    for match in matches:
        try:
            numbers.append(int(match))
        except Exception:
            pass
    
    return max(numbers)

def convert_html_description_to_steam(contents):
    def replace_tag(string, pattern, new_tag):
        for match in re.finditer(pattern, string):
            string = string.replace(match.group(), f"[{new_tag}]" + match.group(1) + f"[/{new_tag}]")
            
        return string
    
    def replace_url(string):
        for match in re.finditer(r"<a class=\"bb_link\" href=\"([\s\S]*?)\" .*?>([\s\S]*?)</a>", string):
            string = string.replace(match.group(), f"[url={match.group(1)}]" + match.group(2) + f"[/url]")
            
        return string
    
    def replace_list(string, ordered = False):
        outer_tag = "list"
        pattern = r"<ul class=\"bb_ul\">([\s\S]*?)</ul>"
        
        if ordered:
            outer_tag = "olist"
            pattern = r"<ol>([\s\S]*?)</ol>"
        
        for match in re.finditer(r"<li>(.*?)</li>", string):
            string = string.replace(match.group(), f"[*]" + match.group(1))
        
        for match in re.finditer(pattern, string):
            string = string.replace(match.group(), f"[{outer_tag}]\n" + match.group(1) + f"\n[/{outer_tag}]\n")
        
        return string
    
    def replace_quote(string):
        pattern = r"<blockquote class=\"bb_blockquote with_author\"><div class=\"bb_quoteauthor\">Originally posted by <b>([\s\S]*?)</b>:</div>([\s\S]*?)</blockquote>"
        
        for match in re.finditer(pattern, string):
            string = string.replace(match.group(), f"[quote={match.group(1)}]" + match.group(2) + "[/quote]")
        
        return string
    
    def replace_table(string):
        for match in re.finditer(r"<div class=\"bb_table_th\">([\s\S]*?)</div>", string):
            string = string.replace(match.group(), f"[th]{match.group(1)}[/th]")
        
        for match in re.finditer(r"<div class=\"bb_table_td\">([\s\S]*?)</div>", string):
            string = string.replace(match.group(), f"[td]{match.group(1)}[/td]")
        
        for match in re.finditer(r"<div class=\"bb_table_tr\">([\s\S]*?)</div>", string):
            string = string.replace(match.group(), f"[tr]{match.group(1)}[/tr]")
        
        for match in re.finditer(r"<div class=\"bb_table\">([\s\S]*?)</div>", string):
            string = string.replace(match.group(), f"[table]{match.group(1)}[/table]\n")
        
        return string
    
    def replace_img(string):
        for match in re.finditer(r"<img src=\"([\s\S]*?)\"/>", string):
            string = string.replace(match.group(), f"[img]{match.group(1)}[/img]")
        
        for match in re.finditer(r"<img src=\"([\s\S]*?)\">", string):
            string = string.replace(match.group(), f"[img]{match.group(1)}[/img]")
        
        return string
    
    contents = replace_quote(contents)
    
    contents = replace_url(contents)
    
    contents = replace_list(contents, ordered = False)
    contents = replace_list(contents, ordered = True)

    contents = replace_tag(contents, r"<div class=\"bb_code\">([\s\S]*?)</div>", "code")
        
    contents = replace_table(contents)
    
    contents = replace_tag(contents, r"<div class=\"bb_h1\">([\s\S]*?)</div>", "h1")
    contents = replace_tag(contents, r"<div class=\"bb_h2\">([\s\S]*?)</div>", "h2")
    contents = replace_tag(contents, r"<div class=\"bb_h3\">([\s\S]*?)</div>", "h3")
    
    contents = replace_tag(contents, r"<b>([\s\S]*?)</b>", "b")
    contents = replace_tag(contents, r"<i>([\s\S]*?)</i>", "i")
    contents = replace_tag(contents, r"<u>([\s\S]*?)</u>", "u")
    
    contents = replace_tag(contents, r"<span class=\"bb_strike\">([\s\S]*?)</span>", "strike")
    contents = replace_tag(contents, r"<span class=\"bb_spoiler\"><span>([\s\S]*?)</span></span>", "spoiler")
    
    contents = replace_img(contents)
    
    contents = contents.replace("<br>", "\n").replace("<br/>", "\n")
    contents = contents.replace("<hr>", "[hr][/hr]").replace("<hr/>", "[hr][/hr]")
    
    return contents

def get_item_details(url):
    item = get_bs(url)
    
    name_area = item.find("div", {"class": "game_area_purchase_game"})
    if not name_area:
        raise Exception(f"[ERROR] Item name not found (name_area): {url}")
        return
    
    name_h1 = name_area.find("h1")
    if not name_h1:
        raise Exception(f"[ERROR] Item name not found (name_h1): {url}")
        return
    
    name = name_h1.contents[2]
    
    description = item.find("div", {"class": "workshopItemDescription"})
    if not description or len(description.contents) <= 0:
        description = "[Empty]"
    else:
        description = convert_html_description_to_steam(description.decode_contents())
    
    images = re.findall(r"onclick=\"ShowEnlargedImagePreview\( '(.*?)' \);", str(item))
    
    scripts = item.find_all("script")
    
    for script in scripts:
        for block in re.finditer(r"var rgFullScreenshotURLs = \[([\s\S]*?)\]", str(script)):
            for match in re.finditer(r"'(https://steamuserimages-a\.akamaihd\.net/ugc/.*?)'", block.group(1)):
                images.append(match.group(1))
    
    id = url.replace("https://steamcommunity.com/sharedfiles/filedetails/?id=", "")
    
    return {
        "name": name,
        "description": description,
        "images": images,
        "id": id
    }

def get_all_items(url):
    pages = get_page_count(url)
    items = []
    
    for i in range(1, pages + 1):
        page = get_bs(url + f"?p={i}")
        urls = page.find_all("a", {"class": "ugc"})
        for i in range(len(urls)):
            urls[i] = urls[i]["href"]
        items += urls
    
    return items

def main():
    items = get_all_items(workshop_url)
    print(f"[INFO] Found {len(items)} workshop items")
    
    try:
        os.mkdir("items")
    except FileExistsError:
        pass
    
    for item in items:
        print(f"[INFO] Gathering details for {item}... ")
        
        try:
            details = get_item_details(item)
            
            folder = "items/" + remove_illegal_chars(details["name"]) + f" ({details['id']})"
            try:
                os.mkdir(folder)
            except FileExistsError:
                pass
            
            with open(f"{folder}/details.txt", "w+", encoding="utf-8", errors="ignore") as f:
                f.write(
                    f"Title: {details['name']}\n\n" +
                    f"ID: {details['id']}\n\n" +
                    f"Description: {details['description']}\n\n"
                )
            
            for i, image in enumerate(details["images"]):   
                r = httpx.get(image, headers={
                    "User-Agent": choice(user_agents)
                })
                
                if r.status_code == 200:
                    with open(f"{folder}/{i}.jpg", "wb+") as f:
                        f.write(r.content)
                    print(f"[INFO] Preview image {i + 1}/{len(details['images'])} downloaded")
                else:
                    print(f"[WARNING] Preview image {i + 1}/{len(details['images'])} failed to download: {r.status_code}")
        except Exception as e:
            print(f"Failed! ({str(e)})\n\n{traceback.format_exc()}\n")

        print("[INFO] Done!")
        
    with open(f"results.txt", "w+") as f:
        f.write(f"Archived details of {len(items)} workshop items.\nEnter these URL's (just copy all of them, it accepts lists as well) into gmpublisher downloader to archive the workshop items themselves.\n\n{'\n'.join(items)}")

main()