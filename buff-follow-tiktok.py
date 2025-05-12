import requests, time, os, sys
from concurrent.futures import ThreadPoolExecutor

chars = " ➤ [«/»] >>>"

os.system('cls' if os.name == 'nt' else 'clear')

ban = f"""
████████╗████████╗ ██████╗  ██████╗ ██╗     
╚══██╔══╝╚══██╔══╝██╔═══██╗██╔═══██╗██║     
   ██║█████╗██║   ██║   ██║██║   ██║██║     
   ██║╚════╝██║   ██║   ██║██║   ██║██║     
   ██║      ██║   ╚██████╔╝╚██████╔╝███████╗
   ╚═╝      ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝
                © Copyright NgTuw 2024
════════════════════════════════════════════════════════════
{chars} (((Author : NgTuw)))
{chars} Contact Me:
{chars}     -> [@NgTuw2712] [Telegram]
{chars}     -> [TuNguyen2712.Dev] [Facebook]
{chars} Group Me:    
{chars}     -> [https://t.me/NgTuwNET] [Telegram]
{chars} Tool Name:
{chars}     -> [BUFF FOLLOW TIKTOK]
════════════════════════════════════════════════════════════
"""
for i in ban:
    sys.stdout.write(i)
    sys.stdout.flush()
    time.sleep(0.005)

def buff_follow(username):
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'vi,fr-FR;q=0.9,fr;q=0.8,en-US;q=0.7,en;q=0.6',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    }
    while True:
        access = requests.get('https://tikfollowers.com/free-tiktok-followers', headers=headers)
        try:
            session = access.cookies['ci_session']
            headers.update({'cookie': f'ci_session={session}'})
            token = access.text.split("csrf_token = '")[1].split("'")[0]
            data = '{"type":"follow","q":"@'+username+'","google_token":"t","token":"'+token+'"}'
            search = requests.post('https://tikfollowers.com/api/free', headers=headers, data=data).json()
            if search.get('success'):
                data_follow = search['data']
                data = '{"google_token":"t","token":"'+token+'","data":"'+data_follow+'","type":"follow"}'
                send_follow = requests.post('https://tikfollowers.com/api/free/send', headers=headers, data=data).json()
                if send_follow.get('o') == 'Success!' and send_follow.get('success') and send_follow.get('type') == 'success':
                    print(f'{chars} Tăng Follow Tik Tok Thành Công cho tài khoản @{username}')
                elif send_follow.get('o') == 'Oops...' and not send_follow.get('success') and send_follow.get('type') == 'info':
                    try:
                        thoigian = send_follow['message'].split('You need to wait for a new transaction. : ')[1].split('.')[0]
                        phut = thoigian.split(' Minutes')[0]
                        giay = int(phut) * 60
                        for i in range(giay, 0, -1):
                            print(f'{chars} Vui Lòng Chờ {i} Giây cho @{username}...', end='\r')
                            time.sleep(1)
                        continue
                    except:
                        print(f'{chars} Lỗi Không Xác Định cho tài khoản @{username}')
                        continue
        except:
            print(f'{chars} Lỗi Không Xác Định cho tài khoản @{username}')
            continue

if __name__ == '__main__':
    usernames = input(f'{chars} Nhập các Username Tik Tok (không có @) cách nhau bằng dấu phẩy: ').split(',')
    with ThreadPoolExecutor(max_workers=len(usernames)) as executor:
        for username in usernames:
            executor.submit(buff_follow, username.strip())